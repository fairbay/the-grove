---
name: architect
description: >
  Plan before coding — "architect this", "tech spec", "PRD", "how would I build
  this". Produces SPEC.md/PLAN.md. Not for raw ideas (→ idea-scout), code
  (→ build), or deploy (→ ship-it).
metadata:
  version: "2026-06-16-01"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# architect — plan before code

Act like a senior engineer pairing on the whiteboard before anyone opens an editor. Opinionated, fast, and willing to recommend ONE path instead of surveying five.

Four artifacts live in this skill's scope:

- **Mission statement (MISSION.md)** (interview mode) — the project's north
  star. WHY this exists. Created first, before SPEC.md. Pushed to repo root.
  Authority document — SPEC.md and PLAN.md serve it, not the other way around.
- **Build plan** (express mode) — short markdown naming stack, data model,
  build sequence, risks. Chat: written to `/mnt/user-data/outputs/build-plan-<slug>.md`
  and presented. Code: written to CWD. Not pushed by default.
- **Product spec (SPEC.md)** (interview mode) — functional requirements at the repo root. WHAT to build. References MISSION.md as authority. Pushed via git-ops.
- **Technical plan (PLAN.md)** (interview mode) — maps each spec step to a technical approach: APIs, data flows, validation, pass criteria. HOW to approach it. Does NOT prescribe executor tooling. Pushed alongside SPEC.md.

Pick the mode up front. Don't blend them.

## Task-shape interrupts

**If you are about to build or modify 3+ files without a written plan, stop.** Draft a quick build sequence (express Phase 4) first — even five lines. Multi-file changes without a plan is how human action steps get dropped and skill installation ceremonies get skipped.

**If a user says "write a SPEC.md" or "spec this" and you are about to start writing one without picking a mode, stop.** Run Mode selection first. Freehand specs skip the self-check, Actor/Route fields, and review delegation.

---

## Mode selection

Ask once, early, then commit:

| User signal | Mode | Artifact |
|---|---|---|
| "architect this", "how would I build this" | **express** | `build-plan-<slug>.md` |
| "spec this", "write a SPEC.md", "PRD", "product spec" | **interview** | `SPEC.md` + `PLAN.md` pushed to repo |
| Auto-chain from idea-scout (buildable verdict) | **express** by default | `build-plan-<slug>.md` |
| User already has `SPEC.md`, wants implementation plan | **plan-only** | `PLAN.md` pushed to repo |

If ambiguous, propose: *"Quick architecture plan, or full spec interview? Express = 5 min, spec = 4-6 interview turns + pushed to repo."*

---

## Philosophy (both modes)

- **Opinionated over comprehensive.** Recommend one stack, not five. Surveying options is a way to dodge the decision the user hired you for.
- **Buildable over elegant.** Boring tech. Ship > beauty.
- **MVP-scoped.** The smallest version that validates the hypothesis. Cut features explicitly.
- **Solo-builder friendly.** One person + AI. No microservices, no complex DevOps.
- **Mobile-first defaults.** Baylee's primary device is iPhone. 320px base, touch targets ≥44px.
- **Scale-appropriate, not scale-proof.** A solution that handles 95% of real usage with a graceful fallback beats enterprise architecture for theoretical load.

---

## Mode A: Express (build plan)

Target: under 2,000 words. Output: `/mnt/user-data/outputs/build-plan-<slug>.md`.

### Phase 1 — Scope lock

- **MVP statement** (1 sentence): `A [type] that lets [user] do [action] so they can [outcome].`
- **In-scope features** — 3-5 max
- **Explicitly out of scope** — name them so they don't creep back
- **Success metric** — one measurable thing

### Phase 2 — User flow

Happy path only:

```
[Entry] → [Step 1] → [Step 2] → [Core value moment] → [Exit/next]
```

For each step: what the user sees/does, what the system does, where it could break.

### Phase 3 — Technical architecture

**Research before asserting.** Run 1-2 web searches on current conventions (export syntax, API shape, platform docs) before recommending a stack. Training knowledge drifts; a quick doc search catches breaking changes. If research returns long API docs or platform references (>3K tokens), delegate summarization to delegate-mechanical — extract only the facts relevant to the architecture decision, keep the raw docs out of main context.

**Stack recommendation.** One stack, 2-3 sentence justification. Defaults:

- **Web app:** Vite + React + Tailwind on Vercel. Upstash KV or Postgres if state needed.
- **Static tool:** Single HTML file or Vite-built static, Cloudflare Pages preferred (unlimited bandwidth). Vercel if Next.js SSR required.
- **iOS app:** Expo + React Native, EAS Build. SwiftUI widget extensions via `@bacons/apple-targets` when needed. Apple Developer $99/yr is sunk cost — do not count.
- **Data-heavy:** Python + pandas/SQLite, Streamlit/Gradio if UI.
- **Zero-cost idea (has `metadata.zero_cost`):** Default to the `arch` in zero_cost metadata. Prefer Cloudflare Pages, client-side storage (Dexie.js/IndexedDB/OPFS), browser-native APIs, BYOK for AI features. Deviating requires a stated reason in the plan.

**Data model.** 3-5 entities max. Columns: Entity / Fields (`field: type`) / Relationships.

**API surface** (if any). REST, obvious naming. No GraphQL unless compelling.

**File structure.** Flat. Deep nesting = over-engineering.

**Pipeline integration** (if tool sits between Claude and external service). Default pattern: compressed JSON in URL hash (`#pf=<lz-string>`), parsed on mount. Audit every user-facing step — if it requires typing something Claude already knows, embed it in the link.

### Phase 4 — Build sequence

5-8 linear steps. Each:

```
Step N: [Title] (~X hours)
What: [What you're building]
Output: [What exists when done]
Actor: claude | baylee | both
Route: [skill name, if step should use a specialized skill]
Key decisions: [Choices to make]
```

Rules:

- Start with data model + basic CRUD.
- Core value loop working before polish.
- Auth is NOT step 1 (unless auth IS the product).
- Deploy early — step 2 or 3 at latest.
- Honest time estimates.
- **Include human action steps.** If a step requires Baylee's hands (install a skill in Claude settings, set an env var, click a dashboard button, approve a deploy), mark it `Actor: baylee`. These cannot be skipped or collapsed into a Claude step — real work with real dependencies.
- **Route to specialized skills.** If a step falls in another skill's domain, name it: `Route: skill-creator-b` for skill modifications, `Route: ship-it` for deployment, `Route: git-ops` for repo pushes. Prevents the builder from ad-hoc reimplementing a workflow that already has a tested skill path.
- **Consumer-facing UI → Gemini.** If the project has a UI and audience type = `consumer-facing`, at least one step should route UI component design to Gemini (AI Studio, Stitch, or MCP server). Claude handles data layer, logic, and integration. See `references/ux-quality-gates.md § Model Routing`.

### Phase 5 — Risk & AI collaboration

- **Technical risks:** "The hard part is X — here's how to handle it."
- **Scope creep triggers:** "You'll be tempted to add Y — don't."
- **Dependencies:** external APIs, datasets, approvals.
- **Cost at MVP scale:** monthly run cost. If idea has `metadata.zero_cost`
  with tier 1 or 2, the plan MUST preserve $0 hosting — any decision that
  breaks the zero-cost guarantee (adding a database, server-side API proxy,
  paid API without BYOK) must be called out explicitly as a trade-off.
- **AI does well:** boilerplate, CRUD, UI components, tests.
- **Human decides:** UX flow, business logic edges, copy.

### Self-check before delivery (express mode)

- [ ] Plan is under 2,000 words (if over, you're drifting into interview-mode territory)
- [ ] Every step has `Actor: claude | baylee | both`
- [ ] At least one `Actor: baylee` step if plan involves: skill install, env var setup, deploy approval, dashboard action, or any action Claude can't do
- [ ] Every `Route:` field references a real skill name
- [ ] Steps involving skill file modifications route through `skill-creator-b`
- [ ] Build sequence is linear — no step depends on a later step

### Auto-chain after express mode

Default: flow directly into the build skill. State *"Plan complete — chaining
to build."* and proceed.

**Stop-conditions (two qualifiers — flow through on everything else):**
1. The user said "just architect" or "plan only."
2. The plan contains a **pending Rung-4 decision** — a call that's
   irreversible, mission-level, or explicitly flagged for Baylee's input.
3. The plan involves **irreversible side effects on existing assets**:
   forward-only migrations on existing tables, deletes of existing repos/data,
   pushes to already-live-deployed repos, spending money, or external comms.

If neither qualifier (2) nor (3) applies, chain immediately. On flow-through:
render the plan inline (non-blocking), log any Rung-3 decisions to Grove, and
note that Baylee can redirect mid-build.

**Hand-off mechanics:** Express mode produces `build-plan-<slug>.md` in `/mnt/user-data/outputs/`, NOT a repo-level `PLAN.md`. When auto-chaining, the plan content is in-context — pass it directly to build. Build's Phase 0 should use the in-context plan rather than reading PLAN.md via git-ops (which won't exist for express-mode projects). If the user asks to push the plan to the repo, route through git-ops as `PLAN.md` — but that's a user-initiated action, not the default.

---

## Mode A′: Plan-only (PLAN.md from existing SPEC.md)

When the user already has a `SPEC.md` and wants an implementation plan without
re-interviewing. Produces a proper `PLAN.md` pushed to the repo — not a
temporary build-plan file.

### Workflow

1. **Read existing SPEC.md** from the repo via git-ops. Also read MISSION.md
   if present.
2. **Research before planning.** Run 1-2 web searches on current conventions
   for the project's stack (same as express Phase 3).
3. **Generate PLAN.md** using the interview-mode Phase 6 template and rules.
   Every spec section maps to build steps with technical approaches. All Phase 6
   rules apply: Actor fields mandatory, Route fields for specialized skills,
   consumer-facing UX steps if applicable.
4. **Self-check** using the Phase 6 PLAN.md checklist.
5. **Push** `PLAN.md` to repo root via git-ops alongside SPEC.md.
6. **Auto-chain to build** unless the user said "just plan."

---

## Mode B: Interview (product spec)

Produces `SPEC.md` at the repo root. Target 400-900 lines. Under 300 means something's missing; over 1,200 means it's bleeding into architecture territory.

### Phase M — Mission interview (first, before spec)

MISSION.md is the project's north star — it answers WHY before SPEC.md answers
WHAT. Create it first. Five questions, one turn:

1. **Why does this exist?** — The problem or opportunity in 1-2 sentences.
2. **Who is it for?** — Named person or specific audience segment.
3. **What does success look like?** — One measurable north-star outcome.
4. **What are we NOT doing?** — 2-3 explicit anti-goals that bound the project.
5. **What principles guide tradeoffs?** — 2-3 rules for resolving competing
   priorities (e.g. "speed over polish", "privacy over convenience").

Pre-fill from memory and conversation context. Present as proposals to correct,
not blank questions. If the project already has a `MISSION.md`, read it via
git-ops and ask what's changed — don't re-interview from scratch.

**Mechanism vs feel.** Implementation and mechanism choices (data source,
content assembly, storage, libraries) are builder calls — decide and state
them, don't interview. Interview questions are reserved for product feel,
audience, and success criteria, where Baylee's answer changes the build.

**MISSION.md template:**

```markdown
# [Project] — Mission
**Why this exists:** [1-2 sentences: the problem or opportunity]
**Who it's for:** [Named person or specific audience]
**What success looks like:** [One measurable north-star outcome]
**What we are NOT doing:** [2-3 anti-goals, bulleted]
**Tradeoff principles:** [2-3 rules, bulleted]
```

Push to repo root immediately — don't wait for the spec.

### SDD level

Default to **spec-anchored** (spec + code both in repo, both version-controlled, spec updates when behavior changes). Only ask explicitly if the project has unusual rigor requirements (safety-critical, contract-bound).

### Budget

5-7 interview *turns* (a turn batches 2-3 questions). One turn for mission,
4-6 for spec. Use `ask_user_input_v0` with single_select or multi_select
options where possible; reserve free text for identity and flow.

**Widget questions must be self-contained.** Carry the proposal being
confirmed in the question text or its options. Prose preceding a tool call
can collapse under tool-activity summaries in the claude.ai UI — every
widget question must make sense as the only thing on screen.

### Phase 0 — Bootstrap

1. Pull context — vault entry, existing repo README/code via `git-ops` read, recent conversation.
2. State what you have in 1-2 lines.
3. Fire Phase 1 questions.

Opening template:

> Got it — spec interview for **[Project]** (`[repo]`).
>
> Going in: [what you pulled, or "starting fresh"].
>
> I'll ask in batches of 2-3 across four phases: **what+why**, **constraints**, **data+behavior**, **quality contract**. Spec-anchored — spec and code both live in the repo.
>
> Starting with **what+why** —

### Phase 1 — What + Why (1-2 turns)

Extract:

- **Identity** — `"[Type] that helps [user] do [action] so they can [outcome]"`
- **Primary user** — name people specifically, not "users"
- **Problem statement** — concrete pain, 2-4 sentences
- **Non-goals** — at least 2
- **Success criteria** — 2-4 measurable statements
- **Audience type** — `internal` (personal tool, dashboard) or `consumer-facing` (public users). Gates UX quality steps in Phase 3 user stories, Phase 6 UX plan steps, and ship-it Phase 2.5. Default: infer from primary user. If Baylee is the only user, it's internal.

**Pre-fill defaults from memory:** user = "just me" or "me + family"; platforms = iPhone primary, PC secondary; hosting = Vercel.

### Phase 2 — Constraints (1 turn)

- **Platforms** — web mobile, web desktop, iOS native, Chrome extension, CLI
- **Hard constraints** — no login, no data leaves device, free tier only, offline support, etc.
- **Dependencies** — external APIs, datasets
- **Risk flags** — anything that could kill the project

### Phase 3 — Data + Behavior (1-2 turns)

- **Entities** — 2-5 core objects and their fields
- **Data flow paths** — for each data type entering the system, trace: input method → processing/transformation → where it lands in the output. If different types need different processing (images vs documents, structured vs unstructured), make the distinction explicit. "All types go through the same pipeline" is a design decision that should be stated and validated, not a silent default.
- **Happy-path user flow** — 3-7 numbered steps
- **Functional requirements** — 8-15 FR-### statements, each "System MUST [verb] [object]"
- **Edge cases** — at least 2 named failure modes with expected behavior

**User stories (consumer-facing only — adds 1 interview turn).** Skip for internal tools. After extracting entities and user flow, propose 3-4 named personas and draft 5-8 user stories with acceptance criteria. Present to Baylee for correction — he knows whether the personas reflect real behavior. Stories drive FRs, so revise FRs after story alignment. Format, quality framework, and common LLM failure modes in `references/ux-quality-gates.md`.

Propose rather than ask blind: after Phase 2 you should be able to *draft* FRs and entities and ask Baylee to correct.

### Phase 4 — Quality contract (1 turn)

- **Acceptance criteria per FR** — 1-2 observable "done when" conditions each
- **Measurable success (SC-###)** — 3-5 metrics
- **Explicit out-of-scope for v1** — at least 3 killed features with "revisit when / no / v2"
- **Assumptions (unvalidated)** — what we're betting on without evidence
- **Rules for future AI changes** — what future sessions must preserve

### Phase 5 — Draft + review

**Spec review via delegation:** After drafting the spec, delegate review to `delegate-adversarial` — the reviewer gets the spec + acceptance criteria but none of the interview context. Catches gaps the interviewer is blind to. Especially valuable for specs >500 lines.

`delegate-adversarial` is the default review path. Escalate to `review-panel` (multi-agent) only when the project is high-stakes (regulated, contract-bound, multi-month commitment) and Baylee asks for the panel by name. Adversarial single-reviewer catches most spec gaps at a fraction of the cost.

Write full `SPEC.md` to `/home/claude/SPEC.md` using the template below.
Surface unresolved items with `[NEEDS CLARIFICATION: ...]` markers inline.
- **Chat:** present via `present_files`.
- **Code:** write to repo root; present inline summary. If >3 markers, do another interview turn; if 0-3, ask Baylee to resolve inline.

### Phase 6 — PLAN.md

After spec is accepted, generate `PLAN.md` — the implementation roadmap. Each spec section maps to one or more build steps with a technical approach.

```markdown
# [Project] — Implementation Plan

## Steps

### Step 1: [Title]
**What:** [What's being built or done]
**Approach:** [Technical approach — which APIs, data flows, validation]
**Actor:** claude | baylee | both
**Route:** [Skill to use, e.g. skill-creator-b, ship-it, git-ops. Omit if none.]
**Pass criteria:** [How to verify this step is done]
**Specs covered:** FR-001, FR-002

### Step 2: ...
```

**Actor field is mandatory.** Any step requiring Baylee's hands (install a skill, set an env var, approve a deploy, click a dashboard button) must be marked `Actor: baylee`. Real dependencies, not elidable.

**Route field prevents ad-hoc reimplementation.** Skill modifications route through `skill-creator-b`. Deployments route through `ship-it`. Repo pushes route through `git-ops`.

**Consumer-facing UX steps.** When audience type = `consumer-facing`, include these steps at the specified insertion points:

1. **UX design intent** (insert after data layer / before UI build). Review user stories against the proposed UI structure. For each story, trace the user's path. Flag any story requiring >3 taps to reach the core value moment. `Actor: claude`. Pass criteria: every story has a traceable UI path.

2. **UI component generation via Gemini** (insert at UI build time). Gemini consistently outperforms Claude on visual design quality (WebDev Arena, dashboard benchmarks, landing page tests). Route UI component design to Gemini — Claude handles data layer, business logic, and integration. Surfaces: Google AI Studio (paste spec + user stories + reference screenshots), Gemini MCP server (Claude Code calls Gemini), or Google Stitch (wireframe → polished UI). Claude integrates Gemini's output with data/logic and handles architectural coherence. `Actor: both` `Route: see references/ux-quality-gates.md § Model Routing`.

3. **Heuristic UX review** (insert after UI is built / before deploy). Cross-model review of the built interface. Use domain-specific heuristics (not just Nielsen's generic 10) — see `references/ux-quality-gates.md` for health-literacy, civic-tech, and e-commerce heuristic sets. Plus Flesch-Kincaid readability (≤8th grade for public-good, ≤10th for dev tools), plain language scan (no jargon in user-facing text). **Surface routing:** In chat — output a copy-paste prompt for Google AI Studio with screenshots. In Claude Code — use `delegate-adversarial` with URL Context. `Actor: claude | baylee`. Pass criteria: no severity-3 heuristic violations, UI text at target grade level.

4. **Device walkthrough** (insert before launch). Walk every user story on target device(s) — mobile-first for Baylee's projects. `Actor: baylee | both`. Pass criteria: every story completes on mobile, touch targets ≥44px, no horizontal scroll.

Push `PLAN.md` alongside `SPEC.md` in the same commit.

### Self-check before delivery (PLAN.md)

- [ ] Every step has `Actor: claude | baylee | both`
- [ ] Every `Route:` field references a real skill name
- [ ] Steps involving skill file modifications route through `skill-creator-b`
- [ ] If consumer-facing: Gemini UI generation step present
- [ ] If consumer-facing: heuristic UX review step present with surface routing
- [ ] If consumer-facing: device walkthrough step present with `Actor: baylee | both`
- [ ] Pass criteria are specific and verifiable (not "looks good" or "works well")

### Phase 7 — Push + vault update

**Deferred-layout breadcrumb.** When a layout or storage decision is deliberately
deferred (e.g. "park in Grove project notes until repo restructure", "layout TBD"),
create a stub file at the artifact's expected repo path before closing the session:

```html
<!-- PARKED: [artifact name] is drafted and stored in [location: Grove project <slug>,
     notes field / Drive / etc.]. Layout deliberately deferred: [reason].
     Do not rebuild — retrieve from the noted location instead. -->
```

Push the stub so a future repo search at the expected path finds a pointer, not silence.

Route through **git-ops**:

- File: `MISSION.md` + `SPEC.md` + `PLAN.md` at repo root
- Commit: `spec: initial mission + product spec` (or `spec: update <section>` for revisions)
- Target: the project's repo

Update the vault (`fairbay/idea-vault` `ideas.json` + matching `archive/<slug>.md`):

- Add `spec_url` pointing to the raw SPEC.md on GitHub
- Update status to `spec-complete` if it was earlier
- Do not touch scores — spec writing doesn't change idea quality

### SPEC.md template

```markdown
# [Project] — Product Spec

**Status:** draft | active | deprecated
**SDD Level:** spec-anchored
**Mission:** See [MISSION.md](MISSION.md) (authority for why this project exists)
**Created:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD
**Repo:** fairbay/...

---

## 1. What + Why

### Identity
[One sentence: "Type that helps user do action so they can outcome"]

### Primary User
[Named, specific]

### Problem Statement
[Concrete pain, 2-4 sentences]

### Non-Goals
- ...

---

## 2. Constraints

### Platforms
- ...

### Hard Constraints
- ...

### Dependencies
- ...

### Risk Flags
- ...

---

## 3. Data + Behavior

### Entities
| Entity | Fields | Notes |
|---|---|---|
| ... | ... | ... |

### User Flow (Happy Path)
1. [Entry]
2. [Step]
3. [Core value]
4. [Exit]

### User Stories (consumer-facing only)
- **US-001**: As a [persona], I want to [action], so that [outcome].
  - *Given* [context], *when* [action], *then* [result].
- **US-002**: ...

### Functional Requirements
- **FR-001**: System MUST ...
- **FR-002**: System MUST ...

### Edge Cases
- **When X fails:** [behavior]

---

## 4. Quality Contract

### Acceptance Criteria
- **FR-001**: Done when [observable].
- **FR-002**: Done when ...

### Success Criteria
- **SC-001**: [metric]

### Out of Scope (v1)
- [Feature] — revisit when X
- [Feature] — no

### Assumptions (unvalidated)
- ...

### Rules for Future Changes
- All changes must preserve FR-###, FR-###.

---

## 5. Open Questions
- [NC-001]: ...

---

## Changelog
- **YYYY-MM-DD**: Initial spec.
```

### Self-check before delivery (interview mode)

- [ ] MISSION.md created and pushed (or existing MISSION.md reviewed)
- [ ] SPEC.md header references MISSION.md as authority
- [ ] Identity sentence is concrete (no "leverage", "ecosystem", "seamless")
- [ ] Primary user is a named person, not "users"
- [ ] Problem describes pain, not a solution
- [ ] ≥2 non-goals
- [ ] ≥2 hard constraints
- [ ] Entities table: 2-5 rows
- [ ] Each input type has its processing path traced (input → transform → output)
- [ ] User flow: 3-7 numbered steps
- [ ] FRs: 8-15, all start with "System MUST", all have matching acceptance criteria
- [ ] Edge cases: ≥2 named
- [ ] SCs: 3-5, all measurable
- [ ] Out of scope: ≥3 explicitly killed
- [ ] `[NEEDS CLARIFICATION]` count: ≤3
- [ ] Under 900 lines
- [ ] If consumer-facing: user stories present, ≥5, Baylee reviewed personas, each has acceptance criteria, QUS-checked (Independent, Unique, Unambiguous — the 3 criteria LLMs fail most)
- [ ] If consumer-facing: PLAN.md includes UX design intent + Gemini UI generation + heuristic review + device walkthrough steps

---

## Interview style (both modes)

- Batch questions 2-3 per turn. Mobile-first. In chat, use
  `ask_user_input_v0` for multiple-choice questions where possible.
- Pre-fill defaults from memory. Don't ask about stack; it's likely Vite+React+Tailwind+Vercel.
- Propose rather than prompt blind. "Here's what I'd write — correct it" beats open-ended questions.
- Say when you're inferring. "Assuming X based on [source]" beats a silent leap.
- Name the project in every opening line.
- **Product questions only — not architecture questions.** Only ask questions the product owner can answer: what the system should do, user preferences, scope decisions, trade-offs between competing goals. Architecture questions (data structures, client vs server, schema design, embedded vs normalized, processing location) are builder decisions — make them yourself and state your reasoning in the spec. If you find yourself about to ask a how-to-implement question, stop — that's your call, not the product owner's.

---

## Edge cases

- **Fresh idea, no prior context:** fine. Full phases from scratch.
- **Existing repo with code but no spec:** read the code first via git-ops, use it to propose the spec, then interview to correct.
- **Updating an existing spec:** read it, ask what's changing, update only affected sections, bump the changelog.
- **Post-build spec update:** when building or testing reveals a design assumption was wrong, update the spec in the same session. Use a "validated/invalidated" split in the Assumptions section to record what the build proved or disproved. This is not scope creep — it's spec maintenance.
- **Feature spec (not whole app):** use `FEATURE-SPEC-<name>.md` in repo, reference parent `SPEC.md`.
- **User gives contradictory answers:** name it directly. "Earlier X, now Y — which is it?"
- **Interview stalls:** offer a concrete starting point ("here's what I'd write — tell me what's wrong") rather than more open questions.

---

## Integration

- **← idea-scout:** Pull one-liner, user voice, verdict.
- **← idea-vault:** Pull vault entry for context; update vault after delivery.
- **→ build:** Auto-chain in express mode unless user said "just architect".
- **→ ship-it:** May specify deployment target for downstream planning.
- **→ git-ops:** All SPEC.md / PLAN.md pushes and vault updates route here.
- **→ delegate-adversarial:** Spec review after Phase 5 draft.
- **→ delegate-mechanical:** Summarize long platform docs returned by Phase 3 research.
- **→ review-panel:** Tier-3 review of the spec itself is appropriate for high-stakes projects. Invoke after Phase 5 if the user flags it.

---

## Handoff to future sessions (interview mode only)

End the delivery message with:

> **For future sessions:** The mission is at `[repo]/MISSION.md`, the spec at `SPEC.md`, and the plan at `PLAN.md`. MISSION.md is the authority — SPEC.md and PLAN.md serve it. Any change to behavior should update `SPEC.md` in the same commit as the code change (spec-anchored rule). New work on this project: read PLAN.md first (build skill), or SPEC.md if no PLAN exists. If the build drifts from MISSION.md, flag it.

This trains future Claude sessions and Baylee himself to treat SPEC.md / PLAN.md as the first read on this project.
