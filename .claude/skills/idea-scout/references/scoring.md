# Idea Scout — Scoring Methodology (v6)

Load this file when entering Phase 3 (scoring) of the scout workflow. Contains
every dimension, anchor, floor rule, and calibration warning. The main
SKILL.md keeps only the workflow + verdict matrix to stay under budget.

## Contents

1. Three-Lens Scoring System overview
2. Impact Lens (6 dimensions, 54-point max)
3. Business Lens (6 dimensions, 54-point max)
4. Sustainability Lens (7 dimensions, 72-point max — IRL Effort 2×)
5. Score Anchors (per dimension)
6. Scoring math + verdict matrix
7. Floor Rules
8. Track Assignment
9. Grove Status + Liveness values
10. Modifiers
11. Calibration Warnings

---

## 1. Three-Lens Scoring System

Every idea gets scored through three independent lenses:

- **Impact** — should this exist in the world?
- **Business** — can it sustain itself financially?
- **Sustainability** — can YOU specifically build and maintain it?

Always report all three.

## 2. Impact Lens (6 dimensions, 54-point max)

Measures: "If this thing magically appeared tomorrow, how good would it be?"

### Shared Dimensions (3 — scored once, interpreted per lens)

| Dimension | Impact Interpretation | Business Interpretation |
|---|---|---|
| **Gap** (0-9) | Are these people being helped? | Is there whitespace? |
| **Need** (0-9) | How serious is the problem? | Will people seek this out and pay? |
| **Reach** (0-9) | How many people can this help? | How big is the paying market? |

For social-impact ideas where "people need this" (Impact) diverges from "people
will pay for this" (Business), score Need separately for each lens and note the
split.

### Impact-Specific Dimensions (3)

- **Depth** (0-9): How much does this change things for each user?
- **Replicability** (0-9): How well does this work across contexts?
- **Inner Circle Value** (0-9): How much does this improve life for you and the
  people closest to you — family, close friends, immediate collaborators?
  Includes synergistic effects when multiple people in your circle use it
  together.

## 3. Business Lens (6 dimensions, 54-point max)

Measures: "Can this generate revenue and survive as a product?"

Uses the same 3 shared dimensions (Gap, Need, Reach) interpreted through a
business lens, plus 3 business-specific dimensions:

- **Go-to-Market Feasibility** (0-9): How hard is it to reach paying customers?
- **Defensibility** (0-9): Can it survive copycats and incumbents?
- **Revenue Path** (0-9): Is there a clear way to make money?

## 4. Sustainability Lens (7 dimensions, 72-point max)

Measures: "Can YOU specifically build and maintain this, given your skills,
tools, resources, and life context?"

- **Domain Fit** (0-9): Skills and tools you already have vs. need to acquire.
- **Digital Effort** (0-9, inverted): Computer/software work to ship. 9 = a
  session, 0 = months of coding.
- **IRL Effort** (0-9, inverted, **weighted 2×**): Physical, logistical,
  in-person work to ship. 9 = none, 0 = manufacturing, supply chain, in-person
  sales. Weighted double because IRL work breaks the Claude → PushCraft →
  Vercel pipeline entirely.
- **Financial Cost** (0-9, inverted): Money to build, launch, and maintain.
  9 = free, 0 = thousands of dollars upfront.
- **Sustained Energy** (0-9): Will you still want to work on this in 3 months?
  **Re-score at each pipeline stage transition** (scout → architect → demo → ship).
- **Maintenance Load** (0-9, inverted): Post-launch ongoing time/attention.
  9 = ship and forget, 0 = constant upkeep.
- **Dependency Risk** (0-9, inverted): External factors you don't control.
  9 = fully self-contained, 0 = dependent on third-party hardware, APIs,
  partnerships, or specific products remaining available.

**IRL Effort weighted 2×**: sustainability max = (6 × 9) + (1 × 9 × 2) = 72.
Report as percentage: score ÷ 72.

**Technical Risk flag:** If the idea requires unproven or unsolved technology
(not just "hard to build" but "unclear if this approach works at all"), note it
and cap Domain Fit at ≤3.

**Context assumption:** All sustainability scores assume Baylee's current
situation: solo builder, iPhone-primary, Claude-as-coder pipeline, two young
kids, mid-relocation. If circumstances change significantly, re-score
sustainability.

## 5. Score Anchors

**Gap:** 0-2: nobody notices the absence. 3-5: narrow or partially addressed by
existing solutions. 6-8: clear unmet need with concrete evidence (forum posts,
workarounds, complaints). 9: surprising vacuum — people are visibly struggling
with no solution. **"Nobody does X" alone is not evidence of a gap. Look for
people actively wanting X.**

**Need:** 0-2: assumed from logic, no external signal. 3-5: some forum posts or
occasional complaints. 6-8: people paying for bad substitutes, building their
own workarounds, or actively asking for this. 9: waitlists, petitions, people
spending significant money on inferior alternatives. **Calibration warning:
"I need this" is not the same as "people need this." Apply second-opinion
framing every time.**

**Reach:** 0-2: hundreds of potential users. 3-5: thousands. 6-8: hundreds of
thousands. 9: near-universal applicability.

**Depth:** 0-2: marginal convenience, nice-to-have. 3-5: meaningful improvement
to a specific workflow or situation. 6-8: changes how someone approaches a
significant part of their life. 9: transformative — hard to imagine going back.
**Calibration warning: score the median user's experience, not the
best-case-scenario user.**

**Replicability:** 0-2: works for one specific context or person. 3-5: works
with meaningful adaptation. 6-8: works broadly with minimal adaptation.
9: universal.

**Inner Circle Value:** 0-2: no one in your household or close circle would use
this. 3-5: you or someone close would benefit occasionally, or one person
benefits regularly. 6-8: regular value for you and/or close family/friends;
bonus for compounding multi-person benefits (shared data, coordination effects,
shared context). 9: daily driver for multiple people in your immediate life.

**Go-to-Market Feasibility:** 0-2: no distribution channel, no audience, cold
start. 3-5: distribution path exists (app stores, communities, partnerships)
but requires active marketing; builder has no existing audience. 6-8: clear
channel, existing demand signal, organic discovery plausible. 9: product sells
itself, viral or built-in distribution.

**Defensibility:** 0-2: trivially cloneable, incumbents could add as feature in
one quarter. 3-5: some complexity barrier but not structural. 6-8: real moat
(network effects, data, IP, relationships). 9: near-impossible to replicate.
**Hard cap: ≤3 if the only barrier is "they haven't thought of it yet." Do not
rationalize past this cap.**

**Revenue Path:** 0-2: no monetization model or explicitly free/gift. 3-5:
possible model but unproven. 6-8: proven model in similar products, clear
pricing. 9: existing revenue or contractual commitments.

**Domain Fit:** 0-2: requires skills/tools far outside your stack (hardware,
manufacturing, legal, enterprise sales). 3-5: adjacent skills you could learn
(new framework, new platform). 6-8: well within your existing capabilities with
minor learning. 9: exactly your stack.

**Digital Effort:** 0-2: months of complex coding. 3-5: weeks of focused work.
6-8: a few sessions to ship. 9: trivial or already done.

**IRL Effort:** 0-2: significant physical/logistical work (manufacturing,
shipping, in-person meetings, sourcing materials). 3-5: some IRL work
(occasional meetings, physical prototyping). 6-8: minimal IRL work (maybe one
trip to a store). 9: entirely digital, zero IRL.

**Financial Cost:** 0-2: thousands of dollars to launch/maintain. 3-5: hundreds
of dollars. 6-8: under $50. 9: free (Vercel free tier, no paid APIs, no
materials).

**Sustained Energy:** 0-2: obligation/should, no intrinsic pull. 3-5:
interesting enough to start but likely to lose steam. 6-8: genuinely excited,
would think about this in the shower. 9: can't stop thinking about it, would
build it even if no one used it.

**Maintenance Load:** 0-2: requires constant attention (live community,
physical inventory, regular content updates). 3-5: periodic maintenance
(dependency updates, user support). 6-8: occasional check-ins. 9: static once
shipped.

**Dependency Risk:** 0-2: dependent on specific third-party products, APIs, or
partnerships that could change or disappear. 3-5: some dependencies but with
alternatives available. 6-8: mostly self-contained. 9: fully under your
control.

## 6. Scoring math + verdict matrix

**Impact:** 6 dimensions × 9 max = 54. Report as percentage (score ÷ 54).
**Business:** 6 dimensions × 9 max = 54. Report as percentage (score ÷ 54).
**Sustainability:** 7 dimensions, IRL Effort at 2× = 72 max. Report as
percentage (score ÷ 72).

Threshold for each lens: **56%** (High). Below 56% = Low.

Eight verdicts based on High/Low across three lenses:

| Impact | Business | Sustainability | Verdict | Meaning |
|---|---|---|---|---|
| H | H | H | **Greenlight** | All systems go. Build and ship. |
| H | H | L | **Overreach** | Right idea, wrong scope or wrong builder. Descope, partner, or license. |
| H | L | H | **Public Good** | Meaningful and buildable. Ship it, don't agonize about money. |
| H | L | L | **Mirage** | Important idea you can't sustain. Document and seed to a better-positioned community. |
| L | H | H | **Workhorse** | Profitable and doable but not deeply meaningful. Fine if you need income. |
| L | H | L | **Fool's Gold** | Looks profitable, isn't sustainable for you. Trap. |
| L | L | H | **Lark** | Low stakes, easy to build. Build for fun, learning, or portfolio. |
| L | L | L | **Pass** | Walk away. |

Score tables and verdict appear immediately after executive summary, before
detailed analysis.

**Expected base rates** (for calibration — if actual distribution diverges
significantly, re-examine thresholds):
- Greenlight: ~5% of scouted ideas
- Public Good: ~25%
- Lark: ~15%
- Pass: ~30%
- Mirage + Overreach + Workhorse + Fool's Gold: ~15% combined
- Remaining ~10%: borderline cases requiring judgment

## 7. Floor Rules

- **Business Floor:** If the average of business-specific dimensions
  (GTM + Defensibility + Revenue) < 3.0, business lens is **capped at Low**
  regardless of total business percentage.
- **Impact Floor:** If the average of impact-specific dimensions
  (Depth + Replicability + Inner Circle Value) < 3.0, impact lens is **capped
  at Low**.
- **Sustainability Floor:** If the average of IRL Effort (unweighted) +
  Financial Cost + Dependency Risk < 3.0, sustainability lens is **capped at
  Low**.

When a floor rule caps a lens, note it explicitly.

## 8. Track Assignment

After scoring, tag the idea with a **pipeline track:**

- **Execution track:** Greenlight or Public Good verdict, and the build path is
  clear. → Build and ship.
- **Discovery track:** Scores well on one+ lens but has uncertain user
  behavior, unproven demand mechanism, or requires iterative learning.
  → Prototype, test, learn, rebuild.
- **Lark track:** Lark verdict. → Build for fun. Different success criteria:
  did you learn something, enjoy it, produce reusable assets? No pressure to
  find users or monetize.
- **Seed track:** Mirage verdict. → Write up the concept + research, post it
  in the community best positioned to execute, vault as "gifted" status.
  Use pitch-crafter in "here's a product someone should build" mode.
- **Pass:** Pass or Fool's Gold verdict. → Kill with documented reasons.
- **Descope track:** Overreach verdict. → Identify the smaller version that
  drops IRL effort or domain mismatch. Re-scout the descoped version.

## 9. Grove Status + Liveness values

### Status (idea lifecycle)

- **raw** — captured but not yet scouted
- **scouted** — scored, not yet building
- **in_dev** — actively in development
- **shipped** — live and accessible
- **shelved** — paused intentionally, may return
- **killed** — permanently rejected with documented reasons
- **gifted** — given to another person or community, no further follow-up planned

### Liveness (real-world usage of deployed/gifted ideas)

- **Live** — actively used or maintained
- **Sunset** — was live, no longer is
- **Untracked** — no visibility into current usage

## 10. Modifiers

- **Need Split:** For social-impact ideas, score Impact-Need and Business-Need
  separately when interpretations diverge. Document both.
- **Technical Risk Flag:** If the idea requires unproven technology, note it
  and cap sustainability's Domain Fit at ≤3.

The v5 Founder-User Fit modifier (+1 to Need) has been removed. Personal
benefit is now captured directly by Inner Circle Value in the Impact lens,
which is more honest and doesn't inflate a shared dimension.

## 11. Calibration Warnings

These address systematic biases identified during the v5→v6 review:

1. **Need scores run ~1 point high.** Evidence bar is too low. "Forum posts
   exist" is 3-5 range, not 6-8. Real demand signals (6-8) require people
   paying for bad substitutes or building their own workarounds. Apply
   second-opinion framing every time.

2. **Depth scores run ~1-2 points high.** You're scoring the best-case user,
   not the median user. "This could change someone's life" is not the same as
   "most people will use it twice and forget." Score the median experience.

3. **Defensibility rationalizes past the ≤3 cap.** The rule says cap at 3 when
   "the only barrier is they haven't thought of it yet." It's always possible
   to find *some* reason an idea is "more than that." Be disciplined. If a
   competent team at an incumbent could replicate the core value in one
   quarter, it's ≤3 regardless of what you tell yourself about your unique
   research or approach.

4. **1-point shifts compound.** Three dimensions each inflated by 1 point =
   5-6 percentage points on a lens. That's exactly the margin between
   verdicts. When in doubt, round down.
