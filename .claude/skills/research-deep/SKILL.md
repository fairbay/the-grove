---
name: research-deep
description: >
  Multi-source research a decision rests on — "research X thoroughly",
  "state of the art". Not quick lookups, scoring (→ idea-scout), or
  flaw-finding (→ delegate-adversarial).
metadata:
  version: "2026-06-14-01"
---

# research-deep — calibrate research effort to stakes, then synthesize

**Version gate (chat only):** In claude.ai, compare this skill's
`metadata.version` against `fairbay/ops` via git-ops. If behind, warn once
and continue. If fetch fails, skip silently. In Claude Code / Routines,
skip — skills are synced from source.

Research depth must scale to the stakes and breadth of the question, decided
**up front** — not discovered after a shallow pass produces a wrong answer
that gets built on. The failure this skill exists to prevent: treating a
high-stakes, multi-facet question with lookup-depth effort (one or two
searches, skim the top result, stop at the first statement that fits), then
acting on it. A topic is not researched when you find a source that agrees
with a hypothesis. It is researched when enough independent sources across
enough facets **converge** — and you have said so in your own synthesis.

## The core discipline

Two rules govern everything below:

1. **Pick the depth tier before searching, keyed to stakes — not after.**
   The instinct is to start searching and let the question's difficulty
   reveal itself. That instinct under-invests, because the cost of being
   wrong isn't visible until the wrong answer is already load-bearing.
   Decide the budget first.

2. **"Researched" means convergence + synthesis, never first-fit.** Finding
   a statement that matches a hunch is the *start* of a facet, not the end
   of the question. Stop only when independent sources across the facets
   agree, disagreements are explicitly noted, and you have written the
   synthesis in your own words.

## Behavioral interrupts

**If you are about to answer a question that a decision, build, or
architectural change will rest on with one or two searches, stop.** That is
lookup depth applied to research-tier stakes. Run the tier-selection step
below and commit to the matching budget before searching.

**If you are about to assert a number, limit, threshold, or named fact you
have not found in a source this session, stop.** State that you don't have a
source and either find one or flag the claim as unverified. Never present a
fabricated specific (the canonical failure: asserting a "9–12" limit that no
source supported). No source, no assertion.

**If you have found one source that supports your current answer and are
about to conclude, stop.** One source is one facet of one perspective. Seek
a second, independent source — ideally a primary one — and a source that
would *disconfirm* the answer if it were wrong. Convergence requires more
than agreement with yourself.

**If two sources conflict and you are about to silently pick the one that
fits, stop.** Surface the conflict in the synthesis. Weight by source tier
(below). An unresolved conflict is a finding, not a problem to hide.

**If the question spans two or more systems, surfaces, or domains and you are
about to treat it as one thing, stop.** The whiplash failure mode is
conflating distinct systems (e.g. treating Claude Code's `CLAUDE.md` and the
chat `memory_user_edits` system as the same surface). Decompose into facets
first (below); research each separately; only then synthesize.

### When this skill does NOT apply

- **Quick factual lookups** — a price, a date, a current office-holder, a
  syntax detail. One search, answer, done. Forcing tiering here is waste.
- **Idea viability scoring** → `idea-scout` (Impact/Business/Sustainability).
- **Adversarial flaw-finding, security audits, score audits** →
  `delegate-adversarial` (review mode). That skill *finds what's wrong*;
  this one *builds an accurate picture*.
- **Generating new concepts** → `brainstorm-engine`.
- **Reconstructing project state** → Grove (`grove_list_*`) + `fairbay/ops`
  handoffs, not web research.

## Step 1 — Calibrate the depth tier

Score the question on two axes, then pick the tier.

**Stakes** — what rides on being right?
- *Low:* satisfies curiosity; trivially reversible; no downstream artifact.
- *Medium:* informs a choice you can revisit; a recommendation; a draft.
- *High:* a decision, a build, an architectural change, a published claim,
  anything expensive or slow to reverse will rest on the answer.

**Breadth** — how many independent facets must agree?
- *Narrow:* one fact, one well-defined question.
- *Wide:* multiple interacting facets; spans systems/surfaces/domains;
  requires reconciling several sources that each cover only part.

| Stakes × Breadth | Tier | Budget |
|---|---|---|
| Low, narrow | **T0 Lookup** | 1 search. Answer. No synthesis needed. |
| Low–med, wide **or** med, narrow | **T1 Scan** | 3–5 searches across the main facets. Short synthesis. Note the biggest open question. |
| High, narrow **or** med, wide | **T2 Investigation** | 6–12 searches. Decompose into facets, cover each, weight sources, write a synthesis that names convergence and conflicts. Consider a cross-model pass. |
| High, wide | **T3 Deep** | 12+ searches across all facets + cross-model breadth (Gemini, below) + consider the claude.ai Research feature. Full synthesis with per-facet confidence and an explicit "what would change this answer." |

**State the tier you picked and why, in one line, before searching.** This is
the up-front commitment that prevents under-investment. If T0, just answer —
this skill adds nothing and shouldn't have fired.

Re-tier *upward* mid-research if a facet turns out deeper or higher-stakes
than it looked. Don't re-tier downward to save effort once committed.

## Step 2 — Decompose into facets (T2+)

Before searching, list the independent sub-questions the answer depends on.
For a cross-system question, each system is at least one facet. For a
"state of the art" question, facets are typically: what exists now, who the
serious players are, what the tradeoffs/disagreements are, what's most
recent. Write the facet list — it is the coverage checklist for Step 3 and
the spine of the synthesis in Step 4.

## Step 3 — Gather, weighting sources by tier

Run searches per facet (not one combined query for everything — combined
queries return shallow results for each part). For each facet, seek more than
one source, and prefer sources that could disconfirm.

**Source tier (weight accordingly, and say which tier a claim came from when
it matters):**

1. **Primary / authoritative** — official docs, the spec itself, the
   source code, peer-reviewed work, the originating org. For anything about
   Anthropic's own products, Anthropic docs are primary; the
   `product-self-knowledge` skill exists for exactly this. Weight highest.
2. **Reputable secondary** — established outlets, well-known practitioners,
   maintained references. Useful, but verify load-bearing specifics against
   primary.
3. **Individual / community** — blog posts, forum answers, third-party
   guides. Treat as leads and hypotheses, not as settled fact. A specific
   number from a single community guide is unverified until a primary source
   confirms it. (This is precisely where the fabricated-limit failure came
   from: a third-party memory guide's claim treated as ground truth.)

Use `web_search` for discovery and `web_fetch` for the full text of the
sources that matter — snippets are too thin to weight or synthesize from.

### Cross-model breadth (T2 optional, T3 expected)

A second model family with a different index and different ranking surfaces
sources Claude's searches miss, and serves as an independent check on the
emerging picture. Use the `delegate-adversarial` skill's **research mode**
(`gemini.py`, search-grounded). This is the breadth/validation layer:

```python
import sys
sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
from gemini import research, GeminiError

try:
    out, usage = research(
        query='<the question, with what you need and in what format>',
        format_hint='Return JSON: {"findings": [...], "sources": [...]}',
        model='gemini-2.5-flash',  # flash is fine for research breadth
    )
except GeminiError as e:
    print(f"Gemini unavailable, proceeding with web_search only: {e}")
```

`usage['sources']` carries the grounding sources. Treat Gemini's output as an
*additional independent perspective to reconcile*, not as a tiebreaker oracle
— cross-model agreement is a confidence signal, not a grounding mechanism.
Where Gemini and Claude's searches disagree, that disagreement is a facet to
resolve against primary sources, and a finding worth reporting.

(In Claude Code / Routines, the same import path resolves from the synced
`.claude/skills/delegate-adversarial/scripts/`. `gemini.py` is
self-contained — it reads its own key and has no cross-skill dependency.)

### The claude.ai Research feature (T3, chat only)

For genuinely large T3 questions in claude.ai — broad landscape scans,
many-source surveys — the built-in **Research** feature (Settings →
toggle Research / Deep Research) runs an extended multi-source agent and is
the right heavy surface rather than dozens of manual searches in one chat.
Suggest it to Baylee when scope crosses roughly "more searches than fit
comfortably in one turn." It complements this skill: this skill decides
*that* deep research is warranted and frames the facets; the feature is one
way to *execute* the heaviest tier.

## Step 4 — Synthesize (the step that makes it "researched")

Gathering is not the deliverable. Synthesis is. Write, in your own words:

- **The answer**, facet by facet, grounded in what the sources actually said.
  Cite sources where claims come from search/fetch results.
- **Where sources converged** — the basis for confidence.
- **Where they conflicted or were thin** — named explicitly, weighted by
  source tier, not hidden.
- **Confidence per facet** (high/medium/low) for T2+, tied to how many
  independent sources of what tier agreed.
- **What would change this answer** (T3) — the disconfirming evidence you'd
  look for next, or the facet you're least sure of.

If you cannot write a convergence statement — if the honest summary is "one
source said so" — you are not done; return to Step 3. The synthesis is the
gate: no synthesis, not researched.

## Step 5 — Record durable findings

Research done for a decision feeds the decision. If this research resolves a
Rung-3 call, log it via `grove_log_decision` with the synthesis as context
and the source tiers as part of the rationale. If it's reusable project
knowledge, it belongs in the relevant repo doc or a Grove note that stands
alone (no chat context assumed), per the capture conventions — not left to
evaporate with the chat.

## Integration

- **← architect / build:** Feasibility, prior-art, and "how is this done"
  questions that a spec or implementation will rest on come here first.
- **← idea-scout:** Demand-validation depth for high-value (Greenlight)
  candidates; this skill frames the multi-facet pass, `delegate-adversarial`
  research mode supplies the cross-model leg.
- **→ delegate-adversarial:** Research mode is *called by* this skill as the
  cross-model breadth layer (Step 3). Adversarial review mode is a different
  job — finding flaws, not building the picture.
- **→ product-self-knowledge:** The primary source for any claim about
  Anthropic's products; consult it instead of asserting from memory.
- **→ grove:** Durable findings and resolved decisions land in Grove (Step 5).
