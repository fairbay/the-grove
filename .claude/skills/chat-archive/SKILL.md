---
name: chat-archive
description: >
  Trigger at session end — "archive this", "wrap up", "we're done", or natural
  stopping points. Fires even mid-build. Not for mid-session status
  (→ chat-status).
metadata:
  version: "2026-10-02-01"
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

**Surface-specific steps in this skill:**
- Step 1: skill install check + confirmation batch differ by surface
- Step 3b′/3c: encoding gate routes to memory edits (chat) or CLAUDE.md (Code)
- Step 3b″: learnings-queue drain is Code-only (hook-captured corrections)
- Step 4: "view memory edits" is chat-only
- Step 10: rename chat is chat-only

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

#### 2a. Doc-drift check

If this session changed data or metrics that external-facing docs reference
(README benefit counts, state counts, category counts, API column lists,
schema descriptions), read those docs and check whether they're still
accurate. Common drift targets: `README.md` key numbers, `docs/API.md`
column references, any "Key Numbers" or "Data Scope" section. If stale,
update in the same commit as other session artifacts.

This is not a full audit — just the docs that reference quantities or facts
this session changed. Skip if the session was planning-only with no data or
code changes.

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

If `<cwd>/.claude/learnings-queue.jsonl` exists, the `capture_corrections.py`
hook queued correction / preference / positive-feedback signals from this
session's prompts (and possibly prior sessions in the same repo). Read it now:

1. Each entry is a raw finding — merge with the 3a/3b list and route through
   the encoding gate (3b′) like any other finding. `correction` entries are
   top-priority (Baylee explicitly flagged friction); `preference` entries
   usually route to CLAUDE.md or a memory-edit Grove task; `positive` entries
   confirm patterns worth keeping — usually "no encoding needed," occasionally
   a skill note.
2. Deduplicate against what 3a already caught in-conversation — the hook and
   the meta-analysis will often see the same moment.
3. After every entry has a routing decision, **delete the queue file in the
   same commit as the handoff.** A drained queue is empty. If the session ends
   without archive, entries persist to the next drain — that is the design.

Skip silently if the file doesn't exist or the surface is chat (no hooks).

#### 3b′. Encoding gate (mandatory)

Before proceeding to Step 4, verify each finding from 3a and 3b has a
routing decision. See `references/encoding-gate.md` for the routing tree.

- **Memory edit** → apply now (chat: `memory_user_edits`; Code: add to
  CLAUDE.md or create a Grove task for the next chat session to apply)
- **Skill update** → push now, or create a Grove task tagged
  `routine:skill-worker` with contractor-grade notes (file path, exact
  change, rationale)
- **Grove task** → create now
- **Adjudication item** → a source conflict, unreachable/blocked-content gap,
  or medium/low-confidence call surfaced this session that needs Baylee's
  judgment: file via `grove_create_adjudication` (question, context,
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

### 4. Session summary

**Gate: read back before summarizing.** Verify via tool calls what actually
shipped this session — read pushed files, check deploy state, view memory
edits (chat: `memory_user_edits command=view`; Code: read CLAUDE.md).
Do not summarize from memory of what you did. This prevents
narration-as-completion at the most dangerous moment (wrap-up, when
attention to process is lowest).

**Delegation for verification reads:** If verifying multiple large files
(>3K tokens each), delegate each read-back to haiku via
`delegate-mechanical`: "Read this file and confirm: (1) does it contain
[expected content]? (2) any obvious issues?" Keeps raw file contents out of
the archive context, which is already budget-constrained.

Concise, scannable:

- **What shipped** — deployed code, published content, deliverables
- **What changed** — vault updates, memory edits (list by number), skill
  modifications
- **Key decisions** — architectural choices, ideas shelved/killed, strategy
  shifts. These feed `decisions_made:` in the handoff (Step 9).
- **What didn't work** — failed approaches worth remembering
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
- `**Next step:** Apply migrations/0004_rpc.sql in the Supabase SQL Editor, then hand back for the smoke test.`
- `**Next step:** Nothing — everything handled this session.`

What this section is meant to prevent:

- A handoff doc is pushed and the response body ends with "Done." — Baylee
  has to open the handoff to learn what's next.
- Three paragraphs of summary with the next step implied via context.
- "See outstanding action items below" when there's exactly one item.

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

- Numbered steps, one action per step.
- Clickable URLs inline — the actual deep-link, not "go to Vercel".
- Group by destination when more than 3 steps touch multiple sites.
- State what Claude already completed *before* listing what Baylee needs to do.
- Before listing any item, confirm Claude can't do it directly.
- One-step handoffs don't need a list — say it in a sentence with the URL inline.
- Don't ask Baylee to paste secrets into chat; redirect to paste into the
  destination field.

### 7. (Removed — telemetry)

Session metadata is captured via the Grove project row update (Step 9b:
`last_session`, `next_actions`, `phase`) and decisions via `grove_log_decision`.
The per-session `ops/telemetry/skill-usage.yaml` append was dropped 2026-06-29 —
the self-graded compliance tally was never systematically audited and the ops
push ceremony it required didn't earn its keep.

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
- **Chat:** push the updated `watchlist.md` to ops via git-ops.
- **Code:** commit the edited copy in the same commit as the handoff. In a
  non-ops repo, also add one line to the handoff `next:` list:
  "Merge `.claude/watchlist.md` observations into `fairbay/ops/watchlist.md`
  (chat session, git-ops)." That is the merge-back route — repo copy → next
  chat session → ops source — chosen over a sync-side merge because the
  observation stays a human-readable diff and nothing merges unattended.
  `sync.py` holds (prints, does not overwrite) a repo copy whose last commit
  is not a sync commit and that has lines the ops source lacks, and exits 2,
  so an observation cannot be clobbered before it is merged. Merge the lines
  verbatim — once they are in the source, the next sync releases the copy.

### 9. Handoff + Grove write-back

Two paths depending on what this session touched:

- **Build handoff** — session involved code changes in a product repo.
  Write `HANDOFF.yaml` at the repo root. See `references/handoff-schema.md`
  for the YAML schema, CLAUDE.md maintenance, and the no-blurb convention.
- **Session-only work** (audits, skill updates, research, architectural
  decisions not tied to a single build) — no separate handoff file. The
  Grove write-back (9b below) IS the handoff. session-start reads Grove
  project rows as a primary source.

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
report the error, retry once, and note the gap in the handoff — never
silently skip.

### 10. Rename chat (chat only)

**Skip in Code / Routines** — no chat to rename.

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
- [ ] Watchlist items checked (only the ones whose condition fired)? Code: repo copy committed + merge-back line in `next:`?
- [ ] Standing rules: every ruling this session is in CLAUDE.md "Baylee's standing rules" with a superseding Grove decision?
- [ ] Chat rename suggested?

## Integration

- **← chat-status:** Mid-session checkpoints precede archive; archive is
  end-of-session only. If invoked mid-session with no close intent, defer to
  chat-status instead.
- **← session-start:** Reads the handoff this skill pushes.
- **→ session-start:** The session-start blurb produced by this skill is
  designed to trigger session-start in the next chat. The blurb must
  include the project name (so session-start can resolve the repo) and
  reference the handoff location — either the repo path or "paste this
  blurb" if the handoff itself is inline.
- **→ skill-creator-b:** Route any skill creates/edits through that skill's
  install ceremony.
- **→ grove:** Park anything that won't ship this session. Step 9b writes the
  project row + Rung-3 decisions that session-start's briefing reads next time.
