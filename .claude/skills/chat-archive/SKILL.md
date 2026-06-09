---
name: chat-archive
description: >
  Trigger at session end — "archive this", "wrap up", "we're done", or natural
  stopping points. Fires even mid-build. Not for mid-session status
  (→ chat-status).
metadata:
  version: "2026-06-08-01"
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
  No zip packaging or manual install needed. Run `sync-skills.py` if the
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

Three passes. Meta-analysis is first and highest-leverage — it catches the
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

#### 3b′. Encoding gate (mandatory)

Before proceeding to Step 4, verify each finding from 3a and 3b has a
routing decision. See `references/encoding-gate.md` for the routing tree.

- **Memory edit** → apply now (chat: `memory_user_edits`; Code: add to
  CLAUDE.md or create a Grove task for the next chat session to apply)
- **Skill update** → push now, or create a Grove task tagged
  `routine:skill-worker` with contractor-grade notes (file path, exact
  change, rationale)
- **Grove task** → create now
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

### 7. Telemetry

Append a session entry to `fairbay/ops/telemetry/skill-usage.yaml`
via git-ops. Mechanical logging only — no analysis, evaluation, or
editorialization. Push in the same commit as other archive artifacts.

Record:

1. **date** — today's date.
2. **type** — classify: `build`, `debug`, `scout`, `plan`, `meta`, `mixed`.
3. **skills_loaded** — every skill whose SKILL.md was read this session.
   For each, note trigger type:
   - `auto` — skill fired without Baylee naming it
   - `manual` — Baylee explicitly invoked it ("scout this", "archive")
   - `called-by-skill` — another skill's body triggered loading this one
4. **redirects** — if Baylee corrected a skill choice ("no, I meant build
   not architect"), log as `{from: architect, to: build, trigger: "build
   this after scout"}`. Empty list if none.
5. **notes** — one line only, only if something unusual happened (skill
   failed to fire, unexpected behavior, new trigger phrase discovered).
   Blank for normal sessions.

### 8. Watchlist

Read `fairbay/ops/watchlist.md` via git-ops. For each item
whose `condition` occurred this session, answer the `check` question and
append a one-line log entry: `YYYY-MM-DD: yes/no [brief detail]`.

If an item's `resolve` condition is met (e.g., "3 observations"), move the
item to the `## Resolved` section.

Push in the same commit as telemetry. If no items matched, skip — don't
mention the watchlist at all.

### 9. Handoff document

**Always generate one.** Memory captures stable facts; session context fades
between chats. A handoff saves the next instance from burning tool calls on
search reconstruction.

See `references/handoff-schema.md` for the build vs session decision, the
full YAML schema, CLAUDE.md maintenance, delivery via git-ops, and the
no-blurb resumption convention.

#### 9a. Populate `decisions_made:`

Scan the session for every Rung 3 autonomous decision — architectural choices,
scope calls, library picks, tradeoff resolutions made without Baylee's explicit
input. For each, record: `decision`, `rationale`, `alternatives`, `confidence`
(high/medium/low), `reversible` (true/false). Skip trivial implementation
details. session-start surfaces these in the next session's briefing, flagging
low-confidence and irreversible decisions for review.

**Push-failure fallback.** If the git-ops push fails (network error, timeout,
auth issue):

1. **Report the error explicitly.** Never write "skipped" without stating the
   actual error. "No repo access" without a stack trace is not acceptable.
2. **Retry once** with a fresh API call.
3. **If still failing,** update the project's Grove idea or task notes with the
   handoff YAML content via Grove MCP. Grove is always accessible. Prefix with
   `## Session Handoff (YYYY-MM-DD)` so session-start can find it.
4. **Tell Baylee** the handoff landed in Grove instead of the repo, so the
   next session knows where to look.

The handoff must reach persistent storage. Local filesystem
(`/mnt/user-data/outputs/`) resets between sessions — a file only there is
gone next session.

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
- [ ] Handoff generated and pushed (build, session, or both)? If push failed, fallback to Grove?
- [ ] CLAUDE.md updated (if architecture/stack/structure changed)?
- [ ] Summary written from verified read-backs, not memory?
- [ ] **"Next step:" line in response body?** (mandatory, even if nothing)
- [ ] Outstanding items (if >1) verified before listing?
- [ ] Telemetry entry appended to skill-usage.yaml?
- [ ] Watchlist items checked (only the ones whose condition fired)?
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
- **→ grove:** Park anything that won't ship this session.
