---
name: systematic-debug
description: >
  Fix bugs systematically — "X is broken", "isn't working", "fix didn't work",
  "still failing", "why is X happening", deploy failures, build errors. Not for
  features (→ build) or architecture (→ architect).
metadata:
  version: "2026-05-27-02"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# systematic-debug — root cause before patches

Act like an experienced incident responder: skeptical of the first plausible answer, generous with instrumentation, allergic to shipping a fix you can't prove works on the failing case.

## Phase 0: Read project context (planned projects only)

If debugging a project with documentation, read before diagnosing:

1. **PLAN.md** — prescribes the technical approach for each step. If the bug is in a planned step, the plan tells you what the step was supposed to do and how.
2. **SPEC.md** — prescribes expected behavior (acceptance criteria). Use to verify what "correct" looks like.
3. **Neither exists** — proceed directly to Phase 1 with conversation context.

Debug reads BOTH PLAN and SPEC, unlike build (which reads PLAN only). Build doesn't need SPEC because PLAN already encodes per-step requirements. Debug needs SPEC to verify what "correct behavior" looks like for the symptom under investigation — the bug may be in a step the plan thought was complete, and the spec is the source of truth for the expected outcome.

---

Random fixes waste session budget and stack technical debt. Symptom-patching feels productive but creates compounding bugs across deploys. **Core principle: find the root cause before writing a patch. No exceptions for "obvious" bugs.**

This skill exists because Claude has a documented failure mode: anchoring on a plausible first hypothesis, shipping a fix, and when it doesn't work, layering MORE fixes on the same wrong hypothesis.

## Three canonical examples

**Listing Lens cap-trim arc:** three deploys, same symptom returning. Each "fix" was a confident answer to the wrong question; the actual cause (a 3.5MB client-side cap in `trimForAnalyze`) was three layers away from where the patches kept landing. Lesson: when a fix doesn't work, the diagnosis was wrong — not the fix too weak.

**Listing Lens premium/ultra scraper tier arc:** when free-tier ScraperAPI failed on one specific listing, the instinct was to build a premium tier as rescue. Premium was tested on a listing that already worked free → declared "premium works." The question that should have been asked: *"does premium rescue the FAILING case?"* The evidence only answered *"does premium run on a working case?"* — a different question. Six hours and ~350 lines of eventually-deleted code later, the session ended with both tiers ripped out: the real root cause was architectural (Vercel IP ranges blocked by PerimeterX regardless of tier; CFNetwork TLS fingerprint strip on iOS Shortcut). No retry tier can fix that. Lesson: characterize the problem before building rescue; match evidence to the exact question being claimed.

Both share a root pattern: **confident hypothesis → fix → fix didn't work → double down instead of re-examine**.

**Listing Lens Vercel deploy failure arc:** three consecutive deploys failed at "Deploying outputs..." after build succeeded. Instead of checking what changed between the last working deploy (v7.2.0) and the first failing one (v7.2.1), the response was to web-search generic "Vercel deploy fails" symptoms — which returned platform-incident threads and anchored on "Vercel platform issue" as the explanation. Available diagnostic tools (Vercel MCP `get_deployment`, inspector URL) were not exhausted; only build logs were checked, and when those didn't show the error, the search went external. The actual error — "No more than 12 Serverless Functions on the Hobby plan" — was visible in the Vercel dashboard the whole time. v7.2.1 had added a new API endpoint, pushing the function count from 11 to 12+. Lesson: when something was working and stopped, diff the changes first — don't search the internet for what broke in your own code. Exhaust available diagnostic tools before going external.

## Phase 1: Evidence before hypothesis

**If something was previously working and stopped, start with: what changed?** Diff the last working state against the current broken state — commits, deploys, config changes, env vars, dependency updates. The change set is the most likely root cause. Do not web-search symptoms of your own code changes.

**Exhaust available diagnostic tools before going external.** When a tool returns partial info (e.g. build logs without the error message), try every other available tool — deployment status endpoints, runtime logs, inspector URLs, dashboard fetches — before searching the web. The actual error message is almost always available somewhere in the platform; web-searching generic symptoms produces generic answers that anchor on the wrong cause.

Answer all five before advancing:

1. **What's the exact symptom?** Inputs, expected output, actual output. Copy-pasteable if possible.
2. **Which layer(s) could be responsible?** List them. Don't anchor on one.
3. **What data flows through each layer?** Size, shape, timing. What are the known limits of each?
4. **What fixes have been tried already (this session OR earlier)?** What did they change? Did the symptom improve, stay the same, or change form?
5. **What single piece of evidence would distinguish between the plausible hypotheses?** If you have none, you haven't identified plausible hypotheses yet.

Record findings before proceeding. If you cannot answer all five, **KEEP GATHERING** — do not advance to Phase 2.

## Phase 2: Hypothesis (singular, falsifiable)

State ONE hypothesis. It must:

- Name a specific layer and a specific mechanism (`"trimForAnalyze in index.html caps base64 payload at 3.5MB"`)
- Predict an observable outcome if true (`"if I log totalB64 before the trim, it'll be >3.5MB on full listings"`)
- Be falsifiable in one tool call or test

**If you have multiple plausible hypotheses, you haven't finished Phase 1.** Go back. The right hypothesis is rarely a coin flip between two equally-likely options — it's the one the evidence actually points to.

## Phase 3: Test the hypothesis (instrument, don't patch)

Before writing any fix:

1. **Reproduce the symptom under instrumentation.** Add logs, print statements, curl probes — whatever surfaces the data flow at suspected layers. In claude.ai context this often means a one-off bash script that simulates the failing call.
2. **Confirm the hypothesis predicts what you observe.** If the prediction doesn't match exactly — different number, different layer, different timing — the hypothesis is WRONG. Return to Phase 1 with the new evidence.
3. **Calculate the expected fix outcome BEFORE patching.** "If I bump cap from 3.5MB to 9MB, that allows ~50 photos at typical sizes — matches the 54-photo listing."

Skip Phase 3 only if the bug is trivial (typo, off-by-one with obvious fix, syntax error) AND your hypothesis names a single line of code AND there's no way the patch could have side effects.

## Phase 4: Patch + verify

1. Write the minimal fix that addresses the named root cause.
2. Test it under the same instrumentation from Phase 3.
3. Verify the prediction held.
4. **Run the Question↔evidence match check** (see section below). Does the evidence answer the exact question the claim is making?
5. **Explicitly state what you verified vs assumed.** "Verified locally with bash: 54 photos × avg sizes = 7.9MB, fits under 9MB cap. Untested: actual production behavior with this exact listing."
6. Ship.

## Phase 4.5: When fixes fail — the cleanup gate

**If a fix you shipped didn't work and the user reports the bug is still happening, STOP.** Do not write the next fix immediately.

### Rule 1: Diagnosis was wrong

A failed fix means the diagnosis was wrong, not that the fix was insufficient. Do not double down on the same hypothesis with a "more aggressive" version. Return to Phase 1 with the new evidence — the failed fix itself is data about what the bug is NOT.

### Rule 2: Revert before next hypothesis

Before trying a new fix, audit the failed fix:

- **Strictly additive with no debt/cost?** (e.g., better headers, more defensive logging) → may stay if independently valuable
- **Adds complexity, dead code, quota cost, or technical debt?** → REVERT before the next hypothesis

State explicitly what was reverted and what was kept. The rationale for keeping anything must be "this is independently valuable," not "well, it doesn't actively hurt."

### Rule 3: Same symptom after fix = wrong diagnosis

If the symptom persists unchanged after applying a fix, the hypothesis was wrong — not the fix too weak. Do not layer another fix on the same hypothesis. Revert the failed fix (Rule 2), return to Phase 1, and re-examine the evidence as if seeing the bug for the first time.

If you find yourself in Phase 1 for a second time on the same symptom: widen the search. The root cause is likely in a different layer than where you've been looking. This is where architectural truth often surfaces (see *Characterize before rescuing* below).

If Baylee says "start over" or "re-examine the problem": treat this as a hard reset. Drop all current hypotheses and return to Phase 1 with no anchoring on prior guesses.

---

## Side-gate: Characterize before rescuing

**If you are about to build a rescue tier, fallback, retry layer, or paid alternative because something failed unexpectedly, STOP and run the 3-part characterization first.** Triggers *before* Phase 1 when the proposed action is "add a new tier" rather than "find the bug."

### Part 1: Scope

Is this failure specific to this case, or general? Run 3–5 **real samples** (not hypothetical cases — actual inputs from the domain) and classify: fails on all, some, or only edge cases? The intuition "this one case is broken" is often wrong in both directions — may be broader than you think, or narrower.

### Part 2: Solvability

Does ANY existing path work on the failing case? Before building a new tier:

- Does a different endpoint, API, or configuration already succeed?
- Does a bookmarklet / client-side / desktop path work?
- Does a different IP range, user agent, or network path pass?

If an existing path succeeds on the failing case, the fix is routing to that path — not a new tier. If no existing path succeeds, proceed to Part 3.

### Part 3: Architecture

Is this a fundamental limit (architectural truth) or a fixable bug? Examples of architectural limits:

- Server IP ranges blocklisted regardless of authentication tier
- TLS fingerprint detection at a layer below HTTP headers
- Rate limit enforced per-origin, not per-request
- Plan tier requirements that require payment regardless of code

If the limit is architectural: **accept the truth, document it, surface it honestly to the user.** Do not build another tier to paper over it.

Tier-dodges (adding premium, ultra, retry-3x when the underlying architecture rejects all of them) cost a full ship-test-rollback cycle per attempt. The premium/ultra arc above cost ~6 hours and ~350 lines of deleted code because Part 3 was skipped.

---

## Side-gate: Question↔evidence match

**Before stating "test shows X," "feature works," or "the fix is live" — confirm the evidence answers the SAME question being claimed.** Common failure modes:

- "Code ran on working case" ≠ "feature rescues failing case"
- "Premium produced output on listing A" ≠ "premium rescues listings that fail free tier"
- "Deploy succeeded" ≠ "new behavior is live for users"
- "No errors in console" ≠ "output is correct"
- "Function returned without throwing" ≠ "function did the right thing"

Before stating a conclusion:

1. **Name the question.** What exactly is being claimed?
2. **Name the evidence.** What exactly was observed?
3. **Confirm match.** Does the observation answer the question? If not, the test was on a different question — run the right test, or narrow the claim to match the evidence.

Applies with special force when reporting a fix: does the evidence show the FIX works on the FAILING CASE, or just that the code runs without erroring on a case it already handled?

---

## Integration

- **← build:** When a build phase hits a bug, systematic-debug takes over. Return to build's phase flow after resolution.
- **← systematic-test:** Bash tests that fail chain here for root-cause analysis, then back to test for re-run.
- **↔ review-panel:** review-panel catches "could this break?" systematic-debug catches "it is broken, find out why." Different tools for different moments.
- **→ git-ops:** Pushes should only ship fixes that passed Phase 4. If about to push a second fix to the same symptom without Phase 4.5 cleanup, STOP.

## Working through the gates

Work phase-by-phase. Do not skip phases unless the Phase 3 trivial-bug carve-out applies. The side-gates (*Characterize before rescuing*, *Question↔evidence match*) apply at specific moments regardless of which phase is active.

## References

- [Superpowers plugin `systematic-debugging` skill](https://github.com/obra/superpowers) — canonical reference. Their 4-phase + 3-failure-stop structure is what this adapts.
- [Anthropic Claude Code best practices](https://code.claude.com/docs/en/best-practices) — "Address root causes, not symptoms" + "The trust-then-verify gap" failure pattern.
- Listing Lens cap-trim arc — canonical example of fix-stacking on wrong hypothesis.
- Listing Lens premium/ultra tier arc — canonical example of building rescue tiers without characterizing. Net result: ~350 lines added and removed in the same session; architectural limits (Vercel IP blocklist, CFNetwork TLS strip) surfaced as the real blockers only after both tiers were ripped out.
- Listing Lens Vercel deploy failure arc — canonical example of web-searching symptoms instead of diffing changes. The 12-function Hobby plan limit was visible in the dashboard; checking what v7.2.1 added would have found it in seconds.
