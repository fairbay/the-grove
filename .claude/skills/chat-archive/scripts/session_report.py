#!/usr/bin/env python3
"""Session usage and routing report from Claude Code transcripts (numbers and labels only).

usage: python3 .claude/skills/chat-archive/scripts/session_report.py <session-dir-prefix> <out.json> <out.md> [--routing]
  <session-dir-prefix> is ~/.claude/projects/<project>/<session-id> (no extension):
  <prefix>.jsonl is the main thread; <prefix>/subagents/agent-*.jsonl (+ .meta.json) are the sub-agents.

Token usage is counted once per API request (one response is stored as one record per content block,
all carrying the same usage). No message text, tool output or environment values are copied: labels are
the first 100 characters of a task, targets are file paths or the first 80 characters of a command, both
with token-like strings redacted.

The JSON carries "cache_read_m": the session's cache-read tokens in millions by model family ({"opus": 12.3,
"sonnet": 4.1}), from the harness cost-state record when the transcript has one, else summed from the
transcripts' usage; it is the session record's cache_read_m (chat-archive references/session-record.md;
the weekly ops read's S10 line sums it per day).

Optional: --routing adds a "routing" section (last JSON key, one "Routing:" Markdown line, and a record line on stdout after the
summary line: asks, refusals, merges, source and cache_read_m): the AskUserQuestion calls of the main thread (when asked, when answered,
when the next tool call came, number of questions and their header labels), the tool results that are a harness permission refusal
(classifier, safety check, rule, user rejection; main thread and sub-agents) and the pull-request merge attempts with their outcome (merged,
refused, failed), one per PR a call names (a loop over two PRs is two; merges_of). It copies no question text and no answer; the only free text kept is the first 200 characters of a classifier's reason,
redacted like every other label. Without it the output is as before.

--record (its own options; see record_main) prints the whole session record as one JSON line, ready for the Grove session-record
decision's context: the routing counts, cache_read_m, the start (pasted, typed or none), and every PR opened or landed with how it merged
(self, ask, github, pending, open) and whether that cost Baylee a tap. It exits 2, printing nothing on stdout, when the record would
be partial or inconsistent (a PR this session opened or merged that --prs does not name, say). chat-archive references/session-record.md.

--check-record <decision id> [--lane x] reads the logged record back from Grove (GROVE_TOKEN) and exits 2, naming each problem,
when the weekly reads would skip it (no context, context not the record JSON, no session-record or lane tag).

A repo wraps this script for its own extras (MBN scripts/session-usage/report.py; it puts the synced
.claude/skills/chat-archive/scripts on sys.path and imports the module): `session_report.PATH_PATTERNS.insert(0, …)` adds the repo's
path generalizations, `session_report.COPY_WATCH = "…"` (assigned on the module, not an imported name) names a path substring whose
copy-command destinations are counted, parse_args(argv, opts, usage) parses its own valued options, and main(..., sections=[...])
appends sections (each callable takes the report dict and returns (key, value, markdown line)) after the base report and before routing.
"""
import json, os, re, shlex, sys, collections, datetime, hashlib

CWD_PREFIX = None  # set from the first record's cwd

PATH_PATTERNS = [  # (regex, replacement) applied to file paths in labels; a wrapper inserts its repo's own in front
    (re.compile(r"/tmp/[^ ]*?/scratchpad/"), "<scratchpad>/"),
    (re.compile(r"shots/[^/]+\.png"), "shots/<shot>.png"),
]
COPY_WATCH = None  # a path substring (MBN: "scripts/mNNNN"); when set, copy commands whose destination or source holds it are counted
MODEL_FAMILY = re.compile(r"(opus|sonnet|haiku|fable|mythos)")  # a model id's family; anything else is "other"

SECRET = re.compile(r"(eyJ[A-Za-z0-9_\-]{20,}|sbp_[A-Za-z0-9]{10,}|[A-Fa-f0-9]{32,}|ghp_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_\-]{20,})")
def redact(s):
    return SECRET.sub("<redacted>", s or "")

def rel(p):
    if not p: return p
    if CWD_PREFIX and p.startswith(CWD_PREFIX + "/"): return p[len(CWD_PREFIX) + 1:]
    return p

def pattern(p):
    p = rel(p)
    for rx, rep in PATH_PATTERNS: p = rx.sub(rep, p)
    return p

def target_of(name, inp):
    if not isinstance(inp, dict): return ""
    for k in ("file_path", "path", "notebook_path"):
        if inp.get(k): return redact(pattern(str(inp[k])))[:120]
    if name == "Bash": return redact(" ".join(str(inp.get("command", "")).split()))[:80]
    if name in ("Grep", "Glob"): return redact(str(inp.get("pattern", "")))[:80]
    if name == "Agent": return redact(" ".join(str(inp.get("description") or inp.get("prompt", "")).split()))[:80]
    if name == "ToolSearch": return redact(str(inp.get("query", "")))[:80]
    if name.startswith("mcp__"): return ""
    return redact(" ".join(json.dumps(inp)[:200].split()))[:80]

def result_size(block, rec):
    c = block.get("content")
    n = 0
    if isinstance(c, str): n = len(c)
    elif isinstance(c, list):
        for b in c:
            if isinstance(b, dict):
                if b.get("type") == "text": n += len(b.get("text", ""))
                elif b.get("type") == "image": n += len(json.dumps(b))
    tur = rec.get("toolUseResult")
    if isinstance(tur, dict) and isinstance(tur.get("persistedOutputSize"), int):
        n = max(n, tur["persistedOutputSize"])
    return n

def hour(ts):
    return ts[:13] + ":00Z" if ts else None

def parse(path, agent_id, label, model_hint):
    global CWD_PREFIX
    seen_req = set()
    run = {"agent": agent_id, "label": label, "model": model_hint, "start": None, "end": None,
           "input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "requests": 0, "tool_calls": 0,
           "write_edit_bytes": 0, "output_tokens_recorded": 0, "output_chars": 0}
    models = collections.Counter()
    cache_by_family = collections.Counter()  # cache-read tokens by the family of each request's own model (a run may switch models)
    pending = {}  # tool_use_id -> (name, target, hour, input_size)
    events = []  # per tool call: dict
    hourly = collections.defaultdict(lambda: {"input": 0, "output_tokens_recorded": 0, "cache_read": 0, "cache_write": 0, "tool_calls": 0, "requests": 0, "output_chars": 0})
    writes = []  # (pattern, path, bytes, tool)
    cps = []  # cp commands: (hour, command80, dests)
    compactions = 0
    first_user = None
    for line in open(path):
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except Exception: continue
        t = o.get("type")
        ts = o.get("timestamp")
        if CWD_PREFIX is None and o.get("cwd"): CWD_PREFIX = o["cwd"]
        if ts and t in ("user", "assistant", "system"):
            run["start"] = run["start"] or ts
            run["end"] = ts
        if t == "system" and o.get("subtype") == "compact_boundary": compactions += 1
        if t == "user" and o.get("isCompactSummary"): pass
        m = o.get("message") or {}
        if t == "user":
            c = m.get("content")
            if first_user is None and isinstance(c, str): first_user = c
            if first_user is None and isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "text": first_user = b.get("text", ""); break
            if isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        size = result_size(b, o)
                        p = pending.pop(b.get("tool_use_id"), None)
                        if p:
                            events.append({"tool": p[0], "target": p[1], "hour": p[2], "input_size": p[3], "result_size": size, "agent": agent_id})
                        else:
                            events.append({"tool": "?", "target": "", "hour": hour(ts), "input_size": 0, "result_size": size, "agent": agent_id})
        elif t == "assistant":
            mod = m.get("model")
            if mod and not mod.startswith("<"): models[mod] += 1
            rid = o.get("requestId") or o.get("uuid")
            u = m.get("usage") or {}
            if rid not in seen_req and u:
                seen_req.add(rid)
                run["requests"] += 1
                h = hourly[hour(ts)]
                for k, uk in (("input", "input_tokens"), ("output_tokens_recorded", "output_tokens"), ("cache_read", "cache_read_input_tokens"), ("cache_write", "cache_creation_input_tokens")):
                    v = u.get(uk) or 0
                    run[k] += v; h[k] += v
                h["requests"] += 1
                cache_by_family[family(mod)] += u.get("cache_read_input_tokens") or 0
            for b in m.get("content") or []:
                if not isinstance(b, dict): continue
                oc = len(b.get("text", "")) if b.get("type") == "text" else len(b.get("thinking", "")) if b.get("type") == "thinking" else len(json.dumps(b.get("input") or {})) if b.get("type") == "tool_use" else 0
                run["output_chars"] += oc; hourly[hour(ts)]["output_chars"] += oc
                if b.get("type") != "tool_use": continue
                name = b.get("name", "?"); inp = b.get("input") or {}
                run["tool_calls"] += 1; hourly[hour(ts)]["tool_calls"] += 1
                pending[b.get("id")] = (name, target_of(name, inp), hour(ts), len(json.dumps(inp)))
                if name == "Write" and isinstance(inp, dict):
                    n = len(inp.get("content") or ""); run["write_edit_bytes"] += n
                    writes.append((pattern(inp.get("file_path", "")), rel(inp.get("file_path", "")), n, "Write"))
                elif name == "Edit" and isinstance(inp, dict):
                    n = len(inp.get("new_string") or ""); run["write_edit_bytes"] += n
                    writes.append((pattern(inp.get("file_path", "")), rel(inp.get("file_path", "")), n, "Edit"))
                elif name == "Bash" and isinstance(inp, dict):
                    cmd = str(inp.get("command", ""))
                    for seg in re.split(r"&&|;|\|\||\n", cmd):
                        toks = seg.strip().split()
                        if len(toks) >= 3 and toks[0] in ("cp", "rsync", "install") or (len(toks) >= 3 and toks[0] == "git" and toks[1] in ("checkout",) and "--" in toks):
                            dests = []
                            for x in toks[1:]:
                                if x.startswith("-"): continue
                                mb = re.match(r"^(.*)\{([^}]*)\}(.*)$", x)
                                if mb: dests.extend(rel(mb.group(1) + part + mb.group(3)) for part in mb.group(2).split(","))
                                else: dests.append(rel(x))
                            cps.append({"hour": hour(ts), "command": redact(" ".join(toks))[:80], "args": [pattern(d) for d in dests]})
    for p in pending.values():
        events.append({"tool": p[0], "target": p[1], "hour": p[2], "input_size": p[3], "result_size": 0, "agent": agent_id})
    if models: run["model"] = models.most_common(1)[0][0]
    if first_user and label is None: run["label"] = redact(" ".join(first_user.split()))[:100]
    return run, events, hourly, writes, cps, compactions, models, cache_by_family

REFUSAL_PREFIXES = [  # Claude Code's own wording; (pattern at the start of a line, kind, has a "Reason: " tail)
    (re.compile(r"^Permission for this action was denied by the Claude Code auto mode classifier\. Reason: ", re.M), "classifier", True),
    (re.compile(r"^Permission for this action has been denied\. Reason: ", re.M), "classifier", True),
    (re.compile(r"^Permission for this command was denied by a built-in Claude Code safety check", re.M), "safety_check", False),
    (re.compile(r"^Permission to use .* has been denied", re.M), "rule", False),
    (re.compile(r"^The user doesn['\u2019]t want to proceed with this tool use\.", re.M), "user_rejected", False),
]
KIND_ORDER, OUTCOME_ORDER = ("classifier", "safety_check", "rule", "user_rejected"), ("merged", "refused", "failed")

def result_text(content):
    if isinstance(content, str): return content
    if isinstance(content, list): return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""

def refusal_of(text, is_error=False):
    """(kind, reason) when a tool result is a harness permission refusal, else None; reason only for the classifier kinds.
    The text must start with a prefix, or the result must be an error with a prefix starting one of its lines (a non-error result that
    only prints the wording, such as a grep of the binary, is not a refusal)."""
    text = text.lstrip()
    for rx, kind, has_reason in REFUSAL_PREFIXES:
        m = rx.search(text) if is_error else rx.match(text)
        if m:
            reason = redact(text[m.end():].split("\n", 1)[0].strip())[:200] if has_reason else None
            return kind, reason
    return None

def strip_heredocs(cmd):
    """The command without heredoc bodies (from a <<WORD, <<'WORD', <<"WORD" or <<-WORD marker to the line that is exactly WORD)."""
    out, ends = [], []
    for line in cmd.split("\n"):
        if ends:
            word, dash = ends[0]
            if (line.lstrip("\t") if dash else line).rstrip("\r") == word: ends.pop(0)
            continue
        out.append(line)
        ends = [(m.group(3), m.group(1) == "-") for m in re.finditer(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2", line)]
    return "\n".join(out)

def shell_segments(cmd):
    """Splits on &&, ||, ;, | and newlines outside single and double quotes."""
    segs, cur, q, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if q:
            cur.append(ch)
            if ch == "\\" and q == '"' and i + 1 < len(cmd): i += 1; cur.append(cmd[i])
            elif ch == q: q = None
        elif ch in "'\"": q = ch; cur.append(ch)
        elif ch == "\\" and i + 1 < len(cmd): cur.append(ch); i += 1; cur.append(cmd[i])
        elif ch in ";\n|" or cmd.startswith("&&", i):
            if cmd.startswith(("&&", "||"), i): i += 1
            segs.append("".join(cur)); cur = []
        else: cur.append(ch)
        i += 1
    segs.append("".join(cur))
    return segs

ENV_PREFIX = re.compile(r"""^[({\s]*(?:(?:command|env|\w+=(?:"[^"]*"|'[^']*'|\S*))\s+)*""")

SHELL_KEYWORD = re.compile(r"^\s*(?:(?:do|then|else|elif)\s+|[({]\s*)*")
FOR_LOOP = re.compile(r"^\s*for\s+([A-Za-z_]\w*)\s+in\s+(.*)$", re.S)
PR_REF = r"(\d+|\$\{?[A-Za-z_]\w*\}?)"  # a literal number or a shell variable ($n, ${n})
VALUE_FLAGS = {"-R", "--repo", "-t", "--subject", "-b", "--body", "-F", "--body-file", "-A", "--author-email", "--match-head-commit"}

def loop_words(spec):
    """A for loop's words; [None] when the list is not plain words ($(seq …), {1..3}, $VAR, backticks): one unchecked entry, never a guess."""
    words = [w.strip("'\"") for w in re.sub(r"(?:^|\s)#.*", "", spec).split()]
    return [None] if any(re.search(r"[$(){}`]", w) for w in words) else words

def pr_numbers(tok, loops):
    """The PR numbers one token names: a number, or a loop variable expanded to each of its numeric words (None for a word that is not a number)."""
    tok = tok.strip("'\"").rstrip(");")
    if tok.isdigit(): return [int(tok)]
    v = re.fullmatch(r"\$\{?([A-Za-z_]\w*)\}?", tok)
    if v and v.group(1) in loops: return [int(w) if w and w.isdigit() else None for w in loops[v.group(1)]]
    return [None]

def merges_of(name, inp):
    """[(pr, repo)] for a tool call that merges pull requests, one entry per PR it names: a merge tool, or a Bash call whose shell segment
    starts with gh pr merge or gh api ... PUT .../pulls/<n>/merge (not inside a heredoc body or a quoted string, after do/then/( keywords).
    Several merge segments give several entries, and a merge inside `for n in 100 431; do …; done` gives one per number of the loop
    (a loop variable counts only until its done or a new assignment). pr is None when the call names no number it can read, or the repo
    is a variable; repo is None when the segment names none (record_main falls back to --repo). xargs and bash -c are not read."""
    inp = inp if isinstance(inp, dict) else {}
    if name.endswith("merge_pull_request"):
        n = inp.get("pullNumber")
        return [(int(n) if str(n).isdigit() else None, repo_of(name, inp))]
    if name != "Bash": return []
    out, loops, open_loops = [], {}, []
    for seg in shell_segments(strip_heredocs(str(inp.get("command", "")))):
        seg = seg[SHELL_KEYWORD.match(seg).end():]
        f = FOR_LOOP.match(seg)
        if f:
            loops[f.group(1)] = loop_words(f.group(2)); open_loops.append(f.group(1)); continue
        if re.match(r"done\b", seg.strip()):
            if open_loops: loops.pop(open_loops.pop(), None)
            continue
        a = re.match(r"\s*([A-Za-z_]\w*)=", seg)
        if a: loops.pop(a.group(1), None)
        seg = seg[ENV_PREFIX.match(seg).end():]
        r = repo_of("Bash", {"command": seg})
        if re.search(r"repos/(?:[^\s/]*\$|[^\s/]+/[^\s/]*\$)|(?:-R|--repo)[\s=]+\S*\$", seg): r = "$"  # a variable repo: one unchecked entry
        m = re.search(r"/pulls/" + PR_REF + r"/merge", seg)
        if re.match(r"gh\s+api\b", seg) and re.search(r"(?:-X\s*|--method[\s=]+)PUT\b", seg) and m:
            out += [(None, None)] if r and "$" in r else [(n, r) for n in pr_numbers(m.group(1), loops)]; continue
        m = re.match(r"gh\s+pr\s+merge\b(.*)", seg, re.S)
        if m:
            try: toks = shlex.split(m.group(1))
            except ValueError: toks = m.group(1).split()
            nums, skip = [None], False
            for tok in toks:
                if skip: skip = False; continue
                if tok in VALUE_FLAGS: skip = True; continue
                if tok.startswith("-"): continue
                u = re.search(r"/pull/" + PR_REF, tok)
                nums = pr_numbers(u.group(1) if u else tok, loops); break
            out += [(None, None)] if r and "$" in r else [(n, r) for n in nums]
    return out

MERGE_OK = re.compile(r'"merged":\s*true|successfully merged|merged pull request', re.I)

def merge_outcomes(entries, name, text, is_error):
    """Sets outcome on a call's merge entries from its one result. With several entries: gh pr merge's own line ("Merged pull request
    o/r#<n>", the number before any title) settles the last entry for that PR; a gh api PUT answer ("Pull Request successfully merged",
    which a GET of the PR never prints) is shared out to the remaining entries only when there is one for each, else they stay failed."""
    if len(entries) == 1:
        if MERGE_OK.search(text) or (name.endswith("merge_pull_request") and not is_error and "merged" in text.lower()): entries[0]["outcome"] = "merged"
        return
    named = {int(n) for n in re.findall(r"merged pull request\s+(?:[\w.-]+/[\w.-]+)?#(\d+)", text, re.I)}
    for n in named:
        last = [e for e in entries if e["pr"] == n][-1:]
        for e in last: e["outcome"] = "merged"
    rest = [e for e in entries if e["outcome"] != "merged"]
    if rest and len(re.findall(r"successfully merged", text, re.I)) >= len(rest):
        for e in rest: e["outcome"] = "merged"

def minutes(a, b):
    if not a or not b: return None
    f = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))
    return round((f(b) - f(a)).total_seconds() / 60, 1)

def family(model):
    """The model family of an id (claude-opus-5-5, us.anthropic.claude-sonnet-4-5-…-v1:0 → opus, sonnet); "other" for anything else, so keys stay bounded."""
    m = MODEL_FAMILY.search(model or "")
    return m.group(1) if m else "other"

def cost_state_counts_cache(cost_state):
    """True when the harness cost-state record carries cacheReadInputTokens for some model; a record without it (or with no models) is not a count."""
    return bool(cost_state) and any("cacheReadInputTokens" in x for x in cost_state["modelUsage"].values())

def cache_read_millions(cache_by_family, cost_state):
    """Cache-read tokens in millions by model family: the harness cost-state totals when they carry the field, else the transcripts' per-request usage."""
    out = collections.defaultdict(int)
    if cost_state_counts_cache(cost_state):
        for mdl, x in cost_state["modelUsage"].items(): out[family(mdl)] += x.get("cacheReadInputTokens") or 0
    else:
        out.update(cache_by_family)
    return {k: round(v / 1e6, 1) for k, v in sorted(out.items(), key=lambda kv: -kv[1])}

ASK_TOOLS = ("AskUserQuestion", "ask_user_input_v0")  # Code's and chat's tap question

def repo_of(name, inp):
    """owner/repo a PR call names (repos/<o>/<r>/pulls, a pull URL, -R/--repo, a tool's owner and repo arguments), else None."""
    inp = inp if isinstance(inp, dict) else {}
    if inp.get("owner") and inp.get("repo"): return f"{inp['owner']}/{inp['repo']}"
    cmd = str(inp.get("command", ""))
    m = re.search(r"repos/([\w.-]+/[\w.-]+)/pulls\b", cmd) or re.search(r"github\.com/([\w.-]+/[\w.-]+)/pull/\d+", cmd) \
        or re.search(r"(?:-R|--repo)[\s=]+([\w.-]+/[\w.-]+)", cmd)
    return m.group(1) if m else None

def creates_pr(name, inp):
    """True for a tool call that opens a pull request: gh pr create, gh api POST repos/<o>/<r>/pulls, a create_pull_request tool."""
    if name.endswith("create_pull_request"): return True
    if name != "Bash": return False
    for seg in shell_segments(strip_heredocs(str((inp or {}).get("command", "")))):
        seg = seg[ENV_PREFIX.match(seg).end():]
        if re.match(r"gh\s+pr\s+create\b", seg): return True
        if re.match(r"gh\s+api\b", seg) and re.search(r"repos/[\w.-]+/[\w.-]+/pulls(?=[\s'\"?]|$)", seg) \
           and not re.search(r"(?:-X\s*|--method[\s=]+)(GET|PATCH|PUT|DELETE)\b", seg) and re.search(r"(?:^|\s)(?:-[fF]|--field|--raw-field|--input|-X\s*POST|--method[\s=]+POST)\b", seg):
            return True
    return False

PR_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)")

def scan_routing(path, agent):
    """One transcript's asks (main thread only), refusals and merge calls."""
    global CWD_PREFIX
    pending, ask_by_id, merge_by_id = {}, {}, {}
    asks, refusals, merges, tool_uses = [], [], [], []  # tool_uses: (record number, timestamp)
    create_by_id, created, cards = set(), [], []  # PRs this thread opened ("owner/repo#n"); adjudications filed
    with open(path) as fh: lines = fh.readlines()
    for n, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        try: o = json.loads(line)
        except Exception: continue
        if CWD_PREFIX is None and o.get("cwd"): CWD_PREFIX = o["cwd"]
        t, ts = o.get("type"), o.get("timestamp")
        c = (o.get("message") or {}).get("content")
        if not isinstance(c, list): continue
        for b in c:
            if not isinstance(b, dict): continue
            if t == "assistant" and b.get("type") == "tool_use":
                name, inp = b.get("name", "?"), b.get("input") or {}
                pending[b.get("id")] = (name, target_of(name, inp))
                if creates_pr(name, inp): create_by_id.add(b.get("id"))
                tool_uses.append((n, ts))
                if name.split("__")[-1] in ASK_TOOLS and agent == "main":
                    qs = [q for q in (inp.get("questions") if isinstance(inp, dict) else None) or [] if isinstance(q, dict)]
                    asks.append({"asked_at": ts, "answered_at": None, "next_tool_at": None, "wait_min": None, "gap_min": None, "questions": len(qs),
                                 "headers": [redact(str(q.get("header", "")))[:12] for q in qs], "_answered_n": None})
                    ask_by_id[b.get("id")] = asks[-1]
                found = merges_of(name, inp)
                if found:
                    entries = [{"at": ts, "agent": agent, "tool": name, "call": b.get("id"), "pr": pr, "repo": r, "outcome": "failed", "result_at": None} for pr, r in found]
                    merges += entries; merge_by_id[b.get("id")] = entries
            elif t == "user" and b.get("type") == "tool_result":
                tid = b.get("tool_use_id"); name, target = pending.get(tid, ("?", ""))
                text = result_text(b.get("content")); ref = refusal_of(text, bool(b.get("is_error")))
                if ref: refusals.append({"at": ts, "agent": agent, "tool": name, "target": target, "kind": ref[0], "reason": ref[1]})
                if tid in create_by_id and not ref and not b.get("is_error"):
                    created += [f"{o}#{n}" for o, n in PR_URL.findall(text)[:1]]
                if name.endswith("grove_create_adjudication") and not ref and not b.get("is_error"): cards.append(tid)
                a = ask_by_id.get(tid)
                if a and a["answered_at"] is None: a["answered_at"], a["_answered_n"] = ts, n
                entries = merge_by_id.get(tid)
                if entries:
                    for e in entries:
                        e["result_at"] = ts
                        if ref: e["outcome"] = "refused"
                    if not ref: merge_outcomes(entries, name, text, bool(b.get("is_error")))
    for a in asks:
        if a["_answered_n"] is not None:
            a["next_tool_at"] = next((ts for n, ts in tool_uses if n > a["_answered_n"]), None)
        a["wait_min"], a["gap_min"] = minutes(a["asked_at"], a["answered_at"]), minutes(a["asked_at"], a["next_tool_at"])
        del a["_answered_n"]
    return asks, refusals, merges, created, cards

def routing_section(paths):
    """The routing section from transcript files: paths = [(agent id, path)], the main thread ("main") first."""
    asks, refusals, merges, created, cards = [], [], [], [], []
    for agent, path in paths:
        a, r, m, c, k = scan_routing(path, agent)
        asks += a; refusals += r; merges += m; created += c; cards += k
    return {"source": "transcript", "asks": len(asks), "refusals": len(refusals), "merges": len(merges),
            "ask_list": asks, "refusal_list": refusals, "merge_list": merges, "prs_opened": sorted(set(created)), "cards_filed": len(cards)}

def routing_md_line(r):
    plural = lambda n, w: f"{n} {w}" if n == 1 else f"{n} {w}s"
    tally = lambda key, order, items: ", ".join(f"{v} {sum(1 for i in items if i[key] == v)}" for v in order if any(i[key] == v for i in items))
    asks = plural(r["asks"], "ask")
    waits = [a["wait_min"] for a in r["ask_list"] if a["wait_min"] is not None]; gaps = [a["gap_min"] for a in r["ask_list"] if a["gap_min"] is not None]
    detail = ([f"waits {sum(waits):.1f} min"] if waits else []) + ([f"next tool call {sum(gaps):.1f} min after asking"] if gaps else [])
    if detail: asks += f" ({'; '.join(detail)})"
    refs = plural(r["refusals"], "refusal") + (f" ({tally('kind', KIND_ORDER, r['refusal_list'])})" if r["refusals"] else "")
    mgs = plural(r["merges"], "merge") + (f" ({tally('outcome', OUTCOME_ORDER, r['merge_list'])})" if r["merges"] else "")
    return f"Routing: {asks}, {refs}, {mgs}."

def transcript_paths(prefix):
    paths = [("main", prefix + ".jsonl")]
    sub_dir = prefix + "/subagents"
    if os.path.isdir(sub_dir):
        paths += [(f[len("agent-"):-len(".jsonl")], os.path.join(sub_dir, f)) for f in sorted(os.listdir(sub_dir)) if f.endswith(".jsonl")]
    return paths

def main(prefix, out_json, out_md, routing=False, sections=()):
    # ---- main thread
    main_run, events, hourly, writes, cps, compactions, main_models, cache_by_family = parse(prefix + ".jsonl", "main", "main thread", None)
    runs = [main_run]
    main_compactions = compactions
    agent_events = []
    sub_dir = prefix + "/subagents"
    if os.path.isdir(sub_dir):
        for f in sorted(os.listdir(sub_dir)):
            if not f.endswith(".jsonl"): continue
            aid = f[len("agent-"):-len(".jsonl")]
            meta = {}
            mp = os.path.join(sub_dir, f"agent-{aid}.meta.json")
            if os.path.exists(mp):
                try: meta = json.load(open(mp))
                except Exception: meta = {}
            label = redact(" ".join(str(meta.get("description") or "").split()))[:100] or None
            r, ev, hr, wr, cp, comp, mods, cbf = parse(os.path.join(sub_dir, f), aid, label, meta.get("model"))
            cache_by_family.update(cbf)
            if not r["label"] and label is None: r["label"] = "(no prompt found)"
            r["spawn_depth"] = meta.get("spawnDepth")
            r["agent_type"] = meta.get("agentType")
            runs.append(r); agent_events.extend(ev); writes.extend(wr); cps.extend(cp)
            compactions += comp
    all_events = events + agent_events

    # ---- totals by model (from runs; a run's requests are all on its model)
    by_model = collections.defaultdict(lambda: {"input": 0, "output_tokens_recorded": 0, "output_chars": 0, "cache_read": 0, "cache_write": 0, "requests": 0, "runs": 0})
    for r in runs:
        bm = by_model[r["model"] or "unknown"]
        for k in ("input", "output_tokens_recorded", "output_chars", "cache_read", "cache_write", "requests"): bm[k] += r[k]
        bm["runs"] += 1
    starts = [r["start"] for r in runs if r["start"]]; ends = [r["end"] for r in runs if r["end"]]
    span = {"start": min(starts), "end": max(ends)}
    d0 = datetime.datetime.fromisoformat(span["start"].replace("Z", "+00:00")); d1 = datetime.datetime.fromisoformat(span["end"].replace("Z", "+00:00"))
    span["hours"] = round((d1 - d0).total_seconds() / 3600, 2)

    # ---- per tool
    per_tool = collections.defaultdict(lambda: {"calls": 0, "input_size": 0, "result_size": 0})
    for e in all_events:
        pt = per_tool[e["tool"]]; pt["calls"] += 1; pt["input_size"] += e["input_size"]; pt["result_size"] += e["result_size"]
    per_tool = dict(sorted(per_tool.items(), key=lambda kv: -kv[1]["result_size"]))

    largest = sorted(all_events, key=lambda e: -e["result_size"])[:20]
    largest = [{"tool": e["tool"], "target": e["target"], "size": e["result_size"], "agent": e["agent"]} for e in largest]

    # ---- writes by pattern
    by_pat = collections.defaultdict(lambda: {"bytes": 0, "writes": 0, "edits": 0, "files": set()})
    for pat, path, n, tool in writes:
        bp = by_pat[pat]; bp["bytes"] += n; bp["files"].add(path); bp["writes" if tool == "Write" else "edits"] += 1
    by_pat = {k: {"bytes": v["bytes"], "writes": v["writes"], "edits": v["edits"], "files": len(v["files"])} for k, v in sorted(by_pat.items(), key=lambda kv: -kv[1]["bytes"])}
    # files created by a copy command whose destination or source is under COPY_WATCH
    copied = collections.Counter(); copied_cmds = 0
    for c in cps if COPY_WATCH else []:
        args = c["args"]
        if len(args) < 2: continue
        dest = args[-1]
        if COPY_WATCH in dest or any(COPY_WATCH in a for a in args[:-1]):
            copied_cmds += 1
            if dest.endswith("/") or "." not in dest.rsplit("/", 1)[-1]:
                for s in args[:-1]: copied[dest.rstrip("/") + "/" + s.rsplit("/", 1)[-1]] += 1
            else: copied[dest] += 1

    # ---- hourly (main thread only)
    hourly_rows = [dict(hour=h, **v) for h, v in sorted(hourly.items()) if h]

    cost_state = None
    try:
        for line in open(prefix + ".jsonl"):
            if '"cost-state"' in line:
                o = json.loads(line)
                if o.get("type") == "cost-state":
                    cost_state = {"totalCostUSD": round(o.get("totalCostUSD", 0), 2), "totalLinesAdded": o.get("totalLinesAdded"), "totalLinesRemoved": o.get("totalLinesRemoved"),
                                  "modelUsage": {m: {k: v for k, v in x.items() if k != "costUSD"} for m, x in (o.get("modelUsage") or {}).items()}}
    except Exception: pass

    if cost_state:
        for mdl, x in cost_state["modelUsage"].items():
            by_model[mdl]["harness"] = {"input": x.get("inputTokens"), "output": x.get("outputTokens"), "thinking": x.get("thinkingTokens"), "cache_read": x.get("cacheReadInputTokens"), "cache_write": x.get("cacheCreationInputTokens")}
    by_model = dict(by_model)
    report = {
        "session": os.path.basename(prefix), "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "transcript usage counted once per API requestId; sub-agent transcripts record only the first streamed usage chunk, so output_tokens_recorded undercounts them (output_chars = characters of text, thinking and tool inputs is the proxy); the harness cost-state record gives authoritative per-model totals; sizes are character counts; labels redacted",
        "span": span, "compactions": {"main_thread": main_compactions, "sub_agents": compactions - main_compactions, "total": compactions}, "totals_by_model": by_model,
        "runs": sorted(runs, key=lambda r: r["start"] or ""), "main_thread_by_hour": hourly_rows,
        "per_tool": per_tool, "largest_tool_results": largest,
        "writes_by_pattern": by_pat,
        "harness_cost_state_cross_check": cost_state,
        "cache_read_m": cache_read_millions(cache_by_family, cost_state),
    }
    if COPY_WATCH:
        report["copy_commands_into"] = {"watch": COPY_WATCH, "commands": copied_cmds, "files": len(copied), "paths": sorted(copied)}
    extra_lines = []
    for section in sections:
        key, value, line = section(report)
        report[key] = value; extra_lines.append(line)
    if routing:
        report["routing"] = routing_section(transcript_paths(prefix))
    json.dump(report, open(out_json, "w"), indent=1)

    def k(n): return f"{n/1000:,.0f}k" if n >= 1000 else str(n)
    L = []
    L.append(f"# Session usage {report['session'][:8]}: {span['start'][:16]}Z to {span['end'][:16]}Z ({span['hours']} h), {main_compactions} main-thread compactions ({compactions - main_compactions} in sub-agents), {len(runs)-1} sub-agent runs")
    L.append("")
    L.append("| Model | Requests | Input | Output (harness) | Thinking (harness) | Cache read | Cache write | Output chars (transcript) |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for mdl, v in sorted(by_model.items(), key=lambda kv: -kv[1]["cache_read"]):
        h = v.get("harness") or {}
        L.append(f"| {mdl} | {v['requests']} | {k(h.get('input') or v['input'])} | {k(h.get('output') or 0)} | {k(h.get('thinking') or 0)} | {k(h.get('cache_read') or v['cache_read'])} | {k(h.get('cache_write') or v['cache_write'])} | {k(v['output_chars'])} |")
    L.append("")
    L.append("Top runs by cache read (full table in the JSON):")
    L.append("")
    L.append("| Run | Model | Start | Req | Out chars | Cache read | Tools | Written |")
    L.append("|---|---|---|---:|---:|---:|---:|---:|")
    for r in sorted(runs, key=lambda r: -r["cache_read"])[:8]:
        L.append(f"| {r['label'][:60]} | {(r['model'] or '?').replace('claude-','')} | {(r['start'] or '')[5:16]} | {r['requests']} | {k(r['output_chars'])} | {k(r['cache_read'])} | {r['tool_calls']} | {k(r['write_edit_bytes'])} |")
    L.append("")
    tt = sorted(per_tool.items(), key=lambda kv: -kv[1]["result_size"])[:6]
    L.append("Tools by result size: " + "; ".join(f"{t} {v['calls']} calls, {k(v['result_size'])} chars" for t, v in tt))
    L.append("")
    L.append("Largest tool results: " + "; ".join(f"{e['tool']} {k(e['size'])} ({e['target'][:40]})" for e in largest[:5]))
    L.append("")
    wp = list(by_pat.items())[:6]
    L.append("Writes by pattern: " + "; ".join(f"{p} {k(v['bytes'])} in {v['files']} files" for p, v in wp))
    if COPY_WATCH: L.append(f"Files under {COPY_WATCH} created by copy commands instead: {len(copied)} ({copied_cmds} commands).")
    L.append("")
    busiest = sorted(hourly_rows, key=lambda h: -h["cache_read"])[:5]
    L.append("Main thread busiest hours (cache read / tool calls): " + "; ".join(f"{h['hour'][5:13]} {k(h['cache_read'])} / {h['tool_calls']}" for h in busiest))
    if cost_state:
        L.append(f"Harness cross-check: {sum(v.get('outputTokens',0) for v in cost_state['modelUsage'].values()):,} output tokens over all models, {cost_state['totalLinesAdded']} lines added; sub-agent transcripts record only the first usage chunk, so per-run output is given as characters.")
    L.append("Cache read, millions by model: " + (", ".join(f"{m} {v}" for m, v in report["cache_read_m"].items()) or "none") + ("" if cost_state_counts_cache(cost_state) else " (from the transcripts; no harness cost-state record with cache-read counts)") + ".")
    L.extend(extra_lines)
    if "routing" in report:
        L.append(routing_md_line(report["routing"]))
    open(out_md, "w").write("\n".join(L) + "\n")
    print(f"runs {len(runs)} events {len(all_events)} compactions {compactions} md_lines {len(L)}")
    if routing:
        r = report["routing"]
        print(json.dumps({"asks": r["asks"], "refusals": r["refusals"], "merges": r["merges"], "source": r["source"], "cache_read_m": report["cache_read_m"]}))
    return report

# ---------------------------------------------------------------- the whole session record (--record)
# Architecture run 75cbc21d, build item 1 (docs/architecture-run/04-PROPOSAL.md §8): every session record
# carries the transcript's counts, cache_read_m, the start, and how each landed PR merged; the record is
# built here in one call and exits 2 rather than print a partial or inconsistent record.

RECORD_VERSION = 2
VIAS = ("self", "ask", "github", "pending", "open")
# self: the session merged ruled upkeep, no tap; ask: the session merged under his answer; github: he merged it himself;
# pending: ready, waiting for his tap; open: a draft the work continues on (no tap yet)
TAPPED = ("ask", "github", "pending")
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)
GO_SENTENCE = re.compile(r"(?:^|\blane [a-z]:\s*)Go:", re.I | re.M)  # close-at-land's Next-step Go, alone on a line or after "lane X:"
# session-start references/dispatch.md Step 3: "Work on MBN, lane D: …" and the other-repo form "Work on fairbay/ops for MBN lane H: …"
# (the comma form alone read every lane H opening as typed: docs/dispatch/DESIGN.md §9 finding 1)
DISPATCH_PROMPT = re.compile(r"^\s*work on [^\n]*?\blane [a-z][a-z0-9]*\b", re.I)
LANE_ID = re.compile(r"[a-z][a-z0-9]*")
DISPATCH_STATES = ("ready", "prompted", "step", "call", "waiting", "running")
DISPATCH_LISTS = ("steps", "calls", "waiting", "running", "cleanup")
def parse_utc(s):
    """An ISO-8601 UTC time with a trailing Z (2026-11-05T00:55Z or with seconds), or None."""
    if not isinstance(s, str): return None
    for fmt in ("%Y-%m-%dT%H:%MZ", "%Y-%m-%dT%H:%M:%SZ"):
        try: return datetime.datetime.strptime(s, fmt).replace(tzinfo=datetime.timezone.utc)
        except ValueError: pass
    return None

def text_hash(text):
    """Eight hex characters of the text with white space collapsed: a printed prompt and a session's opening message
    hash the same when he pasted it unchanged (docs/dispatch/DESIGN.md §4.3)."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()[:8]

def parse_dispatch(path, lanes):
    """The dispatch block of a dispatch record (session-start references/dispatch.md Step 4): what the run printed, checked
    for shape so the next run can reprint a prompt verbatim and tell a prompted lane from a ready one. Refuses (RecordError)
    rather than storing a block the next run cannot read."""
    try:
        with open(path) as fh: d = json.load(fh)
    except (OSError, ValueError) as e:
        raise RecordError(f"--dispatch {path}: {e}")
    if not isinstance(d, dict): raise RecordError("--dispatch: want a JSON object")
    extra = sorted(set(d) - {"lanes", "prompts", *DISPATCH_LISTS})
    if extra: raise RecordError(f"--dispatch: unknown keys {extra}")
    if not lanes: raise RecordError("--dispatch needs --lanes <the declared lanes, comma-separated> (landing.yaml), so the block names each once")
    states = d.get("lanes")
    if not isinstance(states, dict) or not states: raise RecordError("--dispatch: lanes must be an object lane -> state")
    for lane, state in states.items():
        if not LANE_ID.fullmatch(lane): raise RecordError(f"--dispatch: {lane!r} is not a lane id (lower case: a, a2)")
        if state not in DISPATCH_STATES: raise RecordError(f"--dispatch: lane {lane} state {state!r} is not one of {', '.join(DISPATCH_STATES)}")
    want = {x.lower() for x in lanes}
    if set(states) != want: raise RecordError(f"--dispatch: lanes must name every declared lane once: want {sorted(want)}, got {sorted(states)}")
    prompts = d.get("prompts", {})
    if not isinstance(prompts, dict): raise RecordError("--dispatch: prompts must be an object lane -> {text, first, since, offered}")
    out_prompts = {}
    for lane, p in prompts.items():
        if lane not in states or states[lane] not in ("ready", "prompted"):
            raise RecordError(f"--dispatch: prompts names lane {lane!r}, which is not a ready or prompted lane")
        if not isinstance(p, dict): raise RecordError(f"--dispatch: prompt for lane {lane} must be an object")
        text = p.get("text")
        if not isinstance(text, str) or not text.strip(): raise RecordError(f"--dispatch: prompt for lane {lane} is empty")
        m = DISPATCH_PROMPT.match(text)
        if not (m or GO_SENTENCE.search(text)):
            raise RecordError(f"--dispatch: prompt for lane {lane} is not in the template (Work on …, lane X: …) or a Go sentence")
        named = re.search(r"\blane ([a-z][a-z0-9]*)\b", text, re.I)
        if named and named.group(1).lower() != lane:
            raise RecordError(f"--dispatch: prompt for lane {lane} names lane {named.group(1)}")
        first, since = p.get("first"), p.get("since", p.get("first"))
        if parse_utc(first) is None: raise RecordError(f"--dispatch: prompt for lane {lane} needs first as UTC with a Z (2026-11-05T00:55Z)")
        if parse_utc(since) is None: raise RecordError(f"--dispatch: prompt for lane {lane} needs since as UTC with a Z")
        if parse_utc(since) > parse_utc(first): raise RecordError(f"--dispatch: prompt for lane {lane} has since after first")
        offered = p.get("offered", 1)
        if not isinstance(offered, int) or isinstance(offered, bool) or offered < 1: raise RecordError(f"--dispatch: prompt for lane {lane} needs offered as an integer of 1 or more")
        out_prompts[lane] = {"text": text, "first": first, "since": since, "offered": offered, "hash": text_hash(text)}
    for lane, state in states.items():
        if state in ("ready", "prompted") and lane not in out_prompts:
            raise RecordError(f"--dispatch: lane {lane} is {state} but prompts carries no prompt for it")
    out = {"lanes": states, "prompts": out_prompts}
    # which states a list may name (session-start references/dispatch.md Step 4): a step or call inside a Start entry
    # names a ready lane; waiting names waiting lanes; running names running and prompted lanes
    allowed = {"steps": ("step", "ready"), "calls": ("call", "ready"), "waiting": ("waiting",), "running": ("running", "prompted")}
    for k in DISPATCH_LISTS:
        v = d.get(k, [])
        if not isinstance(v, list): raise RecordError(f"--dispatch: {k} must be a list")
        items = []
        for x in v:
            if k == "cleanup":
                if not isinstance(x, str) or not x.strip(): raise RecordError(f"--dispatch: {k} items are non-empty strings")
                items.append(x); continue
            if not isinstance(x, dict) or not isinstance(x.get("text"), str) or not x["text"].strip():
                raise RecordError(f"--dispatch: {k} items are objects {{lane, text}} with a non-empty text")
            lane = x.get("lane")
            if lane is not None and (not isinstance(lane, str) or lane not in states):
                raise RecordError(f"--dispatch: {k} item names lane {lane!r}, which is not in lanes")
            if lane is not None and states[lane] not in allowed[k]:
                raise RecordError(f"--dispatch: {k} item names lane {lane}, whose state is {states[lane]} (want {' or '.join(allowed[k])})")
            items.append({"lane": lane, "text": x["text"]})
        out[k] = items
    listed = {x["lane"] for k in ("waiting", "running") for x in out[k] if x["lane"]}
    for lane, state in states.items():
        if state in ("waiting", "running", "prompted") and lane not in listed:
            raise RecordError(f"--dispatch: lane {lane} is {state} but no waiting or running line names it")
    return out
CONTINUED = re.compile(r"^This session is being continued from a previous conversation")

class RecordError(Exception):
    pass

def opening_text(path):
    """The first message a human wrote in the main thread (system-reminder blocks removed), or None when there is none.
    Meta records, sidechains, tool results and compaction summaries are not his."""
    with open(path) as fh:
        for line in fh:
            try: o = json.loads(line)
            except Exception: continue
            if o.get("type") != "user" or o.get("isMeta") or o.get("isSidechain") or o.get("isCompactSummary"): continue
            c = (o.get("message") or {}).get("content")
            if isinstance(c, str): parts = [c]
            elif isinstance(c, list):
                if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c): continue
                parts = [b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text"]
            else: continue
            text = SYSTEM_REMINDER.sub("", "\n".join(parts)).strip()
            if text and not CONTINUED.match(text): return text
    return None

def start_of(text):
    """How the session started: "pasted" (a printed prompt: a Go sentence or a dispatch prompt), "typed" (anything else he wrote),
    "none" (no human opening message). Only positive evidence makes "pasted"; the length rides beside it as opening_chars."""
    if not text: return "none"
    return "pasted" if GO_SENTENCE.search(text) or DISPATCH_PROMPT.match(text) else "typed"

def ids(spec):
    return [s.strip() for s in (spec or "").split(",") if s.strip()]

def parse_prs(spec, repo):
    """'105:self,fairbay/medicaid-benefits-navigator#431:ask' -> [{"pr": "fairbay/ops#105", "repo": …, "n": 105, "via": "self"}, …]."""
    out = []
    for item in ids(spec):
        m = re.fullmatch(r"(?:([\w.-]+/[\w.-]+)#)?(\d+):(\w+)", item)
        if not m or m.group(3) not in VIAS:
            raise RecordError(f"--prs item {item!r}: want [owner/repo#]<n>:<{'|'.join(VIAS)}>")
        r = m.group(1) or repo
        if not r: raise RecordError(f"--prs item {item!r} names no repo and --repo is null")
        out.append({"pr": f"{r}#{m.group(2)}", "repo": r, "n": int(m.group(2)), "via": m.group(3)})
    seen = [x["pr"] for x in out]
    dup = sorted({p for p in seen if seen.count(p) > 1})
    if dup: raise RecordError(f"--prs lists {', '.join(dup)} twice")
    return out

def merge_key(m, repo):
    """owner/repo#n of a merge call; the repo read from the call, else --repo; None when the call names no number."""
    if m["pr"] is None: return None
    r = m.get("repo") or repo
    return f"{r}#{m['pr']}" if r else f"?#{m['pr']}"

def check_prs(prs, routing, repo, not_merged):
    """The transcript decides what it can: every merge call that did not merge is explained, every PR merged here is named
    self or ask, every PR opened here is named, and no PR named self or ask lacks a merge here."""
    named = {x["pr"]: x for x in prs}
    errs, unchecked = [], 0
    merged = {merge_key(m, repo) for m in routing["merge_list"] if m["outcome"] == "merged"} - {None}  # a failed attempt retried to a merge needs no note
    for m in routing["merge_list"]:
        k = merge_key(m, repo)
        if m["outcome"] == "refused": continue
        if k is None:
            unchecked += 1; continue
        if m["outcome"] == "merged" or k in merged: continue
        if k not in not_merged and not (k in named and named[k]["via"] in ("self", "ask")):
            errs.append(f"merge call on {k} shows no merge in its result: name it in --prs (self or ask) if it merged, else --not-merged {k}")
    for k in sorted(merged - set(named)): errs.append(f"{k} was merged by this session but is not in --prs (as self or ask)")
    for k in routing.get("prs_opened", []):
        if k not in named: errs.append(f"{k} was opened by this session but is not in --prs (open, pending, github, self or ask)")
    for x in prs:
        if x["via"] in ("self", "ask") and x["pr"] not in merged and not any(merge_key(m, repo) == x["pr"] for m in routing["merge_list"] if m["outcome"] == "failed"):
            errs.append(f"{x['pr']}:{x['via']} has no merge call in this session (he merged it: github; waiting: pending; a draft: open)")
        if x["via"] in ("github", "pending", "open") and x["pr"] in merged:
            errs.append(f"{x['pr']}:{x['via']} was merged by this session: self or ask")
    if errs: raise RecordError("; ".join(errs))
    return unchecked

def interrupts_of(rec, routing):
    """Baylee's interrupts: asks + refusals that were not of a merge call (a refused merge's cost is his tap, counted on its PR) +
    PRs he merged or has yet to merge + cards + a pasted start. A merge under his answer is inside the ask; ruled upkeep costs nothing."""
    merge_refusals = len({(m["agent"], m.get("call", m["at"])) for m in routing["merge_list"] if m["outcome"] == "refused"})  # calls, not PRs: a refused loop is one refusal
    taps = sum(1 for x in rec["prs"] if x["via"] in ("github", "pending"))
    return rec["asks"] + rec["refusals"] - merge_refusals + taps + len(rec["cards"]) + (1 if rec["start"] == "pasted" else 0)

def newest_prefix(root=None):
    """The newest main-thread transcript under ~/.claude/projects (this session's own in a cloud container), without .jsonl."""
    root = root or os.path.expanduser("~/.claude/projects")
    files = [os.path.join(d, f) for d in (os.path.join(root, x) for x in (os.listdir(root) if os.path.isdir(root) else []))
             if os.path.isdir(d) for f in os.listdir(d) if f.endswith(".jsonl")]
    if not files: raise RecordError(f"no transcript under {root}: count by hand (record 1, source self-reported)")
    return max(files, key=os.path.getmtime)[:-len(".jsonl")]

def build_record(a, prefix, scratch):
    """The whole record from the transcript at prefix and the session's own fields (argparse namespace a)."""
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        report = main(prefix, os.path.join(scratch, "report.json"), os.path.join(scratch, "report.md"), routing=True)
    r = report["routing"]
    repo = None if a.repo in (None, "", "null") else a.repo
    prs = parse_prs(a.prs, repo)
    unchecked = check_prs(prs, r, repo, set(parse_not_merged(a.not_merged, repo)))
    asks = r["asks"] + a.asks_prose
    if any(x["via"] == "ask" for x in prs) and asks == 0:
        raise RecordError("a PR merged under his answer (ask) but the session counts no ask: add --asks-prose for a question put in prose")
    cards = ids(a.cards)
    if len(cards) < r["cards_filed"]:
        raise RecordError(f"the transcript shows {r['cards_filed']} adjudication cards filed; --cards names {len(cards)}")
    opening = opening_text(prefix + ".jsonl")
    rec = {"record": RECORD_VERSION, "session": a.session, "surface": a.surface,
           "date": datetime.datetime.now(datetime.timezone.utc).date().isoformat(), "repo": repo, "kind": a.kind,
           "asks": asks, "refusals": r["refusals"], "refused": [x["target"] for x in r["refusal_list"]], "merges": r["merges"],
           "prs": [{"pr": x["pr"], "via": x["via"], "tapped": x["via"] in TAPPED} for x in prs],
           "start": "none" if a.surface == "routine" else start_of(opening), "opening_chars": len(opening or ""),  # a routine's prompt is not his
           "calls_logged": ids(a.calls), "calls_shown": ids(a.shown), "cards": cards, "tasks_for_baylee": ids(a.tasks),
           "cache_read_m": report["cache_read_m"] or None, "source": "transcript",
           "opening_hash": text_hash(opening) if opening else None}  # matches a dispatch record's prompt hash when he pasted it unchanged
    if unchecked: rec["unchecked_merges"] = unchecked
    if a.lane: rec["lane"] = a.lane.lower()
    if a.dispatch:
        if a.lane: raise RecordError("a dispatch record takes no --lane (its tag is dispatch)")
        rec["dispatch"] = parse_dispatch(a.dispatch, ids(a.lanes))
    rec["interrupts"] = interrupts_of(rec, r)
    return rec

def parse_not_merged(spec, repo):
    out = []
    for item in ids(spec):
        m = re.fullmatch(r"(?:([\w.-]+/[\w.-]+)#)?(\d+)", item)
        if not m or not (m.group(1) or repo): raise RecordError(f"--not-merged item {item!r}: want [owner/repo#]<n>")
        out.append(f"{m.group(1) or repo}#{m.group(2)}")
    return out

def record_main(argv):
    import argparse, tempfile
    p = argparse.ArgumentParser(prog="session_report.py --record", description="Print the whole session record (one JSON line) for the Grove session-record decision.")
    p.add_argument("--record", action="store_true", required=True)
    p.add_argument("--prefix", default="auto", help="transcript prefix without .jsonl; auto = the newest under ~/.claude/projects")
    p.add_argument("--session", required=True, help="the session URL, as the handoff's meta.session")
    p.add_argument("--surface", required=True, choices=("chat", "code", "routine"))
    p.add_argument("--repo", required=True, help="fairbay/<repo>, or null")
    p.add_argument("--kind", required=True, help="upkeep, direction, or a change_batches kind")
    p.add_argument("--lane", help="the lane worked (lanes repos)")
    p.add_argument("--prs", default="", help="every PR this session opened, merged or left for his tap: [owner/repo#]<n>:<" + "|".join(VIAS) + ">, comma-separated")
    p.add_argument("--not-merged", default="", help="PRs whose merge call shows no merge and did not merge")
    p.add_argument("--asks-prose", type=int, default=0, help="questions put to Baylee in prose (the transcript counts the ask tools only)")
    for f in ("calls", "shown", "cards", "tasks"): p.add_argument("--" + f, default="")
    p.add_argument("--dispatch", help="a dispatch run: the JSON file of what it printed (session-start references/dispatch.md Step 4)")
    p.add_argument("--lanes", default="", help="with --dispatch: the declared lanes (landing.yaml), comma-separated; the block must name each once")
    a = p.parse_args(argv)
    try:
        prefix = newest_prefix() if a.prefix == "auto" else a.prefix
        if not os.path.isfile(prefix + ".jsonl"): raise RecordError(f"no transcript at {prefix}.jsonl")
        print(f"transcript: {prefix}.jsonl", file=sys.stderr)
        with tempfile.TemporaryDirectory() as scratch:
            rec = build_record(a, prefix, scratch)
    except RecordError as e:
        print(f"session_report.py --record: {e}", file=sys.stderr)
        return 2
    print(json.dumps(rec, separators=(",", ":")))
    return 0

# ---------------------------------------------------------------- the read-back (--check-record <decision id>)
# Ledger 6e5aa00e: records logged with a null or prose context are skipped by both weekly reads (4 of 30 in the
# week to 2026-11-03, one hiding 142.5M from S10). The archive's read-back runs this instead of checking by eye.

def check_record(decision, lane=None):
    """Problems that keep the weekly reads from counting this session-record decision (empty list = it counts)."""
    import ops_read
    tags = ops_read.tags_of(decision)
    problems = []
    if "session-record" not in tags:
        problems.append("no session-record tag")
    else:
        recs, bad = ops_read.parse_records([decision])
        problems += [u["reason"] for u in bad]
        if not recs and not bad:
            problems.append("superseded: the newer record is the one that counts")
    if lane and f"lane-{str(lane).lower()}" not in tags:
        problems.append(f"no lane-{str(lane).lower()} tag")
    return problems

def check_main(argv):
    """--check-record <decision id> [--lane x]: exit 0 when the weekly reads count the record, 2 with each problem when not."""
    import argparse
    p = argparse.ArgumentParser(prog="session_report.py --check-record")
    p.add_argument("--check-record", required=True, metavar="DECISION_ID")
    p.add_argument("--lane")
    a = p.parse_args(argv)
    from ops_gather import load_grove
    try:
        d = load_grove().get("decision", a.check_record)
    except Exception as e:  # noqa: BLE001 — a failed read is a failed check, never a pass
        print(f"session_report.py --check-record: cannot read {a.check_record}: {e}", file=sys.stderr)
        return 2
    problems = check_record(d, a.lane)
    for x in problems:
        print(f"session_report.py --check-record {a.check_record}: {x}", file=sys.stderr)
    if problems:
        if not all(x.startswith("superseded") for x in problems):
            print("log it again with supersedes=<this id> and the record JSON as context", file=sys.stderr)
        return 2
    print(f"record {a.check_record}: counted")
    return 0

USAGE = __doc__.split("\n")[2]

def parse_args(argv, opts=None, usage=USAGE):
    """<prefix> <out.json> <out.md> [--routing] plus a wrapper's own valued options (opts: {"--flag": default}); returns ((prefix, out_json, out_md), routing, opts).
    A wrapper passes its own usage line."""
    args, opts, routing = [], dict(opts or {}), False
    it = iter(argv)
    for a in it:
        if a in opts:
            opts[a] = next(it, None)
            if opts[a] is None: sys.exit(f"{a} needs a value\n{usage}")
        elif a == "--routing": routing = True
        else: args.append(a)
    if len(args) != 3: sys.exit(usage)
    return tuple(args), routing, opts

if __name__ == "__main__":
    if "--record" in sys.argv[1:]: sys.exit(record_main(sys.argv[1:]))
    if any(a == "--check-record" or a.startswith("--check-record=") for a in sys.argv[1:]): sys.exit(check_main(sys.argv[1:]))
    (prefix, out_json, out_md), routing, _ = parse_args(sys.argv[1:])
    main(prefix, out_json, out_md, routing)
