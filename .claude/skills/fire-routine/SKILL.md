---
name: fire-routine
description: >
  Fire async Claude Code Routines — "fire scout-r", "fire skill-worker-r",
  "drain the queue", "routine-fire X". Not for inline scoring/scouting
  (→ idea-scout) or sync delegation (→ delegate-*).
metadata:
  version: "2026-06-12-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# fire-routine — fire async Claude Code Routines from chat

Fires a Claude Code Routine via its API trigger endpoint from any chat session.
The Routine runs out-of-session — results land later in Grove, the vault, or
target repos. This is async hand-off, not in-session delegation.

Distinguished from the delegate-* family: a delegate-* call awaits a result and
returns it inline. A Routine fire returns a session URL and ends the
interaction; the work continues elsewhere.

## Available Routines

| Name | Env file | What it does |
|------|----------|--------------|
| `scout-r` | `secrets/scout-r.env` | Runs idea-scout as a Routine — scores idea, commits to idea-vault. |
| `skill-worker-r` | `secrets/skill-worker-r.env` | Drains Grove tasks tagged `routine:skill-worker` — reads work orders from task notes, implements changes, pushes to target repos, marks tasks done. Fires nightly on schedule in addition to manual fires. |
| `grove-prune-r` | — (schedule-only) | Nightly Grove hygiene — stale task/idea assessment. Fires on the nightly schedule. No fire credentials stored; to make it manually fire-able, store `secrets/grove-prune.env` (ROUTINE_FIRE_URL + ROUTINE_FIRE_TOKEN). |

## Routing: fire vs inline

Routine fires are not a precious resource to defend. Fire when Baylee uses a
fire word (`fire`, `routine-fire`, `async`, `drain`, `queue`, or the `-r`
suffix) — or when an objective Baylee has authorized is naturally implemented
by a routine fire, even without fire vocabulary. Route to the inline sibling
only when Baylee plainly wants an in-session answer. Reserve confirmation for
large multi-fire batches (see batch firing below).

| Message | Route to |
|---------|----------|
| "fire scout-r [idea]" / "routine-fire scout-r" / "scout-r [idea]" | this skill, scout-r |
| "drain the queue" / "fire skill-worker-r" | this skill, skill-worker-r |
| "scout this" / "evaluate this idea" (no fire word) | `idea-scout` (inline) |
| "scout all of these" (no fire word) | `idea-scout` per idea, inline |

If the user names a routine without a fire word ("scout-r this idea"), treat
the `-r` suffix as the explicit trigger.

### Three-mode routing (skill-worker-r)

| Mode | When to use | Poll? |
|------|-------------|-------|
| Queue-only | Default — nothing waiting on results; change lands overnight via the nightly drain | No |
| Fire-and-forget | You want the change sooner (minutes) but the session doesn't depend on the result | No |
| Fire-and-verify | Load-bearing: the fire is itself a test, or the next action depends on the result | Yes (Step 5) |

## Workflow

### 1. Identify routine and payload

- **Which routine.** Match by name (`scout-r` / `skill-worker-r`) or queue
  language ("drain," "queue," "worker" → `skill-worker-r`).
- **Payload text.** For scout-r: the idea description. For skill-worker-r:
  optional — pass "drain queue" or empty (the Routine reads its own queue from
  Grove).
- **Batch mode.** If the user names multiple ideas with a fire trigger ("fire
  scout-r on #3, #5, and #8"), fire one Routine per idea. Not applicable to
  skill-worker-r — it processes its own queue internally.

If no payload text is given for scout-r ("fire scout-r" with no idea), ask for
the idea description. For skill-worker-r, no payload is needed — just fire.

#### Batch firing — plan and confirm before executing

When multiple ideas are specified (from a brainstorm list, vault comparison,
or explicit enumeration), announce the batch and wait for confirmation before
firing:

> About to fire scout-r on 5 ideas:
> 1. [first 60 chars of idea text]
> 2. [...]
> Each fire counts against the daily routine cap. Proceed?

The cap is shared across all routine fires that day — a typo'd batch ("on all
12" when Baylee meant 3) is hard to claw back. Single fires skip this
confirmation; the cost-of-error is one fire.

After confirmation:

1. Read credentials once (Step 2).
2. Loop through each idea, POSTing to the fire URL with each idea's description.
3. Collect all session URLs.
4. Report all session URLs in a single response — Routines run concurrently
   and results land in the vault as each completes.
5. If any individual fire fails mid-batch (429 rate limit, etc.), report which
   succeeded and which failed rather than stopping the batch.

### 2. Read credentials from repo

```python
import sys
sys.path.insert(0, '/mnt/skills/user/git-ops/scripts')
from git_push import read_file

env_file = 'secrets/scout-r.env'  # or 'secrets/skill-worker-r.env'
env_content = read_file('fairbay/ops', env_file)

creds = {}
for line in env_content.strip().split('\n'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        key, val = line.split('=', 1)
        creds[key.strip()] = val.strip()

fire_url = creds['ROUTINE_FIRE_URL']
fire_token = creds['ROUTINE_FIRE_TOKEN']
```

### 3. Fire the Routine

```python
import urllib.request, urllib.error, json

payload = json.dumps({"text": idea_text}).encode()
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
- For `scout-r`: "Routine runs asynchronously — results land in the vault when
  done."
- For `skill-worker-r`: "Routine runs asynchronously — it will process the
  task queue and push changes to target repos. Check Grove for completion
  status."
- Session progress is viewable at the URL.

On failure:

- 400 = missing headers (should not happen with this skill's code).
- 401 = token expired — rotate at `claude.ai/code/routines`, update the
  relevant `secrets/*.env`.
- 429 = rate limited — Routine fires count against the daily cap.
- 400 with reason `routine_paused` = the Routine is paused — Baylee unpauses
  at `claude.ai/code/routines`, then refire.

### 5. Post-fire verification — skill-worker-r, load-bearing fires only

Skip this step for scout-r, any read-only routine, and any fire-and-forget or queue-only skill-worker-r fire.

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

**scout-r:**
- "Results land in the vault as a scored idea when the routine finishes
  (usually a few minutes)."
- "Check Grove or ask me to 'show my ideas' to see the scored report."

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

## Security

- Never echo the fire token in output or commit it to any repo.
- The token has fire-only scope — it can't read routine config or session data.
- If the token needs rotating, Baylee does it at `claude.ai/code/routines` and
  updates the relevant `secrets/*.env` in the repo.

## Adding future routines

When a new Routine is created:

1. Store fire credentials in `secrets/<routine-name>.env` with `ROUTINE_FIRE_URL`
   and `ROUTINE_FIRE_TOKEN`.
2. Add a row to the Available Routines table above.
3. Add a follow-up block in Step 6 answering: where do results land, how does
   Baylee verify them, is there a manual collection step.
4. Update this skill's description to include the new trigger phrase.
5. Bump `metadata.version`.

## Integration

- **→ idea-scout, idea-vault:** scout-r results land in the vault.
- **→ grove:** skill-worker-r drains Grove tasks; results visible there.
- **→ git-ops:** post-fire verification reads target repos.
- **vs delegate-* family:** delegate-* awaits a result inline; fire-routine
  hands off async and ends the interaction.
