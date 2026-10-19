#!/usr/bin/env python3
"""capture_corrections.py — UserPromptSubmit hook (Claude Code only).

Detects correction / preference / positive-feedback signals in Baylee's
prompts and appends them to <root>/.claude/learnings-queue.jsonl. chat-archive
step 3b'' drains the queue: each entry is routed through the encoding gate,
then the file is deleted.

Synced into every repo with the chat-archive skill; the hook entry in
.claude/settings.json is managed by fairbay/ops (docs/hook-delivery/DESIGN.md).

Adapted from the claude-reflect pattern (BayramAnnakov/claude-reflect):
hooks capture ephemeral feedback automatically; a human-reviewed gate
persists it. Here the existing encoding gate IS that review step.

Contract (critical):
- NEVER print to stdout — UserPromptSubmit stdout is injected into the
  model's context. Silence on success and on failure.
- ALWAYS exit 0 — a hook failure must never block a prompt.
- The queue holds prompt text, so it is excluded from git BEFORE anything is
  written, and nothing is written if the exclude cannot be confirmed: a
  `git add -A` must never stage it (two Fairbay repos are public).
- Only Baylee's turns: the hook also fires on sub-agent hand-backs, task
  notifications and peer messages, which arrive as user-role turns. Those
  are skipped by their opening.
- Precision over recall — a false negative costs nothing (chat-archive 3a
  still reviews the conversation); false positives pollute the queue.
"""
import json
import os
import re
import subprocess
import sys
import time

QUEUE_REL = ".claude/learnings-queue.jsonl"
CLASSIFY_CHARS = 1000  # a long paste (a report, a log) is not a correction

# Harness-delivered turns. A tag opening covers <agent-message>, <task-notification>,
# <system-reminder>, <wake>, <child-session-event>, <webhook-payload>, ... A bare "["
# is NOT skipped: "[Image #1] fix this" from a screenshot is Baylee's.
ENVELOPE_TAG = re.compile(r"^<[a-z_-]+")
ENVELOPE_PREFIXES = (
    "[SYSTEM", "[Subagent", "[Artifact", "[Request interrupted",
    "Another Claude session sent a message", "Stop hook feedback",
)
ENVELOPE_ANYWHERE = ("[Subagent hand-back]",)

CORRECTION = [
    r"^no[,.\s]+(use|don'?t|do not|that'?s|it'?s|not|you)",
    r"^(actually|wait)[,\s]",
    r"\bi (already )?told you\b",
    r"\bstop (doing|using|adding)\b",
    r"\bthat'?s (wrong|not right|incorrect|not what i)\b",
    r"\bnot what i (asked|meant|wanted)\b",
    r"\byou (forgot|missed|broke|skipped|shouldn'?t have)\b",
    r"\bnever (do|use|add|push)\b",
    r"\bwhy did you\b",
]
PREFERENCE = [
    r"\bremember( to|:|,)\b",
    r"\balways (use|do|run|check|include)\b",
    r"\bfrom now on\b",
    r"\bgoing forward[,\s]",
]
POSITIVE = [
    r"^(perfect|exactly)\b",
    r"\bthat'?s (it|perfect|exactly right)\b",
    r"\bkeep doing (that|this)\b",
]

BUCKETS = (("correction", CORRECTION), ("preference", PREFERENCE),
           ("positive", POSITIVE))


def _git(root, *args, timeout=5):
    """(returncode, stdout) of `git -C <root> ...`; (1, '') when git cannot run."""
    try:
        out = subprocess.run(["git", "-C", str(root), *args],
                             capture_output=True, text=True, timeout=timeout)
        return out.returncode, out.stdout.strip()
    except Exception:
        return 1, ""


def repo_root(cwd=None):
    """$CLAUDE_PROJECT_DIR, else the git top level of cwd, else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return env
    cwd = cwd or os.getcwd()
    rc, top = _git(cwd, "rev-parse", "--show-toplevel")
    return top if rc == 0 and top else cwd


def ensure_excluded(root):
    """Make sure the queue path is git-ignored in this clone. Returns (ok, reason).

    Steps (DESIGN.md §3.3): resolve info/exclude from the root (correct from a
    worktree, never another repo the cwd sits in); create its directory; append
    the line, newline-first when the file lacks a trailing newline; confirm with
    check-ignore from the root. Any failure means: do not write the queue.
    """
    rc, exclude = _git(root, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude")
    if rc != 0 or not exclude:
        return False, "not a git repository"
    try:
        os.makedirs(os.path.dirname(exclude), exist_ok=True)
        current = ""
        if os.path.exists(exclude):
            with open(exclude, encoding="utf-8", errors="replace") as f:
                current = f.read()
        if QUEUE_REL not in current.splitlines():
            with open(exclude, "a", encoding="utf-8") as f:
                f.write(("\n" if current and not current.endswith("\n") else "") + QUEUE_REL + "\n")
    except OSError as e:
        return False, f"cannot write {exclude} ({type(e).__name__})"
    rc, _ = _git(root, "check-ignore", "-q", QUEUE_REL)
    if rc != 0:
        return False, "check-ignore does not cover the queue"
    return True, ""


def is_envelope(prompt):
    s = prompt.lstrip()
    return (bool(ENVELOPE_TAG.match(s))
            or s.startswith(ENVELOPE_PREFIXES)
            or any(m in s for m in ENVELOPE_ANYWHERE))


def classify(prompt):
    low = prompt.strip()[:CLASSIFY_CHARS].lower()
    if not low or low.startswith("/"):  # slash commands are never feedback
        return None, None
    for kind, patterns in BUCKETS:
        for p in patterns:
            if re.search(p, low):
                return kind, p
    return None, None


def _append(root, entry):
    os.makedirs(os.path.join(root, os.path.dirname(QUEUE_REL)), exist_ok=True)
    with open(os.path.join(root, QUEUE_REL), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _record_error(root, session_id, where, exc):
    """One error line per (session_id, where, type), so a persistent crash
    does not add a line for every prompt."""
    key = (session_id, where, type(exc).__name__)
    path = os.path.join(root, QUEUE_REL)
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("kind") == "error" and (e.get("session_id"), e.get("where"), e.get("type")) == key:
                        return
        _append(root, {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "session_id": session_id, "kind": "error", "where": where,
                       "type": type(exc).__name__})
    except Exception:
        pass


def handle(raw):
    """Process one hook payload. Never raises, never prints."""
    try:
        payload = json.loads(raw)
        prompt = payload.get("prompt", "") or ""
        session_id = payload.get("session_id", "") or ""
        cwd = payload.get("cwd")
    except (ValueError, AttributeError):
        prompt, session_id, cwd = raw or "", "", None
    if is_envelope(prompt):
        return
    root = repo_root(cwd)
    try:
        kind, pattern = classify(prompt)
    except Exception as e:
        if ensure_excluded(root)[0]:
            _record_error(root, session_id, "classify", e)
        return
    if not kind:
        return
    ok, _ = ensure_excluded(root)
    if not ok:
        return  # fail closed: SessionStart's inject reports why
    try:
        _append(root, {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id,
            "kind": kind,
            "pattern": pattern,
            "prompt": prompt.strip()[:500],
        })
    except Exception as e:  # the exclude is confirmed, so an error line is safe to write
        _record_error(root, session_id, "write", e)


def main():
    try:
        handle(sys.stdin.read())
    except Exception:
        pass  # never block, never speak


if __name__ == "__main__":
    main()
    sys.exit(0)
