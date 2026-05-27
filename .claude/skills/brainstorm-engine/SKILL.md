---
name: brainstorm-engine
description: >
  Generate NEW concepts — "brainstorm", "what could I build", "crazy 8s". Not
  for evaluating (→ idea-scout), building (→ build), browsing (→ idea-vault),
  or pitching (→ pitch-crafter).
metadata:
  version: "2026-05-12-03"
---

**Version gate:** Compare this skill's `metadata.version` against
`fairbay/baylee-skills/.claude/skills/brainstorm-engine/SKILL.md` via git-ops
before doing anything else. If behind, warn once and continue. If fetch fails,
skip silently.

# brainstorm-engine — structured idea generation

Act like a divergent-thinking partner who knows when to converge. Produce
buildable concepts from problem spaces, constraints, personal interests, or
pure exploration. Front of the funnel — generates candidates that
`idea-scout` can evaluate.

## Routing — when this fires vs. its siblings

- **No concrete idea yet** → brainstorm. "What could I build", "give me
  ideas", "brainstorm around X."
- **One concrete idea in hand** → `idea-scout`. Don't generate more before
  evaluating the one already on the table.
- **A specific generated idea the user points at** → `build` (skip planning)
  or `idea-scout` (evaluate first).

## Philosophy

- **Specific enough to scout.** Each idea should be evaluable by `idea-scout`
  without clarification — name a problem, a user, and a mechanism.
- **Grounded in real problems.** Not "what if there was an app for X" but
  "people currently do Y manually and it costs them Z."
- **Sized for a solo builder.** No "build a social network."
- **Honest about excitement vs. viability.** Some ideas are fun but bad. Say
  so during convergence, not after.
- **Diverge first, converge second.** Generate without judging, THEN evaluate.
  Mixing the two collapses the divergence into safe ideas.

## Interaction principles

- **Use structured input for narrowing.** `ask_user_input_v0` for
  mode/theme/constraint selection. Reduces friction on mobile.
- **Second-opinion lens.** After generating, evaluate as if they came from a
  stranger — the same skeptical framing `idea-scout` uses.

## Modes

### Standard mode (default)

Full pipeline: research → diverge → converge → meta-analysis.

### Rapid-Fire mode (Crazy 8s)

8 one-sentence concepts, maximum diversity. User picks which to expand.
Trigger: "rapid fire", "quick ideas", "crazy 8s", or after standard mode
produced Tier 1 ideas and the user wants variations.

### Reverse mode

Generate worst possible solutions, invert each failure into a design
principle, then generate ideas from those principles. Trigger: "reverse
brainstorm", "worst ideas", "flip it", or when standard generation produces
same-y results.

## Inputs

Works with any combination (at least one required): problem space,
constraints, personal interests, irritation prompt ("things that bug me"),
audience.

---

## Standard mode workflow

### Phase 1: Frame the space

**Known-builder bypass:** if builder context is loaded from memory (solo
builder, mobile-first, Claude-as-coder), skip capability questions. Only ask
narrowing questions if the *problem space* is genuinely ambiguous. 2-3
targeted questions max if needed.

### Phase 2: Research the space (3-5 searches)

Ground the brainstorm in reality: pain points, "I wish someone would
build…", trending capabilities, underserved audiences. Include at least one
analogous-domain search (how does a *different* field solve this class of
problem?). Faster and less exhaustive than `idea-scout` — scout will do the
deep landscape pass if the user picks an idea.

### Phase 3: Diverge — generate 12-15 raw ideas

**Goal: quantity and diversity over quality.** Apply generation lenses
internally (don't explain them in the output):

- Inversion
- Audience shift
- Unbundling
- Workflow observation (alt-tab/copy-paste bridges)
- New capability unlock
- Analog → digital
- Radical simplification
- Cross-domain combination
- HMW reframe (convert pain into "How might we…" then generate 2-3 ideas
  from it)

Each raw idea: **title + one-sentence description.** No evaluation.

### Phase 4: Converge — evaluate and tier

Sort into three tiers:

- **Tier 1: High-Conviction (2-3)** — real problem, clear gap, tractable
  build. Worth scouting.
- **Tier 2: Interesting Bets (3-4)** — genuine potential but unproven demand
  or harder execution.
- **Tier 3: Wild Cards (2-3)** — creative, high-risk. Best ideas often sound
  weird at first.
- **Also considered:** list remaining titles only.

#### Tiered idea format

```
### [Idea Title]
**One-liner:** What it is
**Problem:** Who has this problem and why it matters (2 sentences max)
**How it works:** Core mechanism (2-3 sentences)
**Why now:** What makes this newly possible or timely
**Quick take:** Honest gut check
**Tags:** 3-5 relevant tags
```

### Phase 5: Meta-analysis

- **Patterns:** what themes emerged?
- **Strongest signal:** which had the strongest evidence of real demand?
- **Most fun to build:** which would be most enjoyable?
- **Highest ceiling:** which has the most upside if it works?
- **Recommended next step:** "Run idea-scout on [specific idea]" or "Narrow
  further."

---

## Rapid-Fire mode workflow

1. Skip research (assume space understood from context).
2. Generate 8 concepts: title + one-sentence description. Maximum diversity.
3. Present as numbered list.
4. Ask which to expand (or suggest strongest 2-3).
5. Expand selected into full tiered format.

## Reverse mode workflow

1. Define the target: what is the user trying to solve?
2. Generate 6-8 worst possible ideas — specific and creative, not just "make
   it slow."
3. Extract the inversion from each — what design principle does the opposite
   reveal?
4. Collect inversions into a design priorities list.
5. Generate 4-6 ideas embodying those priorities (full tiered format).

## Deliverable

Single markdown file: `brainstorm-[domain-or-theme-slug].md` in
`/mnt/user-data/outputs/`. Under 2,000 words. Direct, first-person style.

## Edge cases

- **Too vague ("give me ideas"):** ask 2-3 narrowing questions.
- **Too narrow ("ideas for a Chrome extension that tracks X"):** that's one
  idea. Hand off to `idea-scout` directly.
- **User has domain expertise:** don't explain their field. Focus on new
  angles.
- **Repeat session:** focus on new angles. Consider suggesting reverse mode.
- **Mode selection:** default to Standard. Suggest variants when conditions
  fit — don't ask the user to pick.

## Integration

- **← idea-vault:** check for related ideas already explored before generating
  — avoids re-suggesting concepts already in the catalog.
- **→ idea-scout:** "Want me to scout any of these?" is the natural follow-up.
  Don't auto-chain — wait for the user to pick a candidate.
- **→ build:** if user points at an idea and says "build that," hand off
  directly.
- **→ idea-vault (`add`):** "Want me to add these to your vault as raw ideas?"
  Bulk-add as `status: raw` so future sessions don't re-generate them.
