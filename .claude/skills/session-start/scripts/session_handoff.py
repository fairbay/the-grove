"""
session_handoff.py — cross-surface session-continuity helper.

Synced into every repo with the session-start skill. The SessionStart hook entry
that runs it is managed by fairbay/ops (docs/hook-delivery/DESIGN.md).

Commands:

    inject   The ENTRY gate (SessionStart hook). Emits one JSON payload
             (hookSpecificOutput.additionalContext), shaped by the hook input's
             `source`:
               startup / clear / fork / none: header, notes, the open-PR gate table
                 (pr_state.py report --table, at most 15 rows), and HANDOFF.yaml's
                 meta, next and carried_forward;
               compact / resume: notes and next + carried_forward, no network.
             Every source also gets the decision table from .claude/policy.json
             (fairbay/ops docs/decision-routing/DESIGN.md §2), placed under the
             handoff; its room is reserved first, so the handoff is what gets cut.
             The whole payload stays under Claude Code's 10,000-character cap,
             measured on the serialized JSON. It never blocks: a failure becomes
             a note line ("PR gate unavailable", "Entry gate error", ...) and the
             command exits 0. It also makes sure the capture queue is git-ignored
             (chat-archive's capture_corrections.ensure_excluded).

    measure  Signal S8 (DESIGN.md §4): composes the startup payload with a
             synthetic worst-case PR table (PR_TABLE_ROWS rows) and the repo's own
             HANDOFF.yaml and policy.json, and prints one JSON line: payload size,
             the sections and characters cut. Exit 1 when anything is cut, else 0.
             policy-check.mjs runs it; the archive's handoff write runs it too.

    write    EXIT-gate helper. Reads a handoff body as JSON on stdin, stamps
             meta.surface / meta.generated / meta.project, carries unfinished
             `next:` items forward (a parked item counts as accounted for; a body
             without `parked:` keeps the prior list), and writes <repo>/HANDOFF.yaml.
             Exit 1 after writing when `measure` fails: the S8 backstop. Session state
             lives in Grove; there is no session-handoff path any more.
             `write --lane x` (lanes repos): writes handoffs/lane-x.yaml instead, and a
             body's `progress_line` replaces only the `  x:` line of HANDOFF.yaml's
             `progress:`. A plain `write` where lanes are declared refuses (exit 2).

    lane     The LANE gate (UserPromptSubmit hook, fairbay-managed:lane-gate). Where
             .claude/landing.yaml declares `lanes:`, a prompt of Baylee's that names a
             declared lane ("lane A", "lane A2", "lane-c") gets that lane's baton
             (handoffs/lane-<x>.yaml: meta, next, carried_forward) as additionalContext,
             once per session per lane (state: <git dir>/fairbay-lanes.json). Otherwise
             it prints nothing. Design: fairbay/ops docs/lanes/DESIGN.md.

Lanes (docs/lanes/DESIGN.md): with `lanes:` declared, HANDOFF.yaml holds only `meta`
and `progress` (one key per lane, a blank line between keys) and `inject` adds a lane
index (each lane's first `next:` item); compact/resume re-inject the lanes loaded this
session; `measure` checks the startup payload and every lane file's payload.

Stdlib only, except that `write` uses PyYAML when present (JSON otherwise, which
is valid YAML).
"""
from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_CONTEXT_CHARS = 10000  # Claude Code's additionalContext cap (hooks reference)
RESERVE = 300              # room for the closing line and JSON overhead drift
GIT_TIMEOUT = 5
PR_STATE_TIMEOUT = 20
PR_TABLE_ROWS = 15
NOTE_RESERVE = "Note: " + "n" * 294  # S8's allowance for entry notes (measure only)
PR_STATE = Path(".claude/skills/session-start/scripts/pr_state.py")
CAPTURE = Path(".claude/skills/chat-archive/scripts/capture_corrections.py")
POLICY = Path(".claude/policy.json")
LANDING = Path(".claude/landing.yaml")
LANE_DIR = Path("handoffs")
LANE_ID = re.compile(r"^[a-z][a-z0-9]{0,15}$")
LANE_KEYS = ("meta", "progress")          # what HANDOFF.yaml holds once lanes are declared
LANE_STATE = "fairbay-lanes.json"         # in the git dir: never tracked, never staged
INDEX_ITEM_CHARS = 160
PROMPT_CHARS = 2000
FULL_SOURCES = (None, "startup", "clear", "fork")
INJECTED_KEYS = ("meta", "next", "carried_forward")
SECTION_START = re.compile(r"^([a-z_]+):")


def _run(cmd: list[str], cwd: str | None = None, timeout: int = GIT_TIMEOUT) -> str:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def _repo_root(cwd: str | None = None) -> Path:
    """$CLAUDE_PROJECT_DIR, else the git top level of cwd, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    cwd = cwd or os.getcwd()
    top = _run(["git", "-C", cwd, "rev-parse", "--show-toplevel"])
    return Path(top) if top else Path(cwd)


def _repo_slug(root: Path) -> str:
    url = _run(["git", "config", "--get", "remote.origin.url"], cwd=str(root))
    if url:
        u = url.rstrip("/")
        if u.endswith(".git"):
            u = u[:-4]
        parts = u.replace(":", "/").split("/")
        if parts and parts[-1]:
            return parts[-1]
    return root.name


def _read_handoff(root: Path):
    for name in ("HANDOFF.yaml", "HANDOFF.yml", "HANDOFF.md"):
        p = root / name
        if p.is_file():
            return name, p.read_text(encoding="utf-8", errors="replace")
    return None


def _pr_gate_table(root: Path, slug: str):
    """(table or None, note or None). The table is capped at PR_TABLE_ROWS rows."""
    script = root / PR_STATE
    if not script.is_file():
        return None, f"PR gate unavailable: {PR_STATE} missing"
    try:
        out = subprocess.run(
            [sys.executable, str(script), "report", "--repo", f"fairbay/{slug}", "--table"],
            cwd=str(root), capture_output=True, text=True, timeout=PR_STATE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None, f"PR gate unavailable: pr_state.py took over {PR_STATE_TIMEOUT} s"
    except Exception as e:
        return None, f"PR gate unavailable: {type(e).__name__}"
    table = out.stdout.strip()
    if out.returncode != 0 or not table:
        return None, f"PR gate unavailable: pr_state.py exit {out.returncode}"
    return _cap_table(table), None


def _cap_table(table: str) -> str:
    """At most PR_TABLE_ROWS PR rows, then a line saying how many were left out."""
    lines = table.splitlines()
    rows = [i for i, l in enumerate(lines) if re.match(r"^\| \d", l)]
    if len(rows) > PR_TABLE_ROWS:
        keep = rows[PR_TABLE_ROWS - 1] + 1
        lines = lines[:keep] + [f"… {len(rows) - PR_TABLE_ROWS} more open PRs: run pr_state.py report"]
    return "\n".join(lines)


def _capture_note(root: Path):
    """None when the capture gate can work here; otherwise one note line.
    Runs the capture script's own exclude steps (idempotent), so a fresh clone
    gets its exclude line now rather than reporting a false failure."""
    path = root / CAPTURE
    if not path.is_file():
        return f"Capture gate inactive: {CAPTURE} missing"
    try:
        spec = importlib.util.spec_from_file_location("capture_corrections", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ok, reason = mod.ensure_excluded(str(root))
    except Exception as e:
        return f"Capture gate inactive: {type(e).__name__} loading it"
    return None if ok else f"Capture queue could not be excluded: {reason}"


def _decision_table(root: Path):
    """(text or None, note or None) for the decision table in .claude/policy.json.
    No file: (None, None); the repo has no routing policy yet."""
    path = root / POLICY
    if not path.is_file():
        return None, None
    try:
        pol = json.loads(path.read_text(encoding="utf-8"))
        rows = pol["decision_table"]
        lines = [f"Decision table ({POLICY} v{pol.get('version', '?')}; first yes routes the change):"]
        n = 0
        for r in rows:
            if "else" in r:
                lines.append(f"- else: {r['else']}")
            else:
                n += 1
                lines.append(f"{n}. {r['q']} → {r['then']}")
        return "\n".join(lines), None
    except Exception as e:
        return None, f"Decision table unavailable: {POLICY} does not parse ({type(e).__name__})"


def _load_pr_state(root: Path):
    spec = importlib.util.spec_from_file_location("pr_state", root / PR_STATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lanes(root: Path) -> list[str]:
    """The lane ids .claude/landing.yaml declares, read with pr_state's landing.yaml parser;
    else []. A non-string item (YAML reads `no`, `on` as booleans) or a bad id is dropped."""
    path = root / LANDING
    if not path.is_file():
        return []
    try:
        items = _load_pr_state(root).parse_policy_yaml(path.read_text(encoding="utf-8")).get("lanes")
    except Exception:
        return []
    out = []
    for raw in items if isinstance(items, list) else []:
        x = raw.strip().lower() if isinstance(raw, str) else ""
        if LANE_ID.match(x) and x not in out:
            out.append(x)
    return out


def _baton_sections(text: str) -> dict:
    """Top-level sections of a lane baton: by column-0 keys, or from the JSON form `write`
    emits without PyYAML (each key re-dumped on its own), as _handoff_sections does."""
    secs = _sections(text)
    if "next" in secs or "meta" in secs:
        return secs
    obj = _parse_existing_text(text)
    if isinstance(obj, dict):
        return {k: json.dumps({k: v}, indent=2, ensure_ascii=False) for k, v in obj.items()}
    return secs


def _lane_rel(x: str) -> str:
    return f"{LANE_DIR}/lane-{x}.yaml"


def _read_lane(root: Path, x: str):
    """(name, text) of a lane's baton, or None."""
    p = root / _lane_rel(x)
    return (_lane_rel(x), p.read_text(encoding="utf-8", errors="replace")) if p.is_file() else None


def _first_next(text: str) -> str:
    """The first `next:` item of a baton, on one line, cut at INDEX_ITEM_CHARS. Read from
    the YAML text by section (no PyYAML needed), else from the JSON form `write` emits."""
    first = None
    sec = _sections(text).get("next")
    if sec:
        item: list[str] = []
        for line in sec.splitlines()[1:]:
            m = re.match(r"^\s*- (.*)$", line)
            if m and item:
                break
            if m:
                item.append(m.group(1))
            elif item and line.strip():
                item.append(line.strip())
        if item:
            first = " ".join(item).strip()
            if len(first) >= 2 and first[0] == first[-1] and first[0] in "'\"":
                first = first[1:-1]
    if first is None:
        obj = _parse_existing_text(text)
        items = obj.get("next") if isinstance(obj, dict) else None
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                first = first.get("item") or first.get("task") or json.dumps(first, ensure_ascii=False)
    if not first:
        return "(no next: item)"
    one = " ".join(str(first).split())
    return one if len(one) <= INDEX_ITEM_CHARS else one[: INDEX_ITEM_CHARS - 1].rstrip() + "…"


def _lane_index(root: Path, lanes: list[str]) -> str:
    lines = ["Lanes (one baton each, `handoffs/lane-<x>.yaml`; .claude/landing.yaml). Name the lane in your "
             "message (\"lane A\") and its baton loads; the project row carries each lane's line too:"]
    for x in lanes:
        got = _read_lane(root, x)
        lines.append(f"- lane {x.upper()}: {_first_next(got[1]) if got else '(no baton file yet)'}")
    return "\n".join(lines)


def _named_lanes(prompt: str, lanes: list[str]) -> list[str]:
    """Declared lanes the prompt names, in order: "lane A", "lane A2" (sub-item of A), "lane-c"."""
    out = []
    for m in re.finditer(r"(?<![a-z0-9])lane[ \t_-]+([a-z][a-z0-9]*)(?![.][a-z])", prompt.lower()):
        tok = m.group(1)
        hit = next((x for x in sorted(lanes, key=len, reverse=True)
                    if tok == x or (tok.startswith(x) and tok[len(x):].isdigit())), None)
        if hit and hit not in out:
            out.append(hit)
    return out


def _state_path(root: Path):
    rel = (_run(["git", "rev-parse", "--path-format=absolute", "--git-path", LANE_STATE], cwd=str(root))
           or _run(["git", "rev-parse", "--git-path", LANE_STATE], cwd=str(root)))
    if not rel:
        return None
    p = Path(rel)
    return p if p.is_absolute() else root / p


def _lane_state(root: Path) -> dict:
    p = _state_path(root)
    try:
        obj = json.loads(p.read_text(encoding="utf-8")) if p and p.is_file() else {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _save_lane_state(root: Path, state: dict) -> None:
    p = _state_path(root)
    if not p:
        return
    keep = dict(list(state.items())[-20:])  # the newest sessions only
    try:
        p.write_text(json.dumps(keep), encoding="utf-8")
    except Exception:
        pass


def _is_envelope(root: Path, prompt: str) -> bool:
    """capture_corrections' filter for turns that are not Baylee's; a tag opening if it is missing."""
    try:
        spec = importlib.util.spec_from_file_location("capture_corrections", root / CAPTURE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return bool(mod.is_envelope(prompt))
    except Exception:
        return prompt.lstrip().startswith("<")


def _lane_stats(root: Path, x: str):
    """(payload text, stats) for one lane's baton, as the lane gate injects it."""
    limit = MAX_CONTEXT_CHARS - RESERVE
    stats = {"cut": [], "omitted": [], "chars_cut": 0}
    got = _read_lane(root, x)
    if not got:
        return (f"Lane {x.upper()} is declared but {_lane_rel(x)} does not exist yet: start from the "
                f"project row's lane {x.upper()} line."), stats
    name, text = got
    parts = [f"Lane {x.upper()} baton ({name}), loaded because your message names lane {x.upper()}. "
             f"Read back its `next:` items (and `carried_forward:`) before starting work; show the "
             f"project row's lane {x.upper()} line beside it."]
    secs = _baton_sections(text)
    for k in INJECTED_KEYS:
        if k not in secs:
            continue
        added, cut = _fit(parts, secs[k], limit)
        if cut:
            kept = added[: -len("\n  (cut; read HANDOFF.yaml)")] if added else ""
            stats["chars_cut"] += len(secs[k]) - len(kept)
            (stats["cut"] if added else stats["omitted"]).append(k)
        if added:
            parts.append(added.replace("(cut; read HANDOFF.yaml)", f"(cut; read {name})"))
    parts.append(f"Other sections (done, progress, decisions_made, parked, watch_outs, …): read {name}.")
    return "\n\n".join(parts), stats


def _emit_prompt(context: str) -> None:
    payload = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": context}}
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.flush()


def cmd_lane() -> int:
    """The lane gate. Prints one JSON payload or nothing; always returns 0."""
    try:
        hook = _hook_input()
        prompt = hook.get("prompt") or ""
        root = _repo_root(hook.get("cwd"))
        lanes = _lanes(root)
        if not lanes or not isinstance(prompt, str) or not prompt.strip() or _is_envelope(root, prompt):
            return 0
        named = _named_lanes(prompt[:PROMPT_CHARS], lanes)
        sid = str(hook.get("session_id") or "")
        state = _lane_state(root)
        seen = state.get(sid, []) if isinstance(state.get(sid), list) else []
        new = [x for x in named if x not in seen]
        if not new:
            return 0
        text, _ = _lane_stats(root, new[0])
        if len(new) > 1:
            text += (f"\n\nAlso named: {', '.join('lane ' + x.upper() for x in new[1:])}; "
                     f"read {', '.join(_lane_rel(x) for x in new[1:])} if this session works there.")
        state.pop(sid, None)
        state[sid] = seen + [new[0]]
        _save_lane_state(root, state)
        _emit_prompt(text)
    except Exception as e:
        _emit_prompt(f"Note: Lane gate error: {type(e).__name__}. Read handoffs/lane-<x>.yaml for your lane.")
    return 0


def _sections(text: str) -> dict:
    """Top-level sections of a YAML handoff, by column-0 `key:` lines. Comments,
    the `# Handoff:` title and column-0 `- ` items stay with the current section."""
    out, current = {}, None
    for line in text.splitlines():
        m = SECTION_START.match(line)
        if m:
            current = m.group(1)
            out[current] = [line]
        elif current:
            out[current].append(line)
    return {k: "\n".join(v).rstrip() for k, v in out.items()}


def _handoff_sections(name: str, text: str, lanes: bool = False) -> dict | None:
    """{key: text} for the injected keys, or None when the file gives no `next`
    (then the caller falls back to head truncation). With lanes: meta and progress."""
    if name.endswith(".md"):
        return None
    secs = _sections(text)
    if lanes:
        return {k: secs[k] for k in LANE_KEYS if k in secs}
    if "next" in secs:
        return {k: secs[k] for k in INJECTED_KEYS if k in secs}
    obj = _parse_existing_text(text)  # JSON form, as cmd_write emits without PyYAML
    if isinstance(obj, dict) and "next" in obj:
        return {k: json.dumps({k: obj[k]}, indent=2, ensure_ascii=False) for k in INJECTED_KEYS if k in obj}
    return None


def _size(context: str) -> int:
    return len(json.dumps(context, ensure_ascii=False))


def _fit(parts: list[str], extra: str, limit: int, keys: bool = False) -> tuple[str, bool]:
    """Append `extra` to the joined parts if it fits; otherwise cut it at the last
    list-item boundary that fits (with keys, also a two-space mapping key: lanes repos). Returns (text added, whether it was cut)."""
    base = "\n\n".join(parts)
    if _size(base + "\n\n" + extra) <= limit:
        return extra, False
    lines = extra.splitlines()
    for end in range(len(lines) - 1, 0, -1):
        if not (re.match(r"^\s*- ", lines[end]) or (keys and re.match(r"^  [a-z][a-z0-9_]*:", lines[end]))):
            continue  # a list item; with keys (lanes repos), also a lane's progress line
        candidate = "\n".join(lines[:end]) + "\n  (cut; read HANDOFF.yaml)"
        if _size(base + "\n\n" + candidate) <= limit:
            return candidate, True
    return "", True


def _compose(slug: str, source, notes: list[str], table, handoff, decision=None, lanes=None) -> str:
    return _compose_stats(slug, source, notes, table, handoff, decision, lanes)[0]


def _compose_stats(slug: str, source, notes: list[str], table, handoff, decision=None, lanes=None):
    """(payload text, stats). stats: cut (sections cut short), omitted (sections
    left out), chars_cut (characters of handoff text that did not make it in).
    lanes: None, or {"index": text, "loaded": [(lane, baton text)]} where the repo
    declares lanes (startup shows HANDOFF.yaml meta/progress and the index;
    compact/resume the loaded lanes' queues, else the index)."""
    limit = MAX_CONTEXT_CHARS - RESERVE
    if decision:  # its room comes first: the table is never the part that is cut
        limit -= _size("\n\n" + decision) - 2
    stats = {"cut": [], "omitted": [], "chars_cut": 0}
    full = source in FULL_SOURCES
    if full:
        head = (
            f"Open handoff for repo '{slug}'. Review it before designing, building, or "
            f"editing files, and acknowledge the `next:` items first (read-back) before "
            f"starting work.\n`carried_forward:` items are unfinished work from earlier "
            f"sessions that no session has done or explicitly dropped. Treat them as part "
            f"of `next:`: they are queued work, not history. If you are not going to do "
            f"one, say so and record it under `dropped:` in your exit handoff."
        )
        if lanes is not None:
            head += (" This repo keeps one baton per lane: your lane's `next:` loads when your message "
                     "names it; without a lane, pick from the index below.")
    else:
        head = f"Still queued in '{slug}' (session {source}; no read-back needed, carry on):"
    parts = [head] + [f"Note: {n}" for n in notes]
    if full and table:
        parts.append(table)
    omitted = []
    if handoff:
        name, text = handoff
        secs = _handoff_sections(name, text, lanes is not None)
        if secs is None:  # no `next` to find: head truncation, as before the redesign
            block = f"### {name}\n{text}"
            while block and _size("\n\n".join(parts + [block])) > limit:
                block = block[: int(len(block) * 0.9)]
            if block != f"### {name}\n{text}":
                stats["cut"].append(name)
                stats["chars_cut"] += len(f"### {name}\n{text}") - len(block)
                block += "\n[truncated: read the file]"
            parts.append(block)
        else:
            keys = INJECTED_KEYS if full else ("next", "carried_forward")
            if lanes is not None:
                keys = LANE_KEYS if full else ()
            for k in keys:
                if k not in secs:
                    continue
                added, cut = _fit(parts, secs[k], limit, lanes is not None)
                if cut:
                    kept = added[: -len("\n  (cut; read HANDOFF.yaml)")] if added else ""
                    stats["chars_cut"] += len(secs[k]) - len(kept)
                    (stats["cut"] if added else stats["omitted"]).append(k)
                if added:
                    parts.append(added)
                else:
                    omitted.append(k)
            if full and lanes is None:
                parts.append(f"Other sections (done, decisions_made, context, …): read {name}.")
    elif full:
        parts.append("No HANDOFF.yaml in this repo.")
    if lanes is not None:
        blocks = [] if full else [
            (f"lane {x}", f"### Lane {x.upper()} ({_lane_rel(x)}), loaded this session\n" +
             "\n\n".join(v for k, v in _baton_sections(t).items() if k in ("next", "carried_forward")))
            for x, t in lanes.get("loaded", [])]
        if not blocks:
            blocks = [("lane index", lanes.get("index") or "")]
        for key, block in blocks:
            added, cut = _fit(parts, block, limit, True)
            if cut:
                stats["chars_cut"] += len(block) - len(added)
                (stats["cut"] if added else stats["omitted"]).append(key)
            if added:
                parts.append(added)
            else:
                omitted.append(key)
    if omitted:
        parts.append(f"Omitted for space: {', '.join(omitted)}; read the handoff file.")
    if decision:
        parts.append(decision)
    return "\n\n".join(parts), stats


def _lanes_ctx(root: Path, session_id=None):
    """None without declared lanes; else the index and the lanes loaded this session."""
    lanes = _lanes(root)
    if not lanes:
        return None
    seen = _lane_state(root).get(str(session_id or ""), []) if session_id else []
    loaded = [(x, got[1]) for x in seen if x in lanes for got in [_read_lane(root, x)] if got]
    return {"index": _lane_index(root, lanes), "loaded": loaded}


def _emit(context: str) -> None:
    payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}}
    # UTF-8 bytes: a non-UTF-8 stdout must not crash the gate.
    sys.stdout.buffer.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.flush()


def _hook_input() -> dict:
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        obj = json.loads(raw) if raw.strip() else {}
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def cmd_inject() -> int:
    """Prints exactly one JSON payload, as its last act, and returns 0."""
    try:
        hook = _hook_input()
        source = hook.get("source")
        root = _repo_root(hook.get("cwd"))
        slug = _repo_slug(root)
        notes = []
        capture = _capture_note(root)
        if capture:
            notes.append(capture)
        table = None
        if source in FULL_SOURCES:
            table, note = _pr_gate_table(root, slug)
            if note:
                notes.append(note)
        decision, note = _decision_table(root)
        if note:
            notes.append(note)
        context = _compose(slug, source, notes, table, _read_handoff(root), decision,
                           _lanes_ctx(root, hook.get("session_id")))
    except Exception as e:
        context = f"Note: Entry gate error: {type(e).__name__}. Run the session-start skill."
    _emit(context)
    return 0


def _worst_case_table(root: Path, slug: str) -> str:
    """A PR_TABLE_ROWS-row table in pr_state.py's own format, every row as long as
    a real row gets: an owned draft (the longest extra), a 60-character title, the
    policy line and a G2 line above it."""
    ps = _load_pr_state(root)
    longest = max(ps.ROW_TEXT, key=lambda k: len(k) + len(ps.ROW_TEXT[k]))
    pr = {"number": 9999, "row": longest, "state": "D-owned", "checks": "Billing-failed",
          "head_age_days": 999.9, "recommendation": "close_and_upgrade_task", "owner_required": True,
          "majors": ["@playwright/test 1.99.0→2.0.0", "@supabase/supabase-js 2.99.0→3.0.0"],
          "title": "W" * 80}
    rep = {"repo": f"fairbay/{slug}", "checked_at": "2026-01-01T00:00:00Z", "reachable": True,
           "policy_source": "landing.yaml",
           "policy": {"merge_policy_declared": "policy", "merge_policy_fallback": "x" * 160},
           "default_head": {"row": "G2", "sha": "0" * 40, "deploy_state": "failure",
                            "redeploy": "npm run site:publish"},
           "prs": [dict(pr) for _ in range(PR_TABLE_ROWS + 1)]}
    return _cap_table(ps.to_table(rep))


def _measure(root: Path) -> dict:
    slug = _repo_slug(root)
    try:
        table = _worst_case_table(root, slug)
    except Exception as e:
        return {"ok": False, "error": f"worst-case table: {type(e).__name__}: {e}"}
    decision, note = _decision_table(root)
    notes = [note] if note else []
    notes += [NOTE_RESERVE]  # the entry gate's own notes (capture, PR gate) take about this much
    lanes = _lanes(root)
    text, stats = _compose_stats(slug, "startup", notes, table, _read_handoff(root), decision,
                                 {"index": _lane_index(root, lanes), "loaded": []} if lanes else None)
    size = _size(text)
    ok = not stats["cut"] and not stats["omitted"] and size <= MAX_CONTEXT_CHARS - RESERVE
    res = {"ok": ok, "size": size, "limit": MAX_CONTEXT_CHARS - RESERVE,
           "decision_table": bool(decision), **stats}
    if lanes:  # S8 per loaded file: each lane's baton as the lane gate injects it
        res["lanes"] = {}
        for x in lanes:
            if not _read_lane(root, x):
                continue
            ltext, lst = _lane_stats(root, x)
            lok = not lst["cut"] and not lst["omitted"] and _size(ltext) <= MAX_CONTEXT_CHARS - RESERVE
            res["lanes"][x] = {"ok": lok, "size": _size(ltext), **lst}
            if not lok:
                res["ok"] = False
                res["cut"] += [f"lane {x}: {k}" for k in lst["cut"]]
                res["omitted"] += [f"lane {x}: {k}" for k in lst["omitted"]]
                res["chars_cut"] += lst["chars_cut"]
    return res


def cmd_measure() -> int:
    res = _measure(_repo_root())
    print(json.dumps(res, ensure_ascii=False))
    return 0 if res["ok"] else 1


def _to_yaml(obj) -> str:
    try:
        import yaml  # type: ignore

        return yaml.safe_dump(
            obj, sort_keys=False, default_flow_style=False, allow_unicode=True
        )
    except Exception:
        # JSON is valid YAML — safe fallback when PyYAML is unavailable.
        return json.dumps(obj, indent=2, ensure_ascii=False)


def _parse_existing_text(text: str):
    """Parse handoff text (YAML or JSON) after stripping the '# Handoff:' title
    line cmd_write emits. Returns a dict or None; never raises."""
    payload = "\n".join(l for l in text.splitlines() if not l.startswith("# Handoff:"))
    try:
        import yaml  # type: ignore

        obj = yaml.safe_load(payload)
    except Exception:
        try:
            obj = json.loads(payload)
        except Exception:
            return None
    return obj if isinstance(obj, dict) else None


def _parse_existing(dest: Path):
    """Read the handoff we're about to overwrite. Returns a dict or None.
    Never raises — a malformed prior handoff must not block the exit gate."""
    if not dest.is_file():
        return None
    try:
        return _parse_existing_text(dest.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _norm(item) -> str:
    """Stable identity for a next-item so carry-forward can dedupe."""
    if isinstance(item, dict):
        s = item.get("item") or item.get("task") or json.dumps(item, sort_keys=True)
    else:
        s = str(item)
    return " ".join(s.split()).lower()


def _carry_forward(body: dict, dest: Path) -> dict:
    """Preserve unfinished work from the handoff being replaced.

    The exit gate previously did a blind overwrite: whatever the prior session
    queued in `next:` was destroyed even if nothing had been done about it.
    Any prior `next:` item the incoming handoff neither repeats nor explicitly
    resolves is carried into `carried_forward:` so it survives the write.

    A session resolves an item by listing it (verbatim or near-verbatim) in
    `done:` or `dropped:`. Otherwise it persists.
    """
    prior = _parse_existing(dest)
    if not prior:
        return body

    # `parked:` is a list the schema keeps until a session clears it: a body that
    # omits the key keeps the prior list (an empty list clears it).
    if "parked" not in body and isinstance(prior.get("parked"), list) and prior["parked"]:
        body["parked"] = prior["parked"]

    # Prior `next:` AND prior `carried_forward:` are both live queues — an item
    # already carried once must keep surviving until it's done or dropped.
    prior_next = []
    for key in ("next", "carried_forward"):
        vals = prior.get(key) or []
        if isinstance(vals, list):
            prior_next.extend(vals)
    if not prior_next:
        return body

    # Everything the incoming handoff accounts for.
    resolved = set()
    for key in ("done", "dropped", "next", "carried_forward", "parked"):
        vals = body.get(key) or []
        if isinstance(vals, list):
            for v in vals:
                resolved.add(_norm(v))  # a parked {item, location} normalizes by its item

    # Words too common to signal that two items are the same work.
    _STOP = {
        "the", "a", "an", "and", "or", "to", "for", "of", "in", "on", "at",
        "is", "are", "be", "with", "from", "into", "task", "grove", "check",
        "add", "fix", "update", "run", "do", "this", "that", "it", "not",
        "p0", "p1", "p2", "p3", "standing", "new", "all", "per", "via",
    }

    def _tokens(s: str) -> set:
        out = set()
        for raw in s.split():
            t = raw.strip("[]()<>.,:;'\"—-%").lower()
            # 2 chars is the floor: state codes (VT, RI, TX) are among the most
            # distinctive tokens a handoff item carries.
            if len(t) < 2 or t in _STOP:
                continue
            out.add(t)
        return out

    def _ids(s: str) -> set:
        # Grove/commit ids: long hex-ish tokens. Strongest possible signal.
        out = set()
        for raw in s.split():
            t = raw.strip("[]()<>.,:;'\"")
            if len(t) >= 8 and all(c in "0123456789abcdef" for c in t.lower()):
                out.add(t.lower())
        return out

    def _claimed(needle: str) -> bool:
        n_ids, n_tok = _ids(needle), _tokens(needle)
        for r in resolved:
            if not r or not needle:
                continue
            # 1. Exact / containment of the full normalized string.
            if needle == r or needle in r or r in needle:
                return True
            # 2. Shared Grove task id — unambiguous.
            if n_ids and (n_ids & _ids(r)):
                return True
            # 3. Strong token overlap on distinctive words.
            r_tok = _tokens(r)
            if not n_tok or not r_tok:
                continue
            shared = n_tok & r_tok
            if len(shared) >= 2 and len(shared) >= 0.6 * min(len(n_tok), len(r_tok)):
                return True
        return False

    carried = [i for i in prior_next if not _claimed(_norm(i))]
    if not carried:
        return body

    existing = body.get("carried_forward") or []
    if not isinstance(existing, list):
        existing = [existing]
    seen = {_norm(x) for x in existing}
    for c in carried:
        if _norm(c) not in seen:
            existing.append(c)
            seen.add(_norm(c))
    body["carried_forward"] = existing
    return body


def _set_progress_line(root: Path, x: str, line: str, slug: str) -> None:
    """Replace (or add) only the `  x:` line of HANDOFF.yaml's `progress:`, keeping a
    blank line between lane keys so two lanes' edits are never adjacent (git conflicts
    on adjacent lines; docs/lanes/DESIGN.md §2)."""
    dest = root / "HANDOFF.yaml"
    if dest.is_file():
        lines = dest.read_text(encoding="utf-8").splitlines()
    else:
        lines = [f"# Handoff: {slug} (one baton per lane: {LANE_DIR}/lane-<x>.yaml)", "",
                 "meta:", f"  project: {slug}", "  layout: lanes", ""]
    value = f"  {x}: {json.dumps(' '.join(str(line).split()), ensure_ascii=False)}"
    start = next((i for i, l in enumerate(lines) if re.match(r"^progress:\s*(#.*)?$", l)), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", "progress:", value]
    else:
        end = next((i for i in range(start + 1, len(lines)) if SECTION_START.match(lines[i])), len(lines))
        hit = next((i for i in range(start + 1, end) if re.match(rf"^  {re.escape(x)}:(\s|$)", lines[i])), None)
        if hit is not None:
            lines[hit] = value
        else:
            last = max([i for i in range(start, end) if lines[i].strip()] or [start])
            insert = ([value] if last == start else ["", value])
            lines[last + 1:last + 1] = insert
    dest.write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def cmd_write(lane: str | None = None) -> int:
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    try:
        body = json.loads(raw) if raw.strip() else {}
    except Exception:
        body = {}

    root = _repo_root()
    lanes = _lanes(root)
    if lanes and not lane:
        sys.stderr.write(f"refused: .claude/landing.yaml declares lanes {lanes}: write --lane <x> "
                         f"(a whole HANDOFF.yaml rewrite would touch every lane's lines).\n")
        return 2
    if lane and lane not in lanes:
        sys.stderr.write(f"refused: lane {lane!r} is not declared in .claude/landing.yaml ({lanes or 'no lanes'}).\n")
        return 2
    progress_line = body.pop("progress_line", None)
    meta = dict(body.get("meta", {}))
    htype = meta.get("type") or body.get("type") or "build"
    slug = meta.get("project") or _repo_slug(root)
    meta["project"] = slug
    meta["type"] = htype
    if lane:
        meta["lane"] = lane
    meta["surface"] = meta.get("surface", "claude-code")
    meta["generated"] = meta.get("generated") or _dt.datetime.now(
        _dt.timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    body["meta"] = meta
    body.pop("type", None)
    title = body.pop("title", None) or (f"{slug} lane {lane.upper()} handoff" if lane else f"{slug} {htype} handoff")

    dest = root / (_lane_rel(lane) if lane else "HANDOFF.yaml")
    dest.parent.mkdir(parents=True, exist_ok=True)

    # Exit gate: never destroy unfinished work. Anything the prior handoff
    # queued in `next:` that this session didn't do or explicitly drop gets
    # carried into `carried_forward:` rather than silently overwritten.
    body = _carry_forward(body, dest)
    text = f"# Handoff: {title}\n\n{_to_yaml(body)}"

    dest.write_text(text, encoding="utf-8")
    if lane and progress_line:
        _set_progress_line(root, lane, progress_line, slug)
    print(str(dest))
    # S8 backstop (decision routing): the file is written, but the exit says not to push it
    # while the entry hook would cut it. Repos without a PR gate script skip the check.
    if (root / PR_STATE).is_file():
        res = _measure(root)
        if not res["ok"]:
            hint = ("Shorten this lane's progress line (every lane's line rides every startup payload)."
                    if any(k in ("progress", "lane index") for k in res["cut"] + res["omitted"])
                    else "Keep 3-5 next: items and park the rest with a location.")
            sys.stderr.write(f"S8: do not push this handoff: {json.dumps(res, ensure_ascii=False)}. {hint}\n")
            return 1
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "inject":
        return cmd_inject()
    if cmd == "write":
        lane = argv[argv.index("--lane") + 1].lower() if "--lane" in argv[2:-1] else None
        return cmd_write(lane)
    if cmd == "measure":
        return cmd_measure()
    if cmd == "lane":
        return cmd_lane()
    sys.stderr.write("usage: session_handoff.py <inject|lane|measure|write [--lane x]>\n")
    return 0  # never non-zero — callable from a hook context


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
