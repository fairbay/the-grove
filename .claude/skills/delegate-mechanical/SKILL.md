---
name: delegate-mechanical
description: >
  Haiku sub-agent for rote bulk work — summarize, extract, scaffold, compress,
  filter by tag/keyword, scan. Use proactively. Not for judgment
  (→ delegate-analytical) or async (→ fire-routine).
metadata:
  version: "2026-05-10-02"
---

**Version gate:** Compare this skill's `metadata.version` against
`fairbay/baylee-skills/.claude/skills/delegate-mechanical/SKILL.md` via git-ops
before doing anything else. If behind, warn once and continue. If fetch fails,
skip silently.

# delegate-mechanical — haiku sub-agent for comprehension-only work

Offload subtasks that need comprehension but not judgment to a haiku instance
via the Anthropic API. The sub-agent runs in isolation — only the result enters
the main chat.

Model: `claude-haiku-4-5-20251001` — fast (~80-120 tok/s), $1/$5 per M tokens.

## What "mechanical" means

Pattern-matchable, no domain judgment. The criterion is concrete: a tag, a
regex, a question with a stated answer location, a template. If evaluating each
item requires Claude to bring outside knowledge to bear, the work is analytical
→ `delegate-analytical`.

## Behavioral interrupts

These fire BEFORE fetching bulk data. Match on task SHAPE, not estimated size.

**If you are about to delegate a request where the user wants to SEE the
items rather than get a filtered subset, stop.** "Show me my vault," "list
recent ideas," "what's in Grove" — the raw data IS the deliverable. Delegating
returns a summary instead of the items Baylee wanted to react to. Fetch and
display directly.

**If you are about to scan or filter a collection by tag, status, keyword, or
other pattern-matchable criteria, stop.** Fetch via direct API call or file
read in bash, pass to haiku with the filter criteria, return only matches.
Counter-example: "which ideas would benefit from Vercel Workflows" requires
domain knowledge — that's analytical, not mechanical.

**If you are about to read a large file or document to answer a specific
question or extract specific facts, stop.** Read via bash, pass to haiku with
the question, return only the answer.

**If you are about to generate boilerplate code (tests, config, scaffolding)
from a clear spec, stop.** Pass spec and style example to haiku.

**If you are about to compress a transcript or summarize a document, stop.**
Pass to haiku, return only the summary.

**If you are about to process a bulk API response or command output to extract
a subset, stop.** Pass raw output with extraction target to haiku.

### When these interrupts do NOT apply

- Input is small (under ~10 items, single-page doc).
- Content is already in context from an earlier step.
- A one-liner (`grep`, `jq`) handles it faster than an API call.
- The task requires judgment beyond comprehension → `delegate-analytical` or
  `delegate-adversarial`.

## Workflow

### 1. Assemble payload

System prompt (under 300 tokens): role, output format, constraints. Example:
"You are a focused assistant. Return only [format]. No reasoning."

User message: task instruction + content + extraction targets.

Do NOT plan to echo the system prompt, raw input, or sub-agent reasoning back
into the main chat — that defeats the point of delegation. Plan the prompt so
only the extracted result needs surfacing.

### 2. Call API

```python
import sys
sys.path.insert(0, '/mnt/skills/user/delegate-mechanical/scripts')
from delegate import call

output, usage = call(
    model='claude-haiku-4-5-20251001',
    system=system_prompt,
    user=user_message,
)
```

If the helper raises `DelegateError`, surface its message verbatim — it tells
Baylee whether to set up `secrets/delegate.env` or rotate the token. Do not
retry or fall back silently.

### 3. Verify and return

Sanity-check output. Report concisely:
> Sub-agent (haiku) completed [task] — [input_tokens] in / [output_tokens] out.

If the result is bad, retry with a more specific prompt or fall back to inline.

## Cost reference (4K input)

| 500 out | 1K out | 2K out |
|---------|--------|--------|
| $0.006 | $0.009 | $0.014 |

## Integration

- **→ delegate-analytical:** Filter requires domain judgment, not pattern match.
- **→ delegate-adversarial:** Goal is flaw-finding, not retrieval/extraction.
- **→ fire-routine:** Work is async (results land later in Grove/repo).
- **← idea-vault, grove:** Common upstream sources of bulk content.
