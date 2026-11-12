---
name: fire-routine
description: >
  Fire async Claude Code Routines — "fire skill-worker-r", "drain the queue",
  "routine-fire X". Not for inline scoring/scouting
  (→ idea-scout) or sync delegation (→ delegate-*).
metadata:
  version: "2026-11-12-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# fire-routine — fire async Claude Code Routines

Starts a Claude Code Routine outside its schedule. No skill reads or sends a
routine fire token: the skill-worker-r fire URL and token variables were unset
on 2026-11-12 (`docs/secrets-move/DESIGN.md` §4.2). A manual fire is Baylee's **Run now** on
the routine's page, from chat or Code: a session cannot fire a routine created
through the HTTP API, and trigger calls cost him a tap each (global rules,
"Remote Control / Scheduling Tools"). Queueing the work for the routine's next
scheduled run needs no fire at all.
The Routine runs out-of-session — results land later in Grove or
target repos. This is async hand-off, not in-session delegation.

Distinguished from the delegate-* family: a delegate-* call awaits a result and
returns it inline. A Routine fire starts a separate session and ends
the interaction; the work continues elsewhere.

## Available Routines

| Name | How it runs | What it does |
|------|-------------|--------------|
| `skill-worker-r` | Daily at 04:30 New York time | Works Grove tasks tagged `routine:skill-worker`: one draft pull request in `fairbay/ops` per work order. It lands nothing; a later run completes a task once its pull request is merged. |
| `grove-prune-r` | Mondays at 04:00 New York time | Grove hygiene: stale task and idea assessment. |
| `guide-r` | Mondays at 02:00 Detroit time | Keeps the MBN administrator guide current: re-reads the sources of pages that changed and opens one draft pull request in MBN (`routines/guide/ROUTINE.md`). |
| `data-draft-r` | Daily at 03:16 New York time | Drafts the one MBN data batch lane A's START HERE names, as a draft pull request. It applies, publishes and merges nothing, and stops when no batch is named (`routines/data-draft/ROUTINE.md`). |
| `data-apply-r` | Daily at 01:02 New York time | The data runner's separate checking run: checks a drafted batch afresh and applies it only when its own check passes (`routines/data-apply/ROUTINE.md`). |

All five are enabled and were created through the HTTP API, so a session cannot
start one: outside its schedule, a routine starts only on Baylee's **Run now**
(Step 2). The schedules are as stored on 2026-11-12 (`list_triggers`). The
routines page is the record: a row that differs from it is corrected in the
pull request that notices.

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
| Queue-only | Default — nothing waiting on results; the routine's next scheduled run opens the draft pull request | No |
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

### 2. Give Baylee the Run-now steps

Numbered, inline (global rule 7), with the payload text from Step 1 if any:

1. Open `https://claude.ai/code/routines`.
2. Tap the routine's name (for example `skill-worker-r`).
3. Tap **Run now**. A new routine session starts; its progress shows on that
   page.

If the page shows the routine as paused, say so and ask whether he wants it
resumed before he taps.

### 3. A session-made routine only

`fire_trigger` is for a routine this repo records as created by a session
(none is recorded today). One attempt with its trigger id: a refusal is not
retried or reworded; report it verbatim and give the Step 2 steps.

### 4. Report result

Report to the user:

- That the routine was started (or that the steps are with Baylee).
- For `skill-worker-r`: "Routine runs asynchronously — it works the task
  queue and opens one draft pull request per task in fairbay/ops. Nothing
  lands until a pull request is merged; each task's `owns:` line names its
  pull request."

### 5. Post-fire verification — skill-worker-r, load-bearing fires only

Skip this step for any read-only routine and any fire-and-forget or queue-only skill-worker-r fire.

Polling is for load-bearing fires only — when the fire is itself a test or the session's next move depends on the result. For everything else, the mechanical completion gate plus the next scheduled drain are the safety net: an unwatched fire cannot produce a false done, and a refused task is retried automatically.

`worker.py complete` is mechanically gated — it verifies each task's `verify:` lines against the default branch before accepting completion, and `worker.py check <id>` dry-runs the gate. When you do poll (load-bearing fires), this step catches collateral damage the gate can't see (wrong file edited alongside, gate-skipped tasks).

1. **Poll up to ~5 minutes** (every ~30s) for the run to finish — check Grove
   for its completed tasks (item 3). If still running after the cap, stop polling
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

After Step 4, give Baylee routine-specific next steps so
he knows what to do once the routine finishes. The routine runs asynchronously
— these steps tell him how to verify and collect the output.

**skill-worker-r:**
- "The routine opens one draft pull request per task in fairbay/ops and lands
  nothing. An ops session lands each one through close-at-land (or you merge
  it), and the routine's next run then completes the task."
- A draft whose task notes were corrected after it opened is repaired by an
  ops session: the routine pushes once per task and never updates its draft.
- "After a pull request is merged, come
  back to any claude.ai chat and say **'check skill drift'** or **'sync
  skills'** — I'll run `skill_sync.py` to verify the changes landed and hand
  you installable zips for any skills that were updated."
- "If skill_sync shows no drift but Grove tasks were marked done, the routine
  may have failed silently — check the session log."

**guide-r, data-draft-r, data-apply-r (MBN):**
- guide-r and data-draft-r each leave one draft pull request in MBN and land
  nothing; data-apply-r applies a draft only when its own check passes, and
  otherwise files a card for a lane A session.
- A run that stops at a precondition says which one in its summary on the
  routine's page; the lane's next session reads it (lane E for the guide, lane
  A for data).

## Queueing skill-worker tasks — verify lines are mandatory

A `routine:skill-worker` task changes exactly one file in `fairbay/ops`: a
skill's `SKILL.md` or `references/*.md`, or a `docs/**/*.md` (`worker.py precheck`
refuses anything else, and the routine then holds it for Baylee). A script, hook,
workflow or several files is an ops-session task without the tag
(chat-archive `references/encoding-gate.md`).

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

- No routine fire token is kept: none is added to the cloud environment or a
  file (CONVENTIONS "Secrets").

## Adding future routines

When a new Routine is created:

1. No credential is added. Record in its row whether a session created it
   (only then may Step 3's `fire_trigger` fire it); otherwise Run now only.
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
