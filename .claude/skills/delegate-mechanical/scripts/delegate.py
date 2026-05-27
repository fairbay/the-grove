#!/usr/bin/env python3
"""
Shared API call helper for the delegate-* skill family.

Used by delegate-mechanical, delegate-analytical, delegate-adversarial.
Lives in delegate-mechanical/scripts/ because it has to live somewhere; all
three skills are installed together as a family.

Usage:
  import sys
  sys.path.insert(0, '/mnt/skills/user/delegate-mechanical/scripts')
  from delegate import call

  output, usage = call(
      model='claude-haiku-4-5-20251001',
      system='You are a focused assistant. Return only [format].',
      user='[task instruction + content]',
      max_tokens=2048,
  )

Reads ANTHROPIC_API_KEY from secrets/delegate.env in fairbay/baylee-skills.
Surfaces a clear error if the file or key is missing rather than retrying or
falling back silently — Baylee needs to know to set it up or rotate the token.
"""
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, '/mnt/skills/user/git-ops/scripts')
from git_push import read_file  # noqa: E402


class DelegateError(RuntimeError):
    """Surfaced verbatim — message tells Baylee what to do."""


def _load_api_key() -> str:
    try:
        env = read_file('fairbay/baylee-skills', 'secrets/delegate.env')
    except Exception as e:
        raise DelegateError(
            "secrets/delegate.env not found in fairbay/baylee-skills. "
            "First-time setup: create the file with "
            "ANTHROPIC_API_KEY=sk-ant-... from console.anthropic.com."
        ) from e

    pairs = dict(
        line.split('=', 1)
        for line in env.strip().split('\n')
        if '=' in line and not line.startswith('#')
    )
    key = pairs.get('ANTHROPIC_API_KEY', '').strip()
    if not key:
        raise DelegateError(
            "ANTHROPIC_API_KEY missing from secrets/delegate.env. "
            "Rotate at console.anthropic.com and update the file."
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
