#!/usr/bin/env python3
"""
The outside-model doorway client (fairbay/ops docs/llm-doorway/DESIGN.md; MBN m1308).

Every call to an outside model goes through `llm.call` / `llm.result` in the MBN
Supabase database: the key is read from the Vault inside the database and never
returned; the limits refuse (never retry); every call and refusal is a row in
`llm.calls`. This client runs those two statements as two separate Management
API requests with the SUPABASE_ACCESS_TOKEN the session already has.

Surfaces:
  Code sessions and Routines  — this client (SUPABASE_ACCESS_TOKEN in the environment).
  Chat                        — no token: run the same two statements through the
                                Supabase connector (SKILL.md "From chat"); this
                                client raises DoorwayError saying so.

Never read a key, never print one, never fall back to a direct provider call:
when the doorway refuses or cannot be reached, the error names the reason and
the session stops and reports it. A model substitution is Baylee's call.

  from llm_doorway import call, estimate, default_model, DoorwayError
  r = call('google', 'gemini-2.5-flash', body, purpose='idea-scout research', surface='code')
  r['status'] in ('done', 'error', 'refused', 'lost');  r['text'];  r['response'];  r['cost_usd']
"""
import base64
import json
import os
import time
import urllib.error
import urllib.request

PROJECT_REF = 'mqbnsjkeucvumdoqdeww'
API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'
CHAT_BODY_LIMIT = 20_000  # bytes; larger bodies go to a Code session or the manual channel


class DoorwayError(RuntimeError):
    """Surfaced verbatim. Tells the session to stop and report, not to substitute a model."""


def _token() -> str:
    tok = os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip()
    if not tok:
        raise DoorwayError(
            "No SUPABASE_ACCESS_TOKEN in this environment, so the doorway cannot be called from here. "
            "From chat, run `select llm.call(...)` then `select llm.result(<id>, 25)` through the Supabase "
            "connector (delegate-adversarial SKILL.md, \"From chat\"). Otherwise stop and tell Baylee; "
            "do not call a provider directly and do not substitute a model."
        )
    return tok


def _query(sql: str, timeout: int = 60) -> list:
    req = urllib.request.Request(
        API, data=json.dumps({'query': sql}).encode(),
        headers={'Authorization': f'Bearer {_token()}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raise DoorwayError(f"Supabase Management API HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from e
    except urllib.error.URLError as e:
        raise DoorwayError(f"Supabase Management API unreachable: {e.reason}") from e
    out = json.loads(raw) if raw else []
    return out if isinstance(out, list) else [out]


def _lit(s) -> str:
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"


def _b64(body: dict) -> str:
    return base64.b64encode(json.dumps(body, ensure_ascii=False).encode('utf-8')).decode('ascii')


def _body_sql(body: dict) -> str:
    return f"convert_from(decode('{_b64(body)}', 'base64'), 'utf8')::jsonb"


def session_url() -> str | None:
    """The session's address when the harness provides one; otherwise None."""
    for k in ('CLAUDE_SESSION_URL', 'CLAUDE_SESSION', 'CLAUDE_CODE_SESSION_ID'):
        v = os.environ.get(k)
        if v:
            return v if v.startswith('http') else f'session:{v}'
    return None


def default_model(job: str = 'review') -> str:
    """The model `llm.prices` names as the default for a job ('review' | 'mechanical')."""
    rows = _query(f"select model from llm.prices where default_for = {_lit(job)} limit 1")
    if not rows:
        raise DoorwayError(f"llm.prices has no default model for {job!r}")
    return rows[0]['model']


def estimate(provider: str, model: str, body: dict, n_calls: int = 1) -> dict:
    """Price a call (or n of them) before starting. Say the total before a multi-call run."""
    rows = _query(f"select llm.estimate({_lit(provider)}, {_lit(model)}, {_body_sql(body)}, {int(n_calls)}) as r")
    return rows[0]['r']


TIMEOUT_MS = 600000  # pg_net's maximum. A review-sized Pro call (16K output cap) runs ~2 min at the
                     # ~150 tokens/s measured 2026-10-19; one call that day stalled past 300 s.


def finish_reason(response: dict | None) -> str | None:
    """The provider's finish reason (Gemini: candidates[0].finishReason), or None if absent."""
    try:
        return (response or {}).get('candidates', [{}])[0].get('finishReason')
    except (AttributeError, IndexError, TypeError):
        return None


def _mark_finish(res: dict) -> dict:
    """A `done` call whose answer did not finish normally is not done: MAX_TOKENS -> `truncated`,
    any other non-STOP reason (SAFETY, RECITATION, ...) -> `blocked`. Gemini counts thinking tokens
    against maxOutputTokens, so a cap sized for the answer alone truncates it (2026-10-19)."""
    reason = finish_reason(res.get('response'))
    res['finish_reason'] = reason
    if res.get('status') == 'done' and reason not in (None, 'STOP'):
        res['status'] = 'truncated' if reason == 'MAX_TOKENS' else 'blocked'
        res['message'] = (
            f"finishReason {reason}: the answer is incomplete and must not be used as a full result. "
            + ("Thinking counts toward maxOutputTokens: raise the cap or lower the thinking level, then make one new call."
               if reason == 'MAX_TOKENS' else "Report it; do not retry unchanged.")
        )
    return res


def call(provider: str, model: str, body: dict, purpose: str, surface: str = 'code',
         session: str | None = None, run_id: str | None = None, run_budget_usd: float | None = None,
         timeout_ms: int = TIMEOUT_MS, wait_seconds: int | None = None, text_only: bool = False) -> dict:
    """
    One outside-model call through the doorway. Returns the `llm.result` row as a dict:
    status (done | truncated | blocked | error | refused | lost | queued), text, response (when
    text_only is False), finish_reason, usage, cost_usd, est_cost_usd, error, error_class, message.

    `refused`, `error`, `truncated` and `blocked` are returned, not raised: the caller reports them
    and stops; a retry is a new, explicit call that changes something. Only transport failures raise
    DoorwayError.
    """
    if wait_seconds is None:
        wait_seconds = timeout_ms // 1000 + 30
    session = session or session_url()
    budget = 'NULL' if run_budget_usd is None else repr(float(run_budget_usd))
    rows = _query(
        f"select llm.call({_lit(provider)}, {_lit(model)}, {_body_sql(body)}, {_lit(purpose)}, {_lit(surface)}, "
        f"{_lit(session)}, {_lit(run_id)}, {budget}, {int(timeout_ms)}) as r"
    )
    r = rows[0]['r']
    if r.get('status') != 'queued':
        return r
    call_id = r['call_id']
    deadline = time.monotonic() + max(wait_seconds, 1)
    while True:
        remaining = deadline - time.monotonic()
        wait = int(min(25, max(0, remaining)))
        # Always fetch the full response: the finish reason lives there.
        rows = _query(f"select llm.result('{call_id}'::uuid, {wait}, false) as r", timeout=wait + 30)
        res = rows[0]['r']
        if res.get('status') != 'queued' or remaining <= 0:
            res = _mark_finish(res)
            if text_only:
                res.pop('response', None)
            return res


def report_line(res: dict, what: str) -> str:
    """One line for the session's report."""
    u = res.get('usage') or {}
    cost = res.get('cost_usd')
    return (f"Doorway {res.get('status')} for {what}: {u.get('promptTokenCount', '?')} in / "
            f"{u.get('candidatesTokenCount', '?')} out ({u.get('thoughtsTokenCount', 0)} thinking), "
            f"${cost if cost is not None else res.get('est_cost_usd')}"
            + (f" — {res.get('message') or res.get('error')}" if res.get('status') != 'done' else ''))

