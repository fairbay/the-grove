---
name: build
description: >
  Write working code — "build this", "prototype this", "MVP this". Not for
  planning (→ architect), bugs (→ systematic-debug), deploy (→ ship-it), or
  testing (→ systematic-test).
metadata:
  version: "2026-05-24-01"
---
**Version gate:** Compare this skill's `metadata.version` against `fairbay/baylee-skills/.claude/skills/build/SKILL.md` via git-ops before doing anything else. If behind, warn once and continue. If fetch fails, skip silently.

# build — take an idea and build a working prototype

Not a plan. Not a report. A thing you can use.

## Phase 0: Read the plan (if one exists)

Before any other work, check for a plan in this order:

1. **In-context plan from architect express mode** — if the previous turn produced a `build-plan-<slug>.md`, that's the plan. Use it directly. Do not re-read from disk.
2. **`PLAN.md` in the repo** — if the repo is known, read `PLAN.md` via git-ops. This is the interview-mode artifact, pushed alongside SPEC.md.
3. **Neither exists** — fall back to SPEC.md (if present), or reason from conversation context. Valid for unplanned projects.

If a plan exists (either form): it prescribes the technical approach for each step — which APIs, data flows, validation methods. **Follow the plan's approach.** Do not re-derive from the spec.

**Build reads PLAN only, not SPEC.** The plan embeds the relevant requirements for each step. Reading both causes the executor to re-plan from the spec and ignore the plan — the exact failure mode this architecture prevents. (systematic-debug reads both because debug needs SPEC to verify what "correct" looks like; build doesn't because PLAN already encodes that per step.)

**Large plan? Delegate the extraction.** If PLAN.md is >3K tokens and you only need the approach for the current step, delegate to delegate-mechanical: "Read this plan and extract the complete approach for Step N. Return only that step's instructions." Keeps the full plan out of main context.

## Philosophy

- **Build first, refine later.** A working prototype teaches more than a spec.
- **User voice before assumptions.** Research how real people in the target domain talk about their needs. Their language, frustrations, and counterintuitive preferences shape the design. Technical instinct alone produces plausible-but-wrong defaults.
- **Mobile-first always.** Phone screen first, desktop second. 320px baseline.
- **Default to action.** When ambiguous, make a reasonable assumption and build. State the assumption. Never ask more than 2 questions.
- **Asymmetric effort.** Claude can do 1000 tasks to save the user one click — that's a good trade. Pre-generate sample data, wire up defaults, compress payloads into one-tap action links, auto-populate fields. The user is the bottleneck; Claude is not. Every tap or paste the user has to do is friction to be eliminated. When building pipeline tools (Claude → user → external service), build the programmatic input path from V1: URL hash prefill, deep links, clipboard-ready payloads. Don't design standalone and retrofit integration later.
- **Scale-appropriate, not scale-proof.** Hard limits covering 95%+ of real usage with graceful fallback beat enterprise architecture for theoretical load.

## Build guardrails

- **Research before building.** Before choosing a stack, library, or API pattern, run 1-2 web searches to confirm current conventions. Training knowledge drifts — a quick doc search catches breaking changes. Default step, not a post-failure fallback.
- **Test before delivering.** Parse JSON, require/import modules, mock data between components, curl reachable endpoints, validate schemas. State what was verified vs. what couldn't be tested.
- **Complete files only.** Never patches, diffs, or insertion instructions — always complete, pushable files. Patches require source visibility Claude often doesn't have, and partial files cause silent breakage when applied to a slightly-different baseline. If the current source isn't visible, STOP and ask for it.
- **Route pushes through git-ops's push protocol** (`git-ops/references/push-protocol.md`). Don't improvise push mechanics.
- **Durable images: generate → store → embed.** HF image tools return temp URLs that 404 within minutes. Generate freely for preview, but any image destined for a persisted artifact, page, or doc must be stored via the image-store endpoint first — embed the permanent `publicUrl`, never a raw HF temp URL. Flow + endpoint + key: `references/image-store.md`.
- **Quality tier awareness.** Most prototypes are T1 (state limits, sanity check). Quantitative or public-facing → escalate to T2+. Disclose the tier.

## Workflow

### Phase 1: Quick check (< 2 minutes)

1. **Does this already exist as a polished, free product?** (2-3 web searches max)
2. **Is the core concept clear enough to build?** If mostly, state assumptions and proceed.
3. **What's the right form factor?** (See decision guide below)
4. **What is the ONE question this prototype answers?**

### Phase 2: User voice research

**When to trigger:** When the user provides specific requirements, functional needs, or use cases. Skip if generic or user says "just build it."

**What to research (2-4 searches):** What users enjoy about the hard version of this problem, unexpected preferences contradicting technical instinct, community vocabulary, accessibility adaptations, anti-patterns that make users abandon similar tools.

### Phase 3: Plan checkpoint (complex builds only)

**When:** 3+ interacting systems or domain-specific requirements. Skip for simple tools.

Internally reframe the core requirement as "How Might We..." to expand the solution space. Output a 3-5 bullet plan. Show to user only if a genuine trade-off needs their input.

### Phase 4: Form factor decision

Pick ONE. **Default to React artifact.**

**Zero-cost check:** If the idea has `metadata.zero_cost`, default to its
recommended `arch` pattern. Prefer Cloudflare Pages over Vercel for static
sites (unlimited bandwidth). Prefer client-side storage (Dexie.js/IndexedDB)
over Supabase/Upstash. Prefer BYOK over server-side API proxy. Deviating
from the zero-cost architecture is fine but requires a stated reason.

| If the idea is... | Build it as... |
|---|---|
| Interactive tool, dashboard, data explorer | React artifact (.jsx) |
| Simple calculator, form, single-page tool | HTML artifact (.html) |
| Data processing pipeline or analysis | Python script |
| Document generator or formatter | Use appropriate skill (docx, pptx, xlsx) |
| Game or highly visual interactive | React or HTML with Canvas |

**Sandbox check before committing to artifact:** If the build needs to call external APIs (Gemini, OpenAI, Stripe, any non-Anthropic domain) or use `localStorage`/filesystem, the artifact sandbox will fail with "Load Failed" — unfixable. Skip artifact, go straight to Vite project + Vercel. Anthropic API (`api.anthropic.com`) is the exception: whitelisted in artifacts. See *Artifact sandbox limitations* at the bottom.

### Phase 5: Build

1. **Start with the core loop.** The one thing this tool does.
2. **Apply user voice insights.** When user voice contradicts technical instinct, go with users.
3. **Mobile-first layout.** 320px design. Collapsible sections. Touch targets ≥44px. No hover-only interactions. Bottom nav tabs for 3+ modes.
4. **Progressive disclosure.** Presets open, fine controls collapsed, analysis collapsed.
5. **Realistic sample data.** Pre-populate with plausible data.
6. **Self-contained.** One file. No external API calls that break.
7. **Visual polish.** Tailwind. Looks like a real product.
8. **Anticipate next steps.** Download buttons, share options, natural follow-ups.

### Phase 6: Test & fix

Before any review or delivery, verify your own work:

1. **Parse/lint.** Run the code through available validation (node -c, JSON.parse, python -c import). Fix syntax errors.
2. **Trace the happy path.** Mentally walk through the core user journey. Does each state transition make sense? Are there dead ends?
3. **Check edge cases.** Empty inputs, missing data, API failures, null returns. Add guards and fallbacks.
4. **Verify touch targets.** All interactive elements ≥44px? Spacing between adjacent tappable items sufficient?
5. **Test error states.** What happens when the API is down? When the user goes back? When data is malformed?

Fix everything you find. Do not proceed to review with known bugs.

### Phase 7: Self-review

Run adversarial review as a standard build step — not optional, not on-request.

1. **Boundary tests.** Write 5-10 pure-logic tests covering: default state, empty inputs, edge values, toggle/state logic, data shape validation.
2. **AI review.** Two paths based on what was built:
   - **Computational/artifact with testable logic (Claude.ai surface only):** Use `window.claude.complete(prompt)` in a review harness artifact (see review-panel Path 1). Keep prompts concise (~500 chars). Not available in Claude Code or Routines — use the delegate-adversarial path on those surfaces.
   - **Code, config, or non-artifact deliverables (any surface):** Route to **delegate-adversarial** for independent flaw-finding. The reviewer gets the code + criteria but none of your build reasoning — true independence.
   Fix CRITICAL and MODERATE findings. Document MINOR as known.
3. **Visual check.** If the artifact is deployed or previewable, use Claude in Chrome to screenshot at 375px and review layout, overflow, and hierarchy. If not available, self-audit the CSS for mobile issues.
4. **Validate fixes.** After applying review fixes, re-run boundary tests to confirm no regressions.

The goal: Baylee sees only a finished product. Bug-fix, quality, and best-practices feedback should never reach him — catch it all here.

### Phase 8: Functional verification — chain to systematic-test

**If you are about to declare the build "done" without functional testing, stop.** Phase 7 catches quality issues; systematic-test catches "does this actually work under real inputs." Different failure modes — both required.

After Phase 7 passes, chain to **systematic-test**. Decompose the build into testable layers (API endpoints → bash, server logic → bash, client-side state → code review, browser-only → manual instructions). Run bash tests in-session, route browser remainder to Baylee per systematic-test's routing table.

Only after systematic-test reports bash-verified do you move to Phase 9.

### Phase 9: Deliver

Present the working artifact. Minimal commentary — the prototype speaks for itself.

Include:
- What it does (1 sentence)
- What's working (short list)
- What's faked/simplified (honest)
- Assumptions made
- Research-informed decisions (mandatory when Phase 2 ran)
- systematic-test results: bash tests pass + browser tests pending or complete
- Recommended next step

## Handling idea-scout handoffs

Parse scout report for: MVP statement, build scope, target user, key insight, user voice. Use highest-scoring version. Carry forward user voice data — don't re-research. Check verdict tag: "discovery track" → plan for iterative learning. Jump to Phase 4.

## Handling iteration

- Bug fixes / cosmetic → iterate directly (or route to systematic-debug for non-trivial bugs)
- New functional requirements → 1-2 targeted user voice searches, then iterate
- "Is this worth V2?" → if the prototype disproved the core assumption, say so honestly

**Encode learnings.** If a build reveals a technical gotcha, update the relevant skill or memory edit before moving on. Describing without storing = not learning.

## Artifact sandbox limitations

**Works:** React, Tailwind, CDN packages, `window.claude.storage` (artifact-provided persistence API), `fetch` to `api.anthropic.com`.

**Does NOT work:** browser `localStorage` / `sessionStorage` (use `window.claude.storage` instead), `fetch` to external APIs (Gemini, OpenAI, Stripe, arbitrary domains), filesystem access.

**Rule:** If external API calls needed, skip artifact — go straight to Vite project via PushCraft → Vercel. Sandbox "Load Failed" errors are unfixable.

**Exception:** Anthropic API (`api.anthropic.com`) is whitelisted in artifacts.

## Integration

- **← idea-scout:** Reuse scout's user voice data.
- **← architect:** Read PLAN.md for approach guidance. The plan is the primary input, not the spec.
- **← brainstorm-engine:** "Build that" → take over.
- **→ systematic-test:** Phase 8 chain. Functional verification before declaring done.
- **→ systematic-debug:** Bugs surfaced during build or test route here for root cause.
- **→ delegate-mechanical:** Extract step-N approach from large PLAN.md.
- **→ delegate-adversarial:** Phase 7 code review for non-artifact deliverables.
- **→ idea-vault:** Auto-update vault status to "building" via git-ops.
- **→ ship-it:** Guide deployment after build passes systematic-test.
- **→ git-ops:** Route all pushes through `git-ops/references/push-protocol.md` (test → present → push → diff URL → verify).

## Style

- Move fast. Build, don't narrate.
- Comments explain *why*, not *what*.
- Respond to what the user said, not what you think they should want.
