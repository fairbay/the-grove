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
  Code, token read-only/none  — the workflow route: in an MBN checkout, the request is
                                committed to a throwaway claude/doorway-* branch and sent
                                through MBN's db-apply `doorway` mode (scripts/db_apply_remote.py),
                                which holds the write token; same result shape (ops 3477c48b).
  Chat                        — no token: run the same two statements through the
                                Supabase connector (SKILL.md "From chat"); this
                                client raises DoorwayError saying so.

Route (LLM_DOORWAY_ROUTE or call(route=...)): 'auto' (default) uses the token, and takes
the workflow route when there is none or when llm.call fails because the token cannot
write, but only when the working directory is the MBN checkout (the request body stays
on an MBN branch: never route another project's material there unasked); 'direct' never
takes the workflow route; 'workflow' always does. The workflow route waits on timeout_ms
(plus the run's start), not wait_seconds.

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
import re
import secrets
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_REF = 'mqbnsjkeucvumdoqdeww'
API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'
CHAT_BODY_LIMIT = 20_000  # bytes; larger bodies go to a Code session or the manual channel
MBN_REPO = 'fairbay/medicaid-benefits-navigator'
ROUTES = ('auto', 'direct', 'workflow')
# A direct llm.call that fails with one of these is a token that cannot write (C4's Database-read-only
# token): the auto route sends the call through the workflow instead. Inferred from Postgres and the
# Management API's wording; not yet observed on the read-only token itself (first C4 session: check).
_READ_ONLY = re.compile(r'HTTP 40[13]|read[- ]only|permission denied|insufficient privilege|must be owner', re.I)
_ECHOED_SQL = re.compile(r'(\\n|\n)LINE \d+:')  # Postgres echoes the statement (and its purpose text) after this
# MBN scripts/db_modes.py DOORWAY: the workflow refuses a request outside these types.
_PROVIDER_RX = re.compile(r'^[a-z][a-z0-9_]{0,30}$')
_MODEL_RX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
_SESSION_RX = re.compile(r'^https://claude\.ai/code/session_[A-Za-z0-9]{1,64}$')
_RUN_ID_RX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
_PRINTABLE = re.compile(r'^[^\x00-\x1f\x7f]*$')
WORKFLOW_BUDGET_MAX = 5.0
WORKFLOW_BODY_MAX = 1_000_000  # db_modes.BODY_MAX: bytes of json.dumps(body) with its default ensure_ascii


def _cannot_write(err: str) -> bool:
    """A permission failure, read from the message before any echoed SQL (which carries the caller's purpose)."""
    return bool(_READ_ONLY.search(_ECHOED_SQL.split(err, 1)[0]))


class DoorwayError(RuntimeError):
    """Surfaced verbatim. Tells the session to stop and report, not to substitute a model."""


def _has_token() -> bool:
    return bool(os.environ.get('SUPABASE_ACCESS_TOKEN', '').strip())


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
    """The session's address when the harness provides one; otherwise None.

    A cloud Code session exposes its id as CLAUDE_CODE_REMOTE_SESSION_ID=cse_<x>; its URL is
    https://claude.ai/code/session_<x>, the form llm.spend_by_session lookups match (Grove 005d19e7).
    CLAUDE_CODE_SESSION_ID is only the local transcript id, so it is the last resort.
    """
    for k in ('CLAUDE_SESSION_URL', 'CLAUDE_SESSION'):
        v = os.environ.get(k)
        if v:
            return v if v.startswith('http') else f'session:{v}'
    remote = os.environ.get('CLAUDE_CODE_REMOTE_SESSION_ID', '').strip()
    if remote:
        return f"https://claude.ai/code/session_{remote.removeprefix('cse_').removeprefix('session_')}"
    local = os.environ.get('CLAUDE_CODE_SESSION_ID')
    return f'session:{local}' if local else None


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
         timeout_ms: int = TIMEOUT_MS, wait_seconds: int | None = None, text_only: bool = False,
         route: str | None = None) -> dict:
    """
    One outside-model call through the doorway. Returns the `llm.result` row as a dict:
    status (done | truncated | blocked | error | refused | lost | queued), text, response (when
    text_only is False), finish_reason, usage, cost_usd, est_cost_usd, error, error_class, message.
    A call sent by the workflow route also carries route='workflow' and workflow_run (the run's URL).

    `refused`, `error`, `truncated` and `blocked` are returned, not raised: the caller reports them
    and stops; a retry is a new, explicit call that changes something. Only transport failures raise
    DoorwayError.
    """
    route = route or os.environ.get('LLM_DOORWAY_ROUTE', '').strip() or 'auto'
    if route not in ROUTES:
        raise DoorwayError(f"route must be one of {', '.join(ROUTES)}, not {route!r}")
    if wait_seconds is None:
        wait_seconds = timeout_ms // 1000 + 30
    session = session or session_url()
    args = dict(provider=provider, model=model, body=body, purpose=purpose, surface=surface, session=session,
                run_id=run_id, run_budget_usd=run_budget_usd, timeout_ms=timeout_ms, text_only=text_only)
    if route == 'workflow':
        return _via_workflow(**args, why='route workflow')
    if route == 'auto' and not _has_token():
        return _auto_workflow(args, 'no token in this environment')
    budget = 'NULL' if run_budget_usd is None else repr(float(run_budget_usd))
    try:
        rows = _query(
            f"select llm.call({_lit(provider)}, {_lit(model)}, {_body_sql(body)}, {_lit(purpose)}, {_lit(surface)}, "
            f"{_lit(session)}, {_lit(run_id)}, {budget}, {int(timeout_ms)}) as r"
        )
    except DoorwayError as e:
        # llm.call writes a row, so a read-only token fails here before anything is sent (no row, no spend).
        if route == 'auto' and _cannot_write(str(e)):
            return _auto_workflow(args, f'the token cannot write ({str(e)[:160]})')
        raise
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
            return _finish(res, text_only)


def _finish(res: dict, text_only: bool) -> dict:
    res = _mark_finish(res)
    if text_only:
        res.pop('response', None)
    return res


# -- The workflow route (MBN db-apply `doorway` mode) -------------------------

def _git(root, *args, input=None, env=None) -> str:
    p = subprocess.run(['git', '-C', str(root), *args], input=input, capture_output=True, text=True,
                       env=env, timeout=120)
    if p.returncode:
        raise DoorwayError(f"workflow route: git {args[0]} failed: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout.strip()


def _is_mbn(root: Path) -> bool:
    if not (root / 'scripts' / 'db_apply_remote.py').is_file():
        return False
    p = subprocess.run(['git', '-C', str(root), 'remote', 'get-url', 'origin'], capture_output=True, text=True)
    return p.returncode == 0 and re.search(rf'{re.escape(MBN_REPO)}(\.git)?/?$', p.stdout.strip()) is not None


def mbn_root() -> Path | None:
    """The MBN checkout the workflow route runs from: $MBN_ROOT, else the git top level of the working
    directory or of this file, else an MBN clone beside either (a Code session's sibling clones)."""
    tops = []
    for start in (os.getcwd(), str(Path(__file__).resolve().parent)):
        p = subprocess.run(['git', '-C', start, 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip():
            tops.append(Path(p.stdout.strip()))
    cands = ([Path(os.environ['MBN_ROOT'])] if os.environ.get('MBN_ROOT') else []) + tops \
        + [t.parent / MBN_REPO.split('/')[1] for t in tops]
    for c in cands:
        if _is_mbn(c):
            return c
    return None


def _cwd_is_mbn() -> bool:
    p = subprocess.run(['git', 'rev-parse', '--show-toplevel'], capture_output=True, text=True)
    return p.returncode == 0 and bool(p.stdout.strip()) and _is_mbn(Path(p.stdout.strip()))


def _auto_workflow(args: dict, why: str) -> dict:
    """The auto route takes the workflow only for MBN work: the request body is committed to a branch of the
    MBN repository that a session cannot delete, so another project's material (Mission 1 above all) never
    lands there unasked. Anywhere else the caller opts in with route='workflow' (review of ops 3477c48b, finding 1)."""
    if not _cwd_is_mbn():
        raise DoorwayError(
            f"The doorway cannot be called directly from here ({why}). The workflow route commits the request body to "
            f"a {MBN_REPO} branch that stays there, so the auto route takes it only when the working directory is the "
            "MBN checkout. For other work, pass route='workflow' (or LLM_DOORWAY_ROUTE=workflow) only if the body may "
            "sit in that repository; never for personal (Mission 1) material. From chat, run `select llm.call(...)` "
            "then `select llm.result(<id>, 25)` through the Supabase connector (delegate-adversarial SKILL.md, "
            "\"From chat\"). Otherwise stop and tell Baylee; do not call a provider directly and do not substitute a model."
        )
    return _via_workflow(**args, why=why)


def _request_file(provider, model, body, purpose, surface, session, run_id, run_budget_usd, timeout_ms) -> dict:
    """The request db_modes.py types (MBN scripts/db_modes.py DOORWAY); refused here before anything is pushed."""
    if not (isinstance(provider, str) and _PROVIDER_RX.fullmatch(provider)):
        raise DoorwayError(f"workflow route: provider must match {_PROVIDER_RX.pattern}")
    if not (isinstance(model, str) and _MODEL_RX.fullmatch(model)):
        raise DoorwayError(f"workflow route: model must match {_MODEL_RX.pattern}")
    if not isinstance(body, dict):
        raise DoorwayError("workflow route: body must be a JSON object")
    try:
        size = len(json.dumps(body, allow_nan=False).encode())
    except ValueError as e:
        raise DoorwayError(f"workflow route: body is not plain JSON ({e})") from e
    if size > WORKFLOW_BODY_MAX:
        raise DoorwayError(f"workflow route: body is {size:,} bytes as the workflow counts it; at most {WORKFLOW_BODY_MAX:,}")
    if surface not in ('chat', 'code', 'routine'):
        raise DoorwayError(f"workflow route: surface must be chat, code or routine, not {surface!r}")
    if not (isinstance(purpose, str) and 1 <= len(purpose) <= 200 and _PRINTABLE.fullmatch(purpose)):
        raise DoorwayError("workflow route: purpose must be 1 to 200 characters with no control character")
    if run_id is not None and not _RUN_ID_RX.fullmatch(run_id):
        raise DoorwayError(f"workflow route: run_id must match {_RUN_ID_RX.pattern}")
    if run_budget_usd is not None and not (0 < float(run_budget_usd) <= WORKFLOW_BUDGET_MAX):
        raise DoorwayError(f"workflow route: run_budget_usd must be above 0 and at most {WORKFLOW_BUDGET_MAX}")
    if not (1000 <= int(timeout_ms) <= TIMEOUT_MS):
        raise DoorwayError(f"workflow route: timeout_ms must be from 1000 to {TIMEOUT_MS}")
    q = {'provider': provider, 'model': model, 'surface': surface, 'purpose': purpose, 'body': body,
         'timeout_ms': int(timeout_ms)}
    if session and _SESSION_RX.fullmatch(session):
        q['session'] = session
    elif session:  # a local transcript id is not a session URL: the workflow would refuse it, so the call records none
        q['_session_dropped'] = session
    if run_id is not None:
        q['run_id'] = run_id
    if run_budget_usd is not None:
        q['run_budget_usd'] = float(run_budget_usd)
    return q


def _push_request(root: Path, rel: str, branch: str, text: str) -> str:
    """One commit on top of main as just fetched (FETCH_HEAD: a narrow clone may not update origin/main) holding
    only the request file, pushed to `branch`. Plumbing only: the checkout's working tree, index and branch are
    never touched."""
    _git(root, 'fetch', '-q', 'origin', 'main')
    base = _git(root, 'rev-parse', 'FETCH_HEAD')
    blob = _git(root, 'hash-object', '-w', '--stdin', input=text)
    with tempfile.TemporaryDirectory() as td:
        env = {**os.environ, 'GIT_INDEX_FILE': str(Path(td) / 'index')}
        env.setdefault('GIT_AUTHOR_NAME', 'Claude')
        env.setdefault('GIT_AUTHOR_EMAIL', 'noreply@anthropic.com')
        env.setdefault('GIT_COMMITTER_NAME', env['GIT_AUTHOR_NAME'])
        env.setdefault('GIT_COMMITTER_EMAIL', env['GIT_AUTHOR_EMAIL'])
        _git(root, 'read-tree', base, env=env)
        _git(root, 'update-index', '--add', '--cacheinfo', f'100644,{blob},{rel}', env=env)
        tree = _git(root, 'write-tree', env=env)
        commit = _git(root, 'commit-tree', tree, '-p', base, '-m',
                      f'doorway request {Path(rel).name} (llm_doorway.py workflow route; data, never merged)', env=env)
    _git(root, 'push', '-q', 'origin', f'{commit}:refs/heads/{branch}')
    return commit


def _via_workflow(provider, model, body, purpose, surface, session, run_id, run_budget_usd, timeout_ms,
                  text_only, why) -> dict:
    root = mbn_root()
    if root is None:
        raise DoorwayError(
            f"The doorway cannot be called from here ({why}) and no {MBN_REPO} checkout was found for the workflow "
            "route (set MBN_ROOT to one). From chat, run `select llm.call(...)` then `select llm.result(<id>, 25)` "
            "through the Supabase connector (delegate-adversarial SKILL.md, \"From chat\"). Otherwise stop and tell "
            "Baylee; do not call a provider directly and do not substitute a model."
        )
    q = _request_file(provider, model, body, purpose, surface, session, run_id, run_budget_usd, timeout_ms)
    dropped = q.pop('_session_dropped', None)
    if _has_token():  # a read works on a read-only token; the workflow's mode does not price the body first
        est = estimate(provider, model, body)
        if not est.get('ok'):  # refused before llm.call, so no llm.calls row: nothing was sent
            return {'status': 'refused', 'route': 'workflow', 'error_class': 'estimate', 'estimate': est,
                    'error': '; '.join(est.get('problems') or []) or 'llm.estimate answered ok=false',
                    'message': 'llm.estimate refused the body, so nothing was sent; fix the body, then make one new call.'}
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    name = f"{stamp}-{re.sub(r'[^A-Za-z0-9._-]', '-', run_id or 'call')[:40]}-{secrets.token_hex(3)}"
    rel, branch = f'reports/doorway/{name}.json', f'claude/doorway-{name}'
    _push_request(root, rel, branch, json.dumps(q, ensure_ascii=False, allow_nan=False, indent=1) + '\n')
    where = f"branch {branch}, pushed {stamp}"
    res, log, err = None, '', None
    try:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / 'result.json'
            wait = int(timeout_ms) // 1000 + 300  # the call's own limit plus the workflow's start and artifact
            p = subprocess.run(
                ['python3', 'scripts/db_apply_remote.py', '--mode', 'doorway', '--args', rel, '--sql-ref', branch,
                 '--out', str(out), '--timeout', str(wait)],
                cwd=root, capture_output=True, text=True, timeout=wait + 120)
            log = (p.stdout + p.stderr).strip()
            if out.is_file():  # exit 1 with a result is the call's own status (db_modes exits 1 unless done)
                res = json.loads(out.read_text(encoding='utf-8'))
            else:
                hint = (" (exit 2: this checkout's scripts/db_apply_remote.py may predate the doorway mode; pull main)"
                        if p.returncode == 2 else "")
                err = f"no result from the db-apply doorway run (exit {p.returncode}){hint}: {log[-600:]}"
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        err = f"{type(e).__name__}: {str(e)[:300]} (the workflow run may still be going; read `gh run list --workflow db-apply.yml` before any new call)"
    finally:
        try:
            left = _delete_branch(root, branch)
        except (OSError, subprocess.SubprocessError):
            left = True
    if err is None and not isinstance(res, dict):
        err = f"the result is not a JSON object: {str(res)[:200]}"
    if err is None and res.get('status') == 'failed':  # db_modes' own failure record: the step, never the database text
        code = re.search(r'\b(\d{2}[0-9A-Z]{3})\b', str(res.get('database', '')))
        err = f"the workflow's {res.get('what', 'llm step')} failed" + (f" (SQLSTATE {code.group(1)})" if code else "")
    if err:
        raise DoorwayError(f"workflow route: {err}; {where}" + (" (left on origin)" if left else " (deleted)"))
    runs = re.findall(r'https://github\.com/\S+/actions/runs/\d+', log)
    res.update(route='workflow', workflow_run=runs[-1] if runs else None)
    if left:
        res['branch_left'] = branch
    if dropped:
        res['session_dropped'] = dropped
    return _finish(res, text_only)


def _delete_branch(root: Path, branch: str) -> bool:
    """Try once to delete the request branch; True when it is still on origin. A cloud session's git proxy
    refuses branch deletion (HTTP 403, while git itself exits 0; observed 2026-11-05), so the branch is
    checked, never assumed gone: a left branch is named in the result (`branch_left`) and cleared later
    by whoever can delete branches (MBN task a7785d68). A policy denial is not retried."""
    subprocess.run(['git', '-C', str(root), 'push', '-q', 'origin', '--delete', branch],
                   capture_output=True, text=True, timeout=60)
    p = subprocess.run(['git', '-C', str(root), 'ls-remote', 'origin', f'refs/heads/{branch}'],
                       capture_output=True, text=True, timeout=60)
    return p.returncode != 0 or bool(p.stdout.strip())


def report_line(res: dict, what: str) -> str:
    """One line for the session's report."""
    u = res.get('usage') or {}
    cost = res.get('cost_usd')
    return (f"Doorway {res.get('status')} for {what}: {u.get('promptTokenCount', '?')} in / "
            f"{u.get('candidatesTokenCount', '?')} out ({u.get('thoughtsTokenCount', 0)} thinking), "
            f"${cost if cost is not None else res.get('est_cost_usd')}"
            + (f" — {res.get('message') or res.get('error')}" if res.get('status') != 'done' else ''))

