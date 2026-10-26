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
(classifier, safety check, rule, user rejection; main thread and sub-agents) and the pull-request merge calls with their outcome (merged,
refused, failed). It copies no question text and no answer; the only free text kept is the first 200 characters of a classifier's reason,
redacted like every other label. Without it the output is as before.

A repo wraps this script for its own extras (MBN scripts/session-usage/report.py; it puts the synced
.claude/skills/chat-archive/scripts on sys.path and imports the module): `session_report.PATH_PATTERNS.insert(0, …)` adds the repo's
path generalizations, `session_report.COPY_WATCH = "…"` (assigned on the module, not an imported name) names a path substring whose
copy-command destinations are counted, parse_args(argv, opts, usage) parses its own valued options, and main(..., sections=[...])
appends sections (each callable takes the report dict and returns (key, value, markdown line)) after the base report and before routing.
"""
import json, os, re, sys, collections, datetime

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

def merge_of(name, inp):
    """(is_merge, pr) for a tool call that merges a pull request. A Bash call counts only when gh pr merge or gh api ... PUT .../pulls/<n>/merge
    starts a shell command segment (not inside a heredoc body or a quoted string)."""
    inp = inp if isinstance(inp, dict) else {}
    if name.endswith("merge_pull_request"):
        n = inp.get("pullNumber")
        return True, int(n) if str(n).isdigit() else None
    if name != "Bash": return False, None
    for seg in shell_segments(strip_heredocs(str(inp.get("command", "")))):
        seg = seg[ENV_PREFIX.match(seg).end():]
        m = re.search(r"/pulls/(\d+)/merge", seg)
        if re.match(r"gh\s+api\b", seg) and re.search(r"(?:-X\s*|--method[\s=]+)PUT\b", seg) and m: return True, int(m.group(1))
        m = re.match(r"gh\s+pr\s+merge\b(.*)", seg, re.S)
        if m:
            for tok in m.group(1).split():
                if tok.startswith("-"): continue
                n = re.fullmatch(r"\d+", tok) or re.search(r"/pull/(\d+)", tok)
                return True, int(n.group(n.lastindex or 0)) if n else None
            return True, None
    return False, None

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

def scan_routing(path, agent):
    """One transcript's asks (main thread only), refusals and merge calls."""
    global CWD_PREFIX
    pending, ask_by_id, merge_by_id = {}, {}, {}
    asks, refusals, merges, tool_uses = [], [], [], []  # tool_uses: (record number, timestamp)
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
                tool_uses.append((n, ts))
                if name == "AskUserQuestion" and agent == "main":
                    qs = [q for q in (inp.get("questions") if isinstance(inp, dict) else None) or [] if isinstance(q, dict)]
                    asks.append({"asked_at": ts, "answered_at": None, "next_tool_at": None, "wait_min": None, "gap_min": None, "questions": len(qs),
                                 "headers": [redact(str(q.get("header", "")))[:12] for q in qs], "_answered_n": None})
                    ask_by_id[b.get("id")] = asks[-1]
                is_merge, pr = merge_of(name, inp)
                if is_merge:
                    merges.append({"at": ts, "agent": agent, "tool": name, "pr": pr, "outcome": "failed", "result_at": None})
                    merge_by_id[b.get("id")] = merges[-1]
            elif t == "user" and b.get("type") == "tool_result":
                tid = b.get("tool_use_id"); name, target = pending.get(tid, ("?", ""))
                text = result_text(b.get("content")); ref = refusal_of(text, bool(b.get("is_error")))
                if ref: refusals.append({"at": ts, "agent": agent, "tool": name, "target": target, "kind": ref[0], "reason": ref[1]})
                a = ask_by_id.get(tid)
                if a and a["answered_at"] is None: a["answered_at"], a["_answered_n"] = ts, n
                mg = merge_by_id.get(tid)
                if mg:
                    mg["result_at"] = ts
                    if ref: mg["outcome"] = "refused"
                    elif re.search(r'"merged":\s*true|successfully merged|merged pull request', text, re.I) or (name.endswith("merge_pull_request") and not b.get("is_error") and "merged" in text.lower()):
                        mg["outcome"] = "merged"
    for a in asks:
        if a["_answered_n"] is not None:
            a["next_tool_at"] = next((ts for n, ts in tool_uses if n > a["_answered_n"]), None)
        a["wait_min"], a["gap_min"] = minutes(a["asked_at"], a["answered_at"]), minutes(a["asked_at"], a["next_tool_at"])
        del a["_answered_n"]
    return asks, refusals, merges

def routing_section(paths):
    """The routing section from transcript files: paths = [(agent id, path)], the main thread ("main") first."""
    asks, refusals, merges = [], [], []
    for agent, path in paths:
        a, r, m = scan_routing(path, agent)
        asks += a; refusals += r; merges += m
    return {"source": "transcript", "asks": len(asks), "refusals": len(refusals), "merges": len(merges),
            "ask_list": asks, "refusal_list": refusals, "merge_list": merges}

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
    (prefix, out_json, out_md), routing, _ = parse_args(sys.argv[1:])
    main(prefix, out_json, out_md, routing)
