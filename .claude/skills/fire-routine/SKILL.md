---
name: fire-routine
description: >
  Fire async Claude Code Routines — "fire skill-worker-r", "drain the queue",
  "routine-fire X". Not for inline scoring/scouting
  (→ idea-scout) or sync delegation (→ delegate-*).
metadata:
  version: "2026-10-26-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# fire-routine — fire async Claude Code Routines

Fires a Claude Code Routine via its API trigger endpoint. The fire credentials
are environment variables of the "GitHub" cloud environment, so a fire runs
from a Code session (or a Routine); chat has no environment and no key file to
read (faca1b33). In chat, queue the work instead (the nightly drain picks it
up) or ask Baylee to press Run now on the routine's page.
The Routine runs out-of-session — results land later in Grove or
target repos. This is async hand-off, not in-session delegation.

Distinguished from the delegate-* family: a delegate-* call awaits a result and
returns it inline. A Routine fire returns a session URL and ends the
interaction; the work continues elsewhere.

## Available Routines

| Name | Environment variables | What it does |
|------|---------------------------|--------------|
| `skill-worker-r` | `SKILL_WORKER_R_FIRE_URL`, `SKILL_WORKER_R_FIRE_TOKEN` | Drains Grove tasks tagged `routine:skill-worker` — reads work orders from task notes, implements changes, pushes to target repos, marks tasks done. Fires nightly on schedule in addition to manual fires. |
| `grove-prune-r` | — (schedule-only) | Nightly Grove hygiene — stale task/idea assessment. Fires on the nightly schedule. No fire credentials stored; to make it manually fire-able, Baylee adds `GROVE_PRUNE_R_FIRE_URL` and `GROVE_PRUNE_R_FIRE_TOKEN` to the cloud environment. |

scout-r was retired on 2026-10-26 (decision 8238c666): idea scouting runs inline (→ idea-scout).

## Routing: fire vs inline

Routine fires are not a precious resource to defend. Fire when Baylee uses a
fire word (`fire`, `routine-fire`, `async`, `drain`, `queue`, or the `-r`
suffix) — or when an objective Baylee has authorized is naturally implemented
by a routine fire, even without fire vocabulary. Route to the inline sibling
only when Baylee plainly wants an in-session answer. A single fire needs no
confirmation; the cost of an error is one fire.

| Message | Route to |
|---------|----------|
| "drain the queue" / "fire skill-worker-r" | this skill, skill-worker-r |
| "scout this" / "evaluate this idea" (no fire word) | `idea-scout` (inline) |
| "scout all of these" (no fire word) | `idea-scout` per idea, inline |

If the user names a routine without a fire word ("skill-worker-r this"), treat
the `-r` suffix as the explicit trigger. A request for scout-r goes to idea-scout
inline (scout-r is retired).

### Three-mode routing (skill-worker-r)

| Mode | When to use | Poll? |
|------|-------------|-------|
| Queue-only | Default — nothing waiting on results; change lands overnight via the nightly drain | No |
| Fire-and-forget | You want the change sooner (minutes) but the session doesn't depend on the result | No |
| Fire-and-verify | Load-bearing: the fire is itself a test, or the next action depends on the result | Yes (Step 5) |

## Workflow

### 1. Identify routine and payload

- **Which routine.** Match by name (`skill-worker-r`) or queue language
  ("drain," "queue," "worker" → `skill-worker-r`).
- **Payload text.** Optional for skill-worker-r — pass "drain queue" or empty
  (the Routine reads its own queue from Grove). One fire per request: it
  processes its own queue internally, and each fire counts against the daily
  routine cap.

### 2. Read credentials from the environment

```python
import os

prefix = 'SKILL_WORKER_R'  # the routine name, upper-cased, '-' → '_'
fire_url = os.environ.get(f'{prefix}_FIRE_URL')
fire_token = os.environ.get(f'{prefix}_FIRE_TOKEN')
if not (fire_url and fire_token):
    raise SystemExit(f'{prefix}_FIRE_URL / _FIRE_TOKEN not set: fire from a Code '
                     'session in the "GitHub" cloud environment, or queue the work.')
```

No key file is read and none is committed; the values never appear in output.

### 3. Fire the Routine

```python
import urllib.request, urllib.error, json

payload_text = 'drain queue'  # optional for skill-worker-r (Step 1)
payload = json.dumps({"text": payload_text}).encode()
req = urllib.request.Request(
    fire_url,
    data=payload,
    headers={
        "Authorization": f"Bearer {fire_token}",
        "Content-Type": "application/json",
        "anthropic-beta": "experimental-cc-routine-2026-04-01",
        "anthropic-version": "2023-06-01",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
        session_url = result.get('claude_code_session_url', '')
        session_id = result.get('claude_code_session_id', '')
except urllib.error.HTTPError as e:
    error_body = e.read().decode()
    status = e.code
```

### 4. Report result

On success (2xx), the response contains:

```json
{
  "claude_code_session_id": "session_...",
  "claude_code_session_url": "https://claude.ai/code/session_...",
  "type": "routine_fire"
}
```

Report to the user:

- The session URL (clickable link).
- For `skill-worker-r`: "Routine runs asynchronously — it will process the
  task queue and push changes to target repos. Check Grove for completion
  status."
- Session progress is viewable at the URL.

On failure:

- 400 = missing headers (should not happen with this skill's code).
- 401 = token expired — Baylee regenerates it at `claude.ai/code/routines` and
  updates the variable in the cloud environment.
- 429 = rate limited — Routine fires count against the daily cap.
- 400 with reason `routine_paused` = the Routine is paused — Baylee unpauses
  at `claude.ai/code/routines`, then refire.

### 5. Post-fire verification — skill-worker-r, load-bearing fires only

Skip this step for any read-only routine and any fire-and-forget or queue-only skill-worker-r fire.

Polling is for load-bearing fires only — when the fire is itself a test or the session's next move depends on the result. For everything else, the mechanical completion gate plus the nightly drain are the safety net: an unwatched fire cannot produce a false done, and a refused task is retried automatically.

`worker.py complete` is mechanically gated — it verifies each task's `verify:` lines against the default branch before accepting completion, and `worker.py check <id>` dry-runs the gate. When you do poll (load-bearing fires), this step catches collateral damage the gate can't see (wrong file edited alongside, gate-skipped tasks).

1. **Poll up to ~5 minutes** (every ~30s) for the session to finish — check
   the session URL from Step 4. If still running after the cap, stop polling
   and tell Baylee to verify later via `'check skill drift'`. Do not block
   the session indefinitely.
2. **For each task the Routine claimed to complete**, verify the repo change
   exists. Use `git-ops` to read the target file from the repo and confirm
   the edit. If the file is unchanged, the task needs to be reopened and the
   change applied manually.
3. **Check Grove** for recently-completed `routine:skill-worker` tasks
   (status=done, sorted by completed_at descending). For each: confirm the
   corresponding repo change landed.

If any claimed completion has no matching change, report it to Baylee:
> skill-worker-r marked [task title] done but the change is not in the repo.
> It needs to be re-queued or applied manually.

### 6. Provide follow-up guidance

After reporting the session URL, give Baylee routine-specific next steps so
he knows what to do once the routine finishes. The routine runs asynchronously
— these steps tell him how to verify and collect the output.

**skill-worker-r:**
- "The routine will process the task queue and push changes to target repos."
- "After it finishes (check the session URL or give it a few minutes), come
  back to any claude.ai chat and say **'check skill drift'** or **'sync
  skills'** — I'll run `skill_sync.py` to verify the changes landed and hand
  you installable zips for any skills that were updated."
- "If skill_sync shows no drift but Grove tasks were marked done, the routine
  may have failed silently — check the session log."

## Queueing skill-worker tasks — verify lines are mandatory

When creating a `routine:skill-worker` task ("queue this for the worker"),
the task notes MUST include at least one machine-readable verify line:

```
verify: owner/repo/path/to/file :: distinctive phrase proving the change
```

`worker.py complete` is mechanically gated (anti-pattern 7): it fetches each
verify target from the repo's DEFAULT BRANCH over the GitHub API and refuses
completion unless every phrase is found. A queued task without verify lines
cannot be completed by the routine — it will be skipped back to you. Pick a
phrase that exists ONLY after the change (new text being added, the new
version string), not text that's already in the file.

## If create_trigger is denied

When a chat→Code session fire via `create_trigger` is denied by the permission classifier (the block is intermittent and wording-dependent; observed 2026-09-29, MBN ledger-30 notifier):

1. Do not retry, and do not reword the prompt to get past the classifier.
2. Write the full prompt to a `.md` file right away, send it with `SendUserFile`, and tell Baylee in one line to paste it into a new Claude Code session on the repo.
3. Keep the same prompt structure: authorization block, steps, landing, close-out.

## Security

- Never echo the fire token in output or commit it to any repo.
- The token has fire-only scope — it can't read routine config or session data.
- If the token needs rotating, Baylee does it at `claude.ai/code/routines` and
  updates the variable in the cloud environment. Never write it to a file.

## Adding future routines

When a new Routine is created:

1. Baylee adds `<NAME>_FIRE_URL` and `<NAME>_FIRE_TOKEN` to the "GitHub" cloud
   environment (never a file in a repo).
2. Add a row to the Available Routines table above.
3. Add a follow-up block in Step 6 answering: where do results land, how does
   Baylee verify them, is there a manual collection step.
4. Update this skill's description to include the new trigger phrase.
5. Bump `metadata.version`.

## Integration

- **→ grove:** skill-worker-r drains Grove tasks; results visible there.
- **→ git-ops:** post-fire verification reads target repos.
- **vs delegate-* family:** delegate-* awaits a result inline; fire-routine
  hands off async and ends the interaction.
