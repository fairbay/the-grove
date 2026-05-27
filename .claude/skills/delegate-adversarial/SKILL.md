---
name: delegate-adversarial
description: >
  Opus sub-agent for solo flaw-finding — adversarial review, security audit,
  "tear this apart", architecture critique. Not for standard review
  (→ delegate-analytical) or panel (→ review-panel).
metadata:
  version: "2026-05-10-02"
---

**Version gate:** Compare this skill's `metadata.version` against
`fairbay/baylee-skills/.claude/skills/delegate-adversarial/SKILL.md` via git-ops
before doing anything else. If behind, warn once and continue. If fetch fails,
skip silently.

# delegate-adversarial — opus sub-agent for flaw-finding and deep scrutiny

Offload subtasks where the goal is to find what's wrong, missing, or vulnerable
to an opus instance via the Anthropic API. The sub-agent runs in isolation
with no access to the builder's reasoning — that independence IS the value.

Model: `claude-opus-4-7` — deep analysis (~20-30 tok/s, ~8s TTFT), $5/$25 per
M tokens. The reasoning premium over sonnet justifies the cost when missing a
subtle flaw has real consequences.

## What "adversarial" means

The reviewer's job is to *find flaws*, not to weigh the deliverable. Trigger
language: "tear this apart," "what's wrong with," "find issues," "security
audit," "what could break," "what am I missing," architecture critique, spec
gap-finding. Distinguished from:

- **delegate-analytical:** weighs and grades; verdict can be "good enough."
- **review-panel:** multi-agent, multi-round; this skill is solo, single-pass.

## Behavioral interrupts

**If you are about to flaw-find a spec, code, architecture, or scoring output
inline, stop.** Delegate to opus. Pass the deliverable + the standards it
should meet. The sub-agent has no access to the builder's context — that
isolation IS the value.

**If you are about to security-audit code or configuration inline, stop.**
Delegate to opus with explicit audit targets (injection, auth flaws, secrets,
data handling, access control). Without explicit targets opus pattern-matches
to generic "common vulnerabilities" and misses domain-specific risks.

**If you are about to gap-find a spec or architecture inline, stop.** Delegate
to opus with "find what's missing, contradictory, or unstated."

### When these interrupts do NOT apply

- The verdict is "good enough / needs work" rather than a flaw list →
  `delegate-analytical`.
- Multi-round or multi-agent review needed → `review-panel`.
- **Mid-build (Phase 7 of build pipeline).** `review-panel` already auto-runs
  there. "Tear this apart" inside an active build flow defers to the panel.
- The user wants to *discuss* the work rather than receive a punchlist.
  Heuristic: "punchlist," "list of issues," "flaws ranked" → delegate. "What
  do you think," "talk through this with me" → handle inline so the reasoning
  chain stays visible.
- Input is small or the stakes are low — opus overhead isn't justified.
- The task needs conversation history, tools, or memory → handle inline.

## Workflow

### 1. Assemble payload

System prompt (under 300 tokens): adversarial role, output format, constraints.
Instruct the sub-agent to be a critic, not a helper. Without explicit framing,
opus defaults to balanced "here's what's good and what needs work" — which
collapses to analytical-style output and wastes the model premium.

Template:
> You are a senior reviewer. Your job is to find flaws, gaps, and risks. Do
> not praise what works. Return only issues found, ranked by severity
> (CRITICAL / MODERATE / MINOR). For each: location, what's wrong, why it
> matters, suggested fix.

User message: deliverable + evaluation standards + "what should I be worried
about?"

### 2. Call API

```python
import sys
sys.path.insert(0, '/mnt/skills/user/delegate-mechanical/scripts')
from delegate import call

output, usage = call(
    model='claude-opus-4-7',
    system=system_prompt,
    user=user_message,
)
```

If the helper raises `DelegateError`, surface its message verbatim — it tells
Baylee whether to set up `secrets/delegate.env` or rotate the token. Do not
retry or fall back silently. Opus calls are slower (~8s TTFT) — this is
expected, not a failure.

### 3. Verify and return

Sanity-check output. Report concisely:
> Sub-agent (opus) completed [task] — [input_tokens] in / [output_tokens] out.

Do not echo the system prompt, raw input, or reasoning into the main chat —
only the ranked flaw list goes to Baylee.

## Cost reference (4K input)

| 500 out | 1K out | 2K out |
|---------|--------|--------|
| $0.033 | $0.045 | $0.070 |

## Integration

- **→ delegate-analytical:** Standard review where verdict (not flaw list) is the deliverable.
- **→ delegate-mechanical:** Rote comprehension or pattern-matchable filtering.
- **→ review-panel:** Multi-agent + multi-round for the highest-stakes work.
- **← architect, build, idea-scout:** Common upstream sources of artifacts to scrutinize.
