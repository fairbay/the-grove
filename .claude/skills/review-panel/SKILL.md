---
name: review-panel
description: >
  Multi-agent or cross-model review — "panel review",
  "calibrate scores", "audit my vault". Auto-runs build Phase 7.
  Not for isolated checks (→ delegate-analytical/adversarial).
metadata:
  version: "2026-06-16-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# review-panel — multi-agent adversarial review

Two modes. Both adversarial by design: the goal is that Baylee never receives
feedback Claude could have caught first.

| Mode | Trigger | What gets reviewed |
|---|---|---|
| **A: Artifact** | "panel review", build Phase 7 | code / computation / UX |
| **B: Scores** | "calibrate scores", "audit my vault", batch re-scores | vault scoring consistency |

## Collision zone with delegate-adversarial

Both find flaws. The split is structural, not topical.

| User says / context | This skill | delegate-adversarial |
|---|---|---|
| "panel review" | yes | no |
| "Gemini review" | no | yes |
| "calibrate scores", "audit vault" | yes (Mode B) | no |
| build Phase 7 on Claude.ai (artifact) | yes (Path 1) | no |
| build Phase 7 in Claude Code or Routines | no | yes |
| "tear this apart" inline, single pass | no | yes |
| "security audit" inline | no | yes |
| Architecture critique, spec gap-find | no | yes |

Rule of thumb: **iterative or multi-agent → here. Single-pass flaw list →
delegate-adversarial.** A user who says "panel" wants multiple voices; a user
who says "tear this apart" or "Gemini review" wants one decisive critic.

## Quality tiers (reference)

This skill owns T3.

- **T0:** Chat, brainstorm, Q&A — no formal review.
- **T1:** Plans, research, writing — standard diligence.
- **T2:** Quantitative work, scoring — boundary-test claims, web-verify facts.
- **T3:** Adversarial panel (this skill). 3-round cap.

Production-facing specs and architecture docs default to T3 before presenting
to Baylee.

---

## Mode A: Artifact review

Standard build step (Phase 7) AND on-demand. Three paths; pick by deliverable
type and surface.

| Path | Use when | Why |
|---|---|---|
| **1. Harness (Claude-reviewing-Claude)** | Computational artifact on Claude.ai | Automated, zero user effort |
| **2. Gemini handoff** | Visual/UX-heavy, public-facing, belt-and-suspenders | True cross-model independence |
| **3. API-delegated (opus)** | Non-artifact deliverable (code, spec, prose) — any surface | True independence + no harness needed |

Path 1 is default for artifacts with testable logic on Claude.ai. Path 3 is
default for non-computational deliverables (code, specs). Path 2 is opt-in for
visual review or when Path 1/3 finds zero issues on something complex.

---

### Path 1: Claude-reviewing-Claude harness

Companion artifact runs boundary tests and sends results to a fresh Claude
instance via `window.claude.complete()`. Available only on Claude.ai (the API
isn't accessible from Claude Code or Routines — use Path 3 there).

#### Critical constraints (learned from failures — don't re-derive)

1. `window.claude.complete(promptString)` takes a **raw string**, not an
   object. `{prompt: "..."}` returns empty string silently.
2. Only works inside `useEffect(fn, [deps])` on mount. Hangs from click
   handlers or timers.
3. Artifacts have **no external network access** (fetch is sandboxed).
4. The harness auto-runs when opened — no init buttons.
5. Cache results in `window.storage` so re-opening shows cached results.
6. `navigator.clipboard.writeText()` may fail in sandbox — fall back to
   textarea + `document.execCommand('copy')`.
7. `window.location.reload()` does not work. Use a `runKey` state variable in
   the `useEffect` dependency array for re-run.
8. `setPhase("done")` **before** `await window.storage.set(...)`. If cache
   write hangs, the UI must still advance. Wrap cache writes in try/catch.
9. Keep prompts ~500 chars. `window.claude.complete()` has ~8K char response
   limit. Request "max 5 issues, one sentence each" to avoid truncated JSON.
   Handle truncation by stripping backticks and attempting bracket-closing
   repair.

#### Architecture

```
Claude builds artifact → generates review harness artifact
User opens harness → useEffect fires:
  1. Check window.storage for cached results → show if exists
  2. Run boundary tests (instant, pure JS)
  3. Build review prompt (completeness + traceability + severity)
  4. window.claude.complete(prompt) → fresh Claude (~10-30s)
  5. Parse JSON, display, cache
  6. window.claude.sendConversationMessage(summary) → chat thread
```

#### Prompt quality — the three pillars

Prompt quality IS review quality.

**Pillar 1 — Completeness verification.** Before sending, verify the reviewer
has enough information to evaluate every claim:

1. List every claim (formulas, corrections, features).
2. Map claims to variables — which output variables demonstrate each?
3. Trace dependencies — for each displayed variable, what intermediates does
   it depend on? Include intermediates needed to make the output interpretable.
4. Cross-check — can a reviewer seeing ONLY the formatted output verify every
   claim? If anything is unverifiable, add variables.

Principle: for any `X` shown in output, if `X = f(Y)` and `Y` isn't obvious,
include `Y`. Missing intermediates are the #1 source of false-positive
"this is wrong" reviews — the reviewer can't see the path.

**Pillar 2 — Formula traceability.** For computations with branching logic,
include a formula label showing which path ran:

```
SPL at 10ft = 187.8 dB  [formula: Rayleigh pitot (P_ratio=5.928)]
```

Eliminates "wrong formula was probably used" false positives. Apply to regime
switches, conditional corrections, fallback paths.

**Pillar 3 — Severity calibration.** Without definitions, the reviewer
defaults to CRITICAL for everything. Include in the prompt:

```
SEVERITY CALIBRATION (follow strictly):
- CRITICAL = computation produces numerically wrong results. Formula wrong or
  code doesn't match formula.
- MODERATE = notation, documentation, or presentation issues that could cause
  confusion but don't affect computed values.
- MINOR = cosmetic. Floating-point display artifacts (-0.00 vs 0.00),
  rounding, style.

VERIFICATION METHODOLOGY:
Before claiming a result is wrong, compute the expected value yourself using
the stated formulas. Check formula labels to confirm code path.
```

#### Building the harness

1. **Extract computation engine.** Copy pure-logic functions from the
   artifact, strip React/UI. Clamp floating-point noise near zero:
   `Math.abs(x) < 1e-9 ? 0 : x`.
2. **Write boundary tests (4-6 cases).** Defaults, all-min, all-max, mixed
   extremes, domain-specific edges. Check for NaN, Infinity,
   negative-where-invalid.
3. **Format test output** with all three pillars applied.
4. **Build prompt:**

```
[Domain] review. Find errors only.

CONTEXT: [What this is; rigor level expected]

Do NOT flag: [premise, stated simplifications, style, missing features]
DO flag: [wrong formulas, arithmetic errors, physical impossibilities,
inconsistencies between stated formulas and displayed results]

[SEVERITY CALIBRATION block — see Pillar 3]
[VERIFICATION METHODOLOGY block]

CLAIMS: [numbered list]
FORMULAS: [the actual math]
CONSTANTS: [...]

Results:
[FORMATTED OUTPUT — all variables, formula labels, expected values where
hand-computable]

JSON only, no backticks:
{"issues":[...], "summary":"...", "approved":bool, "false_positive_risk":"HIGH|LOW"}
```

5. **Fire on mount with re-run support:**

```javascript
const [runKey, setRunKey] = useState(0);

useEffect(() => {
  (async () => {
    try {
      const cached = await window.storage.get('review-<id>');
      if (cached?.value) {
        setReview(JSON.parse(cached.value));
        setPhase("done");
        return;
      }
    } catch { /* no cache, proceed */ }

    const tests = runBoundaryTests();
    const prompt = buildReviewPrompt(tests);
    setPhase("reviewing");

    // CRITICAL: pass raw string, NOT object.
    const response = await window.claude.complete(prompt);
    let parsed;
    try {
      const text = typeof response === 'string' ? response : JSON.stringify(response);
      const clean = text.replace(/```json|```/g, '').trim();
      parsed = JSON.parse(clean);
    } catch {
      parsed = { issues: [], summary: 'Parse error — raw: ' + response, approved: false };
    }

    setReview(parsed);
    setPhase("done");
    try { await window.storage.set('review-<id>', JSON.stringify(parsed)); } catch {}

    const critCount = parsed.issues.filter(i => i.severity === 'CRITICAL').length;
    const summary = critCount
      ? `Review found ${critCount} critical issues`
      : 'Review passed — no critical issues';
    try { await window.claude.sendConversationMessage(summary); } catch {}
  })();
}, [runKey]);
```

#### Processing results

- **Parse JSON** — strip backticks, regex fallback.
- **Triage:**
  - CRITICAL → fix immediately
  - MODERATE → present, ask which to fix
  - MINOR → note, fix opportunistically
  - `approved: true` with no CRITICALs → clean bill, move on
- **False-positive check** — if `false_positive_risk: "HIGH"`, the prompt
  usually has a Pillar 1 or 2 gap (missing context), not a bad review. Re-check
  the prompt before re-prompting.

---

### Path 2: Gemini handoff

True cross-model review. Manual paste into AI Studio — 30 seconds, works from
any device, genuine model independence.

Claude generates a **review packet** (HTML artifact with Copy button):

1. Full artifact source
2. Claims section (what the artifact says it does)
3. Boundary test results (if quantitative) — same tests as Path 1
4. Review focus, tailored to artifact type:
   - **Visual/UX:** layout breaks at 320px, touch targets <44px, text
     overflow, color contrast, missing states, scroll/z-index issues
   - **Quantitative:** formula correctness, unit consistency, edge cases,
     displayed results matching code
   - **Functional:** state management, edge cases, accessibility, mobile

User copies packet, opens `aistudio.google.com`, pastes, optionally attaches
screenshots of the rendered artifact, pastes Gemini's JSON response back.
Claude parses and triages.

**Visual review tips for Baylee:**
- Screenshot at mobile width (375px) and desktop width.
- Capture interactive states (expanded menus, filled forms, errors).
- Multiple screenshots > one screenshot for multi-view artifacts.

**Iterative loop:** Round 1 build → Gemini → fix CRITICALs. Round 2 present
fixes → optionally re-review → converge. **Cap at 3 rounds.** If still
failing, surface as a design problem, not a code problem.

---

### Path 3: API-delegated review (opus)

For non-computational reviews — code quality, spec completeness, prose
clarity, architecture critique — where the `window.claude.complete()` harness
doesn't apply (no boundary tests, no extractable functions). This is the
default for non-artifact deliverables.

**When to use Path 3 over Path 1:**
- Deliverable is code, a spec, a plan, or prose (not a computational artifact).
- No quantitative logic to boundary-test.
- Want true reviewer independence — the reviewer has NO access to the
  builder's reasoning, conversation history, or earlier drafts.

**Workflow:**

1. **Assemble the review packet.** Deliverable text + evaluation criteria.
   Include: what the deliverable is, who it's for, what "good" looks like.
   Do NOT include your reasoning about why you made specific choices — the
   reviewer evaluates the output, not the process.

2. **Delegate to opus** via the delegate-mechanical helper. Opus is the
   default — the reasoning premium over sonnet matters for adversarial review,
   cost is ~$0.02-0.07/call.

   System prompt: "You are a senior reviewer performing adversarial analysis.
   Find flaws the builder missed. Be decisive — state issues as facts, not
   possibilities. Surface your reasoning chain. What tradeoffs did you
   consider? What alternatives did you reject and why? Return JSON: `{issues:
   [{severity, description, location, suggestion}], reasoning: string,
   approved: bool, summary: string}`. Severity: CRITICAL = blocks delivery,
   MODERATE = should fix, MINOR = optional polish."

3. **Triage results** using the same severity scheme as Path 1.

4. **Fix and re-review** if CRITICAL issues found. Cap at 2 rounds.

For multi-round panel-style work, escalate to running Path 3 with a second
distinct system prompt (e.g., a "spec auditor" persona) and reconcile.

---

## Mode B: Score review panel

Simulates five-expert adversarial panel critiquing vault idea scores to catch
inflation, inconsistency, systematic bias. Use after batch re-scoring, for
individual uncertain scores, when vault hits 10+ scored ideas, or on explicit
"calibrate" request.

**If you are about to present batch-rescored vault output without a
calibration pass, stop.** Run Mode B first. Fresh scores look defensible in
isolation; the panel exists to catch inflation patterns and methodology drift
that aren't visible idea-by-idea.

### Panel composition

Five experts, each covering a distinct failure mode:

**1. Market Economist.** Inflated demand signals, "build it and they'll
come", generous market sizing, revenue optimism on free/gift products,
willingness-to-pay without evidence. *"Who actually pays? What's the
evidence?"*

**2. Impact Measurement Researcher.** Inflated depth, reach overestimates,
unvalidated impact, confusing "could help" with "will help". *"What's the
evidence chain from tool → behavior change → outcome?"*

**3. Solo Indie Builder.** Effort underestimates, hidden scope creep, burnout
risk, "just a simple X". *"Could one person actually build this in the
implied time? What's the hardest unsolved technical problem?"*

**4. Competitive Intelligence Analyst.** False gaps, unexamined incumbents,
defensibility inflation, "nobody does this" ≠ "nobody could". *"Who owns the
IP/engine/audience? Could an incumbent add this as a feature in one quarter?"*

**5. Scoring Methodology Auditor.** Systematic biases, internal
inconsistencies, threshold artifacts, dimension scores contradicting
justification text, anchors applied inconsistently. *"Are the same anchors
applied consistently? Do scores land exactly on a threshold and pivot on a
single modifier?"*

### Process

1. **Present scores.** Full table with dimension breakdowns AND
   justifications. The panel needs granular data, not summary percentages.
2. **Round 1 — independent review.** Each expert reviews separately. Each
   produces 2-4 specific objections citing idea, dimension, current score,
   proposed change, rationale. "No objection" is valid.
3. **Triage objections.**
   - **Accept** — clear error, apply immediately.
   - **Discuss** — reasonable disagreement, present both sides.
   - **Reject** — misunderstanding or different methodology, explain why.
4. **Apply corrections.** Update scores, recalculate percentages and
   verdicts. Note what changed.
5. **Round 2 — verdict.** Each expert returns APPROVED / APPROVED with note /
   OBJECTION (specific remaining issue).
6. **Iterate if needed.** Cap at 3 rounds. After that, note unresolved
   disagreements as open questions.
7. **Structural reflection.** Meta-question: *"Is the scoring system itself
   still sound?"* Each expert states whether any systematic issue emerged
   that the structure can't handle. One recommendation each, or "no change".
   Prevents patching scores to fit a broken system.
8. **Summarize.** Final score table with all changes, methodology
   recommendations, key calibration findings.

### Rules

1. **Experts critique independently.** Don't let one expert's objection
   contaminate another's.
2. **Quantify objections.** "This seems high" isn't an objection.
   "Defensibility 5 should be 3 because Asmodee owns the IP, engine, and
   audience" is.
3. **Don't paper over disagreements.** Two experts disagree → present both,
   make a judgment call, note it.
4. **Sustainability lens check.** Verify IRL Effort is weighted 2×, and the
   sustainability floor (avg of IRL Effort unweighted + Financial Cost +
   Dependency Risk < 3.0 caps sustainability at Low) is applied correctly.
5. **Business floor check.** If avg(GTM + Defensibility + Revenue) < 3.0,
   verdict is capped at Low for business. Primary mechanism preventing false
   Greenlights. Verify on every idea.
6. **Need splitting.** For social-impact ideas, check whether Impact-Need
   and Business-Need should score differently. "People need this" ≠ "people
   will pay for this".
7. **Borderline annotations.** Any score on the 56% threshold or within 1
   point of flipping a verdict gets annotated with the dependency.
8. **Solo-builder context.** All scores assume solo. If circumstances change
   (team, funding, institutional support), flag re-scoring warranted.

### Anti-patterns

- **Rubber-stamping.** If Round 1 produces zero objections, the review was
  too soft. At minimum, the Methodology Auditor should identify one
  systematic pattern.
- **Death by committee.** Panel's job is error-catching, not scoring-system
  redesign. Methodology recommendations outnumbering score corrections =
  scope creep.
- **Expert capture.** Don't let the Competitive Analyst kill every idea by
  finding incumbents. Incumbents exist for almost everything — the question
  is whether they address the specific gap.
- **Anchoring on originals.** Evaluate dimension scores against anchors
  independently, not "should this go up or down from where it was".

---

## Integration

- **← build:** auto-runs Path 1 (Claude.ai) or Path 3 (Claude Code/Routines)
  as Phase 7.
- **← idea-scout:** can review individual scout scores when uncertain.
- **← idea-vault:** `calibrate` command triggers Mode B across scored ideas.
- **→ delegate-adversarial:** solo single-pass flaw-finding outside Phase 7.
- **→ delegate-analytical:** when the verdict is "good enough" not a flaw
  list.
- **→ git-ops:** corrected scores pushed to vault.
- **→ idea-scout:** systematic methodology findings update the scout skill
  or memory.
