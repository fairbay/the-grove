#!/usr/bin/env python3
"""
Shared API call helper for the delegate-* skill family (runs on API credits, not the
subscription).

Used by delegate-mechanical, delegate-analytical, delegate-adversarial. Lives in
delegate-mechanical/scripts/, which sync.py copies into every repo's .claude/skills/.

Python:
  import sys
  sys.path.insert(0, '.claude/skills/delegate-mechanical/scripts')   # chat: /mnt/skills/user/...
  from delegate import call
  output, usage = call(model='claude-haiku-5-5', system='...', user='...', max_tokens=2048)

Command line (bulk text goes in files, never in tool arguments):
  python3 .claude/skills/delegate-mechanical/scripts/delegate.py \
      --model claude-sonnet-5-5 --system-file sys.txt --user-file task.txt [--max-tokens 4096]
  The reply goes to stdout; token usage goes to stderr.

The key is $ANTHROPIC_API_KEY from the session's environment; no key file is read
(faca1b33). Where it is not set, a Code session uses an Agent sub-agent with an explicit
model and chat applies the lens inline. A missing key is surfaced, never retried or
worked around.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


class DelegateError(RuntimeError):
    """Surfaced verbatim — message tells Baylee what to do."""


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise DelegateError(
            "ANTHROPIC_API_KEY is not set in this session's environment (no key file is "
            "read). In a Code session, use an Agent sub-agent with model set instead; "
            "to use this helper, Baylee adds the key to the cloud environment."
        )
    return key


def call(model: str, system: str, user: str, max_tokens: int = 2048) -> tuple[str, dict]:
    """POST one message to the Anthropic API and return (text, usage)."""
    api_key = _load_api_key()

    payload = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        raise DelegateError(f"Anthropic API HTTP {e.code}: {body}") from e

    text = "".join(b["text"] for b in result["content"] if b["type"] == "text")
    return text, result.get("usage", {})


def main() -> int:
    ap = argparse.ArgumentParser(description="One Anthropic API call on API credits.")
    ap.add_argument("--model", required=True)
    ap.add_argument("--system-file", required=True)
    ap.add_argument("--user-file", required=True)
    ap.add_argument("--max-tokens", type=int, default=2048)
    a = ap.parse_args()
    try:
        text, usage = call(a.model, open(a.system_file).read(), open(a.user_file).read(), a.max_tokens)
    except DelegateError as e:
        print(f"delegate: {e}", file=sys.stderr)
        return 1
    print(text)
    print(json.dumps({"model": a.model, "input_tokens": usage.get("input_tokens"),
                      "output_tokens": usage.get("output_tokens")}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

