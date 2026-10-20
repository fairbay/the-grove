#!/usr/bin/env python3
"""decision_fit.py — count a Grove decision's characters before grove_log_decision.

grove_log_decision refuses a `decision` over 2,000 characters; sessions hit that
three times in a row before the text fit (Grove e6a91e53). Run this first: it
counts, and when the text is over the target it keeps whole sentences up to the
target in `decision` and returns the rest as `overflow`, which goes in the
call's `context` (or in task notes when the context would pass the target too).

    python3 decision_fit.py [--target 1500] < text.txt
    python3 decision_fit.py --json '{"decision": "...", "context": "..."}'

Prints one JSON object: {"chars", "target", "fits", "decision", "overflow"};
with --json input also "context" (the input context with the overflow prepended
under "Detail: ") and "context_fits" (false: put the long form in notes instead). Exit 0 always on valid input, 2 on bad input.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

HARD_CAP = 2000  # the API's validation limit
SENTENCE_END = re.compile(r"(?<=[.;!?])\s+(?=\S)")


def fit(text: str, target: int) -> tuple[str, str]:
    """Whole sentences up to `target` characters, and the rest, sliced from the original text
    (never re-joined, so nothing is lost or repeated whatever the whitespace)."""
    text = text.strip()
    if len(text) <= target:
        return text, ""
    cut = 0
    for m in SENTENCE_END.finditer(text):
        if m.start() > target:
            break
        cut = m.start()
    if cut:
        return text[:cut].rstrip(), text[cut:].strip()
    # no sentence ends inside the target: cut at the last space before it
    sp = text.rfind(" ", 0, target - 1)
    sp = sp if sp > 0 else target - 1
    return text[:sp].rstrip() + "…", text[sp:].strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1500)
    ap.add_argument("--json", dest="payload")
    a = ap.parse_args(argv)
    if not 1 <= a.target <= HARD_CAP:
        print(f"decision_fit: --target must be 1..{HARD_CAP}", file=sys.stderr)
        return 2
    context = None
    if a.payload is not None:
        try:
            obj = json.loads(a.payload)
            text = obj["decision"]
            context = obj.get("context") or ""
        except (ValueError, KeyError, TypeError) as e:
            print(f"decision_fit: bad --json input: {e}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()
    if not isinstance(text, str) or not text.strip():
        print("decision_fit: empty decision text", file=sys.stderr)
        return 2
    decision, overflow = fit(text, a.target)
    out = {"chars": len(text.strip()), "target": a.target, "fits": not overflow,
           "decision": decision, "overflow": overflow}
    if context is not None:
        out["context"] = (f"Detail: {overflow}\n\n{context}" if overflow else context).strip()
        # past the target, the long form belongs in the task or project notes, not the decision row
        out["context_fits"] = len(out["context"]) <= a.target
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
