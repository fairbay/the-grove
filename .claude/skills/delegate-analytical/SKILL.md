---
name: delegate-analytical
description: >
  Sonnet sub-agent for judgment — review, compare, rank, evaluate. Use
  proactively. Not for flaw-finding (→ delegate-adversarial), rote
  (→ delegate-mechanical), panel reviews (→ review-panel).
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# delegate-analytical — sonnet sub-agent for judgment and evaluation

Offload subtasks that require weighing, comparing, or evaluating to a sonnet
instance via the Anthropic API. The sub-agent runs in isolation — only the
result enters the main chat.

Model: `claude-sonnet-4-6` — strong analysis (~40-60 tok/s), $3/$15 per M tokens.

## What "analytical" means

Judgment work — the deliverable is a verdict, ranking, comparison, or filtered
shortlist where each item was *evaluated* against criteria. Distinguished from:

- **mechanical:** the criterion is pattern-matchable (tag, keyword, regex).
- **adversarial:** the goal is to find flaws, not weigh tradeoffs.
- **review-panel:** multi-agent, multi-round; this skill is solo, single-pass.

## Behavioral interrupts

These fire BEFORE fetching bulk data. Match on task SHAPE.

**If you are about to scan or filter a collection where each item must be
evaluated against domain knowledge or external criteria, stop.** This is the
key distinction from `delegate-mechanical`: "which ideas would benefit from
Vercel Workflows" requires Workflows knowledge to judge each idea — analytical,
not mechanical. Fetch via bash, pass to sonnet with the criteria and context
needed to evaluate, return only matches with brief rationale.

**If you are about to compare, rank, or cross-analyze multiple items where
the raw data is large but the deliverable is a ranked list, stop.** Comparison
requires judgment — sonnet's job, not haiku's.

**If you are about to review a deliverable (text, code, plan) where only the
verdict and action items matter, stop.** Pass the deliverable + evaluation
criteria, return verdict + action items. If the framing is "tear this apart"
or "find what's wrong," route to `delegate-adversarial` instead — adversarial
framing changes the prompt, not just the model.

**If you are about to route a bare "review this" to delegate-adversarial,
stop.** "Review this PR," "review this plan," "review my draft" default here,
not to adversarial. Adversarial requires explicit flaw-finding framing ("tear
apart," "audit," "what's broken," "what am I missing"). Without that framing,
the user wants a verdict, not a flaw list — and adversarial's prompt template
suppresses the verdict.

### When these interrupts do NOT apply

- The filter is pattern-matchable (tag, status, keyword) → `delegate-mechanical`.
- The task is flaw-finding or adversarial scrutiny → `delegate-adversarial`.
- The deliverable warrants a multi-agent panel → `review-panel`.
- Input is small (under ~10 items, single-page doc).
- The reasoning chain IS the deliverable (architecture decisions, explanations).
- The task needs conversation history, tools, or memory → handle inline.

## Workflow

### 1. Assemble payload

System prompt (under 300 tokens): role, output format, constraints. Include
the evaluation criteria or comparison dimensions explicitly — sonnet needs to
know WHAT to judge against, not just what to look at. Without explicit criteria
the verdict drifts toward generic "looks good / could be better."

User message: task instruction + content + criteria/dimensions.

Plan the prompt so only the verdict and action items need surfacing — do not
plan to echo the system prompt, raw input, or reasoning back into the main chat.

### 2. Call API

```python
import sys
sys.path.insert(0, '/mnt/skills/user/delegate-mechanical/scripts')
from delegate import call

output, usage = call(
    model='claude-sonnet-4-6',
    system=system_prompt,
    user=user_message,
)
```

If the helper raises `DelegateError`, surface its message verbatim — it tells
Baylee whether to set up `secrets/delegate.env` or rotate the token. Do not
retry or fall back silently.

### 3. Verify and return

Sanity-check output. Report concisely:
> Sub-agent (sonnet) completed [task] — [input_tokens] in / [output_tokens] out.

If the result is bad, retry with sharper criteria or fall back to inline.

## Cost reference (4K input)

| 500 out | 1K out | 2K out |
|---------|--------|--------|
| $0.020 | $0.027 | $0.042 |

## Integration

- **→ delegate-mechanical:** Pattern-matchable filter / rote comprehension.
- **→ delegate-adversarial:** "Tear this apart" / find-flaws framing.
- **→ review-panel:** High-stakes work warranting multi-agent review.
- **← idea-vault, idea-scout:** Common upstream sources for ranking/comparison.
