---
name: chat-archive
description: >
  Trigger at session end — "archive this", "wrap up", "we're done", or natural
  stopping points. Fires even mid-build. Not for mid-session status
  (→ chat-status).
metadata:
  version: "2026-10-26-04"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# chat-archive — close out a session with verified state

**CRITICAL — fires even in build-mode.** The instinct to write a casual prose
recap is strongest right after shipping code, exactly when archive matters
most. Inline summaries skip the verification gate, the encoding gate, and the
handoff push — leaving Baylee to reconstruct context next session and findings
to evaporate.

**If you are about to write any prose recap of this session — "here's what we
did", "summary so far", "to wrap up", "great session" — stop.** Run the full
archive checklist below instead. The "recommend new chat" behavior on topic
shifts is handled by memory edit, not this skill.

References used by this skill (one hop):
- `references/handoff-schema.md` — YAML schema, build vs session, delivery
- `references/encoding-gate.md` — memory edit principles, finding routing
- `references/close-at-land.md` — PR hand-off: markers, owner tasks, ready, merge tap
- `references/session-record.md` — session record, random fifth, MBN batch close, agent state
- `references/lanes.md` — repos whose landing.yaml declares `lanes:`: one baton per lane, handoff-merge

**Surface-specific steps in this skill:**
- Step 1: skill install check + confirmation batch differ by surface
- Step 3b′/3c: encoding gate routes to memory edits (chat) or CLAUDE.md (Code)
- Step 3b″: learnings-queue drain is Code-only (hook-captured corrections)
- Step 4: "view memory edits" is chat-only
- Step 10: rename chat is chat-only

## Close-at-land — a draft PR's work is finished

**If you are about to mark a PR ready, stop.** Run
`references/close-at-land.md` instead: handoff and Grove markers written for the
post-merge state, `pre_ready` checks, the `Close-at-land:` commit, ready, then
one merge tap (none for ruled upkeep, which the session merges itself). It is the PR-scoped mini archive: the session goes on afterwards,
and this full archive still runs at session end (its Step 9 handoff is then the
one already in the close-at-land commit). When no other work is ongoing or
planned, the merge tap offers "Merge and archive", so one answer lands the PR
and runs this archive.

---

## Steps 1–10 — Full archive

Run this checklist in order. Each step is a tool call or a verification, not a
narration. Narrating a step is NOT completing it.

### 1. Resolve pending action items

Gather every action item given to Baylee during the session (push links, env
var setup, testing, sign-ups, repo configuration, etc.).

**Skill installation check.** If any `.claude/skills/` files were created or
modified this session, verify delivery per surface:
- **Chat:** each skill must be packaged as `.skill` (zip) and presented via
  `present_files`. Git push alone is NOT delivery — Baylee must install
  manually in Claude settings. If any were missed, package and present now.
- **Code:** skills are auto-discovered from the repo. Git push IS delivery.
  No zip packaging or manual install needed. Run `sync.py` if the
  skill needs to reach other repos.

For each item:

1. **Try to verify completion independently.**
   - Deployed code → `web_fetch` the live URL, look for version-number bump
   - Grove state → check via Grove MCP tools
   - Memory edits → `memory_user_edits` command=view (chat only; in Code,
     check CLAUDE.md or project docs instead)
   - Baylee's later reports in conversation
   - In Claude.ai chat, `/mnt/skills/user` is a read-only snapshot from
     session start — check it but don't assume uninstalled if you can't
     confirm. In Code/Routines, check `.claude/skills/` in the repo.
2. **Verifiable and done** → mark complete, don't ask.
3. **Verifiable and NOT done** → note as outstanding.
4. **Unverifiable** → add to confirmation batch.

Present unverifiable items as a batch:
- **Chat:** use `ask_user_input_v0` with Yes/No/Skip options per item.
- **Code:** ask in prose, one batch question listing all items.

Wait for answers. Then proceed.

### 2. Verify no open to-dos

Scan the *conversation* for anything promised but not delivered: code not
pushed, vault ops not executed, memory edits not applied, files not
presented, fixes not implemented. TODOs live in Grove, not in Claude's
context — this is a conversation scan only.

If anything is open: resolve it before continuing.

**Agent state.** Before naming any background agent as running, finished,
stopped or lost, run the output-file check in `references/session-record.md`
("Agent state": `stat` and the last line of its `tasks/<id>.output`); relaunch a
stopped one, take a lost notification's report from the file.

#### 2a. Doc-drift check

If this session changed data or metrics that external-facing docs reference
(README benefit counts, state counts, category counts, API column lists,
schema descriptions), read those docs and check whether they're still
accurate. Common drift targets: `README.md` key numbers, `docs/API.md`
column references, any "Key Numbers" or "Data Scope" section. If stale,
update in the same commit as other session artifacts.

Only the docs that cite what this session changed; skip for planning-only sessions.

### 3. Gather and apply learnings

Four passes. Meta-analysis is first and highest-leverage — it catches the
lessons Baylee is least likely to flag explicitly.

#### 3a. Meta-analysis — what would have made this session lower-effort?

Scan the whole session and ask: **what did I make Baylee do (or wait for)
that I could have handled myself? What ceremony didn't earn its keep? What
questions did I ask that had discoverable answers?**

Patterns worth naming when they appear:

- **Punted a verification** to a handoff or "next session" instead of
  running it right then with seeded credentials.
- **Padded a passing check** with NL/UX "just to be sure" steps after a
  programmatic check already proved the thing worked.
- **Asked a clarifying question** whose answer was discoverable from
  conversation, the repo, or a tool call.
- **Over-phased a simple task** — e.g. smoke test → reinstall → second
  smoke test, when one programmatic check sufficed.
- **Narrated a lesson** without encoding it in the same turn.
- **Repeated work** across turns that could have been one tool call.

Surface these even if Baylee didn't flag them. If Baylee DID flag workflow
friction, those are top-priority lessons — promote them aggressively.

#### 3b. Tactical notes

Reusable insights from the session — bugs hit, APIs tried, libraries
evaluated, quirks discovered, platform facts confirmed.

#### 3b″. Drain the learnings queue (Code / Routines only)

If `.claude/learnings-queue.jsonl` exists at the repo root (`$CLAUDE_PROJECT_DIR`,
else `git rev-parse --show-toplevel`), the capture hook queued correction /
preference / positive signals from Baylee's prompts in this container. Read it:

1. Each entry is a raw finding: merge with 3a/3b (dedupe) and route through the
   encoding gate (3b′); `correction` first. A `kind: error` line means the
   capture script crashed: report it in the Step 4 summary.
2. After every entry has a routing decision, delete the file (git-ignored, never
   committed; an undrained queue dies with the container).

No file: skip silently. Multi-repo and chat sessions run no hooks; 3a is the capture.

#### 3b′. Encoding gate (mandatory)

Before proceeding to Step 4, verify each finding from 3a and 3b has a
routing decision. See `references/encoding-gate.md` for the routing tree.

- **Class probe** → for every issue fixed this session, name the mechanical
  probe run over the whole set (its count), or the reason none applies, before
  the finding gets a routing decision (global rule 5).
- **Ledger (process frictions)** → a process friction not fixed in this session
  (a step, a rule, a skill, a tap that cost more than it should) seen for the
  first time is a Grove task tagged `ledger`, `seen-1`, priority 0 — not a rule,
  a skill edit or a run. Search the ledger first
  (`grove_list_tasks(tag="ledger", status="open", limit=100)`): a match is bumped
  to `seen-2` (rewrite the full tag list read back from the task) and earns
  encoding now, by the rows below. Not for: an issue fixed this session (rule 5's
  class probe), a reviewer's validator proposal (a validator rule now), a batch
  follow-up (`from-mNNNN`, one class tag), or a work item agreed in-session
  (filed at crystallization). `references/encoding-gate.md`, "The ledger".
- **Memory edit** → apply now (chat: `memory_user_edits`; Code: add to
  CLAUDE.md or create a Grove task for the next chat session to apply)
- **Skill update** → push now, or create a Grove task tagged
  `routine:skill-worker` with contractor-grade notes (file path, exact
  change, rationale)
- **Grove task** → create now; a batch follow-up (`from-mNNNN`) is refused
  without exactly one class tag (`references/encoding-gate.md`)
- **Adjudication item** → a source conflict no rule settles, an unreachable/
  blocked-content gap, or a medium/low-confidence call that is also expensive
  to reverse or needs Baylee's context (a cheap-to-reverse medium call is a
  Grove decision, never a card): file via `grove_create_adjudication` (question, context,
  discriminator, options[] each with `explanation` + `evidence_urls`) — not
  buried as prose in task notes. Each option must stand alone, with enough
  context to judge without chat history.
- **No encoding needed** → state which existing edit/skill already covers it

**Do not proceed to Step 4 until every finding has a routing decision.**
Narrating a finding in the archive output is NOT encoding it.

#### 3c. Apply

Make tool calls. See `references/encoding-gate.md` for the routing tree
and skill update conventions. Duplicate-check before adding:
- **Chat:** `conversation_search` with 1-3 content keywords.
- **Code:** check CLAUDE.md and recent handoffs for the same finding.

**Note quality gate.** Every Grove task or idea created here must stand alone —
no chat context assumed. Include: why it exists, what "done" looks like, key
decisions, and links to repos/artifacts. "Contractor-grade notes" (step 3b′)
means a reader can execute without searching past chats. Same standard as
add-to-do and grove.

#### 3d. Permissions audit (chat only)

Scan the session for every permission request, tool denial, or capability gap
that required Baylee's intervention or degraded the response. Three categories:

1. **Tool permission prompts.** Any time Claude requested access to a tool
   and Baylee had to grant it (location, calendar, reminders, etc.). Note
   which tool triggered the prompt and whether it could be pre-authorized.
2. **Missing or disconnected connectors.** Any time Claude suggested
   connecting an MCP app, searched the registry, or fell back to web search
   because a connector wasn't available. Note the connector name.
3. **Settings-gated capabilities.** Any time a response was limited because
   a setting was off — web search disabled, code execution unavailable,
   memory/past-chat search toggled off, artifacts disabled, etc.

For each item found, determine the **preventive action** — the one-time
setup step that would eliminate the permission request in future sessions:

| Gap type | Preventive action |
|----------|-------------------|
| Tool permission prompt | Grant persistent access in Claude Settings → Privacy |
| Missing MCP connector | Connect it in Claude Settings → Connected apps |
| Setting toggled off | Enable in Claude Settings → Feature controls |
| Connector auth expired | Re-authenticate in Connected apps |
| No preventive action possible | Note as inherent (e.g., first-use tool grants on iOS) |

**Output goes in Step 4** under "Permissions & setup gaps." If zero items
found, skip — don't mention permissions in the summary.

**Encoding:** If a gap recurred across multiple sessions (check
`conversation_search`), create a memory edit or Grove task to track it.
One-time grants don't need encoding — the summary is sufficient.

#### 3e. Session record (refusal: no close without it)

Before the summary, log the session-record decision (`references/session-record.md`,
"The record"): asks, refusals, merges, cache_read_m (Code: `session_report.py
--routing`; else self-reported), the rung-3 call ids, the random fifth picked
from them (printed in Step 4 and 9b), cards and tasks for Baylee. **No summary
or Next-step line until its id is in hand.** If Grove refuses twice, the record
JSON goes into the handoff's `pending_record:` (Phase 0 logs it) and the archive says so.

### 4. Session summary

**Gate: read back before summarizing.** Verify via tool calls what actually
shipped this session — read pushed files, check deploy state, view memory
edits (chat: `memory_user_edits command=view`; Code: read CLAUDE.md).
Do not summarize from memory of what you did. This prevents
narration-as-completion at the most dangerous moment (wrap-up, when
attention to process is lowest).

Verifying several large files (>3K tokens each)? Delegate each read-back to
haiku (`delegate-mechanical`) and keep only its yes/no and issues.

Concise, scannable:

- **What shipped** — deployed code, published content, deliverables
- **What changed** — vault updates, memory edits (list by number), skill
  modifications
- **Key decisions** — architectural choices, ideas shelved/killed, strategy
  shifts. These feed `decisions_made:` in the handoff (Step 9).
- **What didn't work** — failed approaches worth remembering
- **Calls to check (random fifth)** — from Step 3e, one line each with
  "reply 'reverse <id>' to undo"
- **Permissions & setup gaps** (from 3d, only if any) — what Claude
  requested permission for, what was missing, and the specific settings
  path or connector name to prevent it next time. Format each as:
  "[what happened] → **Fix:** [exact action, e.g. Claude Settings →
  Connected apps → connect X]." Baylee should be able to act on each
  item without further research.

**Retro format (when applicable):** If the session surfaced a process lesson,
state it in 3-5 sentences. Name the pattern, not the play-by-play. Then
encode it — memory edit, skill update, or Grove task — in the same turn.

### 5. Next step for Baylee — mandatory, in the response body

Regardless of whether outstanding action items exist, whether handoff was
pushed, whether anything else happened — **the response must include a
clear, labeled "Next step:" line** naming exactly what Baylee should do next.

Rules:

- Goes in the **response body** — not exclusively in a handoff doc, not
  implied, not buried.
- One line, imperative voice, specific.
- If nothing is needed: `"**Next step:** Nothing — this workstream is
  complete."`
- Clickable links inline on the same line or the line immediately following.

Good examples:

- `**Next step:** Install the updated chat-archive skill (presented above), then this workstream is closed.`
- `**Next step:** When ready, start a new chat and say "work on grove-web" — session-start picks up from HANDOFF.yaml.`

**MBN data sessions: the ruled Go rides in this line.** When the next session
is a data batch (guard verdict `continue`), the line carries the repo's
`.claude/policy.json` `harness.go` read from the file, `mNNNN` filled with the
next migration number (`references/session-record.md`, "MBN data-batch close").
Pause, escalate or a library session: the line names that work and no Go.

### 6. Outstanding action items (only when there are >1)

**Verification checklist per item (run internally, don't output):**

1. Was it completed in this conversation?
2. Did Baylee confirm it?
3. Is it observable (skill on disk, deploy working, memory edit exists)?
4. Is it still relevant (not superseded by later decisions)?

**Only list items surviving all four checks.**

Format as plain markdown — **never inside code blocks** (breaks clickable URLs):

**1.** [action] — [clickable link](https://...)

**2.** [action] — [clickable link](https://...)

If exactly one item is outstanding, promote it into Section 5's "Next step:"
line rather than a list of one. If all items are completed, omit this
section and use Step 5's nothing-needed phrasing.

For vault-related items: **verify the round-trip before listing.** Read the
relevant `ideas.json` entry back from `fairbay/idea-vault` via git-ops and
confirm the change landed. Never tell Baylee "vault updated" based only on a
push response — read it back.

**Action item formatting** (applies anywhere action items appear — Step 5's
"Next step:" line, this list, and ship-it Mode C handoffs):

- Numbered steps, one action each, with the deep link inline; group by site past 3 steps.
- State what Claude already did first; confirm Claude can't do an item before listing it.
- One step → one sentence with the URL. Secrets go into the destination field, never chat.

### 7. Cost shape

One line in the Step 4 summary and the Grove session line (9b): sub-agents by model, full
regenerations, review passes, outside-model calls/refusals/dollars. The last from Supabase
`execute_sql` (project `mqbnsjkeucvumdoqdeww`): `llm.spend_by_session` where `session` contains
this session's id, `llm.spend_by_run` per `run_id` used; none → "no outside calls".

### 8. Watchlist

The source is `fairbay/ops/watchlist.md`. `sync.py` mirrors it to
`.claude/watchlist.md` in every synced repo, so a Code session sees it without
the ops repo attached.

**Surface branching:**
- **Chat:** read `fairbay/ops/watchlist.md` via git-ops.
- **Code:** read `.claude/watchlist.md` in the repo. In `fairbay/ops` itself,
  `watchlist.md` at the root is the source — edit it directly. If the file is
  missing, the repo has not been synced since the watchlist was added: say so
  in one line and continue.

For each item whose `condition` occurred this session, answer the `check`
question and append one log line under the item:
`- YYYY-MM-DD: yes/no — brief detail`. If the item's `resolve` condition is
met (e.g. "3 observations"), move it to `## Resolved` — in the ops source
only. A repo copy gets appended lines and nothing else, so the merge back
into ops stays a clean append; the chat session that merges does the
resolving.

If no items matched, skip — don't mention the watchlist or push anything.
If items matched:
- **Chat:** land the updated `watchlist.md` on ops with git-ops `push_and_merge()` (ops lands at the push).
- **Code:** commit the edited copy in the same commit as the handoff. In a
  non-ops repo, also add one line to the handoff `next:` list:
  "Merge `.claude/watchlist.md` observations into `fairbay/ops/watchlist.md`
  (chat session, git-ops)." `sync.py` holds (exit 2, no overwrite) a repo copy
  with lines the ops source lacks until they are merged verbatim.

### 9. Handoff + Grove write-back

Two paths depending on what this session touched:

- **Build handoff** — session involved code changes in a product repo.
  Write `HANDOFF.yaml` at the repo root (with `lanes:` declared, only this lane's baton: `references/lanes.md`).
  Work in a PR: the handoff rides the close-at-land commit (`references/close-at-land.md`), not a later push, and is not
  pushed while `session_handoff.py measure` fails (S8). See `references/handoff-schema.md`
  for the YAML schema, CLAUDE.md maintenance, and the no-blurb convention.
- **Session-only work** (audits, skill updates, research, architectural
  decisions not tied to a single build) — no separate handoff file. The
  Grove write-back (9b below) IS the handoff. session-start reads Grove
  project rows as a primary source.

**MBN data session first:** append the batch to `scripts/batch/guard-record.json`,
run `node scripts/batch/guard.mjs` (with `--tasks` when a Grove dump is at hand)
and write its verdict line into HANDOFF `progress:` (lanes: the lane file's) and the batch's Grove
decision (`references/session-record.md`, "MBN data-batch close").

#### 9a. Populate `decisions_made:` (build handoffs only)

Scan the session for every Rung 3 autonomous decision — architectural choices,
scope calls, library picks, tradeoff resolutions made without Baylee's explicit
input. For each, record: `decision`, `rationale`, `alternatives`, `confidence`
(high/medium/low), `reversible` (true/false). Skip trivial implementation
details. These also get logged to Grove in 9b.

#### 9b. Grove write-back (mandatory)

Grove is the primary store of session continuity. For session-only work
this IS the handoff; for build sessions it complements the repo HANDOFF.yaml.

**Park-time breadcrumb.** If any artifact produced or referenced this session
is parked in Grove (project notes, idea notes) rather than committed to a repo,
and that artifact has an obvious expected repo path (e.g. `MISSION.md`,
`SPEC.md`, `PLAN.md`), create a stub file at that path in the repo:

```html
<!-- PARKED: [artifact name] is drafted and stored in Grove project [slug]
     (notes field). Do not rebuild — read from Grove instead.
     Deferred: [reason]. -->
```

Push the stub in the same commit as the handoff. This prevents future sessions
from concluding the artifact doesn't exist because the repo search returned empty.

1. **Project row.** `grove_list_projects(slug=<project slug>)`. If a row
   exists, `grove_update_project(id, phase=..., blockers=...,
   next_actions=..., last_session=<today>)` — pass only what changed. If no
   row exists and the session did substantive work on a named project,
   `grove_create_project` (slug, repo for code projects or omit for
   non-code, phase, next_actions; notes = planning context for non-code).
2. **Decisions.** For each Rung-3 entry in `decisions_made:` (Step 9a),
   `grove_log_decision(decision, project_ref=<'fairbay/<repo>' or slug>,
   alternatives, confidence, reversible, context, rung=3)`. Decisions are
   append-only — to correct an earlier one, pass `supersedes` with its ID
   instead of editing.
3. **Standing rules.** If a ruling from Baylee this session added or changed
   a rule, two things must already be true before the handoff commit: the
   repo `CLAUDE.md` section "Baylee's standing rules" was edited in this
   session (check the diff — one rule per line with the decision id), and a
   Grove decision was logged — with `supersedes` pointing at the earlier
   decision when the ruling replaces one. If either is missing, do it now.
   A ruling that lives only in chat or only in the decision log gets
   contradicted by the next session — that is the failure this list exists
   to stop.

Skip only if the session touched no project (pure Q&A). If Grove MCP fails,
report the error, retry once, and note the gap in the handoff (with the
session record as `pending_record:`, Step 3e) — never silently skip.

### 10. Rename chat (chat only; skip in Code / Routines)

Format: `-----[keyword1] [keyword2] [keyword3] [keyword4]`

Five dashes prefix, then specific keywords in descending relevance. Use
project/feature/tool names over generic words. Claude cannot rename
programmatically — state the recommended name.

---

## Capture integrity rule

When claiming to have captured something, update ALL relevant destinations
(handoff, vault, memory, todos) before confirming. Name exactly where each
item went. Never say "captured" after partial storage. If a destination
fails, say so explicitly.

## Internal checklist (don't output)

- [ ] Pending actions resolved?
- [ ] All code pushed / push links generated?
- [ ] All vault ops executed (and tested)?
- [ ] All `.claude/skills/` changes packaged as `.skill` and presented?
- [ ] Meta-analysis pass done (3a)?
- [ ] Encoding gate cleared — every finding has a routing decision?
- [ ] Memory edits applied — folds attempted first, count under 12?
- [ ] `decisions_made:` populated with all Rung 3 decisions from session?
- [ ] Build handoff pushed to repo root (if code changes)? Session-only → Grove write-back is sufficient.
- [ ] Grove write-back done (9b) — project row refreshed, Rung-3 decisions logged via grove_log_decision?
- [ ] CLAUDE.md updated (if architecture/stack/structure changed)?
- [ ] Summary written from verified read-backs, not memory?
- [ ] **"Next step:" line in response body?** (mandatory, even if nothing)
- [ ] Outstanding items (if >1) verified before listing?
- [ ] Permissions audit done (3d, chat only)? Setup gaps surfaced in summary?
- [ ] Cost shape line (7) in the summary and the Grove session line?
- [ ] Session-record decision logged (3e), random fifth printed with "reverse <id>"?
- [ ] MBN data session: guard-record appended, guard.mjs verdict in `progress:` and the batch decision, Go in Next-step?
- [ ] Agent states checked against their output files before naming them?
- [ ] Watchlist items checked (only the ones whose condition fired)? Code: repo copy committed + merge-back line in `next:`?
- [ ] Standing rules: every ruling this session is in CLAUDE.md "Baylee's standing rules" with a superseding Grove decision?
- [ ] Chat rename suggested?

## Integration

- **← chat-status:** Mid-session checkpoints precede archive; archive is
  end-of-session only. If invoked mid-session with no close intent, defer to
  chat-status instead.
- **← session-start:** Reads the handoff this skill pushes.
- **→ session-start:** The blurb names the project and the handoff location
  (repo path, or "paste this blurb"); Phase 0 writes the session record if
  this archive did not.
- **→ skill-creator-b:** Route any skill creates/edits through that skill's
  install ceremony.
- **→ grove:** Park anything that won't ship this session. Step 9b writes the
  project row + Rung-3 decisions that session-start's briefing reads next time.
