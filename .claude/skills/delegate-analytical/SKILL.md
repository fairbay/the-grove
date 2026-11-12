---
name: delegate-analytical
description: >
  Sonnet sub-agent for judgment — review, compare, rank, evaluate. Use
  proactively. Not for flaw-finding (→ delegate-adversarial), rote
  (→ delegate-mechanical), panel reviews (→ review-panel).
metadata:
  version: "2026-11-11-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# delegate-analytical — sonnet sub-agent for judgment and evaluation

Offload subtasks that require weighing, comparing, or evaluating to a sonnet
sub-agent (the Agent tool with `model: "sonnet"`). The sub-agent runs in
isolation — only the result enters the main chat. In claude.ai chat there is no
sub-agent: apply the same lens inline.

There is no API helper: `delegate.py` is removed, and no skill reads
`ANTHROPIC_API_KEY`, which is being retired (unset from the environment after
Baylee reads its last-used date; Grove 0ee04363, `docs/secrets-move/DESIGN.md` §4.2).

## What "analytical" means

Judgment work — the deliverable is a verdict, ranking, comparison, or filtered
shortlist where each item was *evaluated* against criteria. Distinguished from:

- **mechanical:** the criterion is pattern-matchable (tag, keyword, regex).
- **adversarial:** the goal is to find flaws, not weigh tradeoffs.
- **review-panel:** multi-agent, multi-round; this skill is solo, single-pass.

**Harness note (Agent-tool sub-agents in cloud Code sessions).** A sub-agent may
be unable to write files outside its working set ("Subagents should return
findings as text"): brief it to reply with findings as text and save them
yourself. Its final report is recoverable from `tasks/<id>.output` (the
SubagentHandback tool_use input) when the completion notification is lost. A
sub-agent sent to the web carries the global rule's search-first paragraph
verbatim.

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

### 1. Assemble the brief

Role, output format and constraints first (under 300 tokens). Include
the evaluation criteria or comparison dimensions explicitly — sonnet needs to
know WHAT to judge against, not just what to look at. Without explicit criteria
the verdict drifts toward generic "looks good / could be better."
Then the task instruction, the content (or its file paths) and the criteria/dimensions.

Plan the brief so only the verdict and action items need surfacing — do not
plan to echo the brief, raw input, or reasoning back into the main chat.

### 2. Run the sub-agent

In a Code session, call the Agent tool with `model: "sonnet"` and the role,
criteria and task in its prompt. Bulk input stays in files: name the paths and
let the sub-agent read them. A brief that lets it run shell commands or reach
the web carries the global rules' verbatim Shell and Web paragraphs.

### 3. Verify and return

Sanity-check output. Report concisely:
> Sub-agent (sonnet) completed [task].

If the result is bad, retry once with sharper criteria or fall back to inline.

## Integration

- **→ delegate-mechanical:** Pattern-matchable filter / rote comprehension.
- **→ delegate-adversarial:** "Tear this apart" / find-flaws framing.
- **→ review-panel:** High-stakes work warranting multi-agent review.
- **← idea-vault, idea-scout:** Common upstream sources for ranking/comparison.
