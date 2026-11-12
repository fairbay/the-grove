---
name: delegate-mechanical
description: >
  Haiku sub-agent for rote bulk work — summarize, extract, scaffold, compress,
  filter by tag/keyword, scan. Use proactively. Not for judgment
  (→ delegate-analytical) or async (→ fire-routine).
metadata:
  version: "2026-11-11-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# delegate-mechanical — haiku sub-agent for comprehension-only work

Offload subtasks that need comprehension but not judgment to a haiku sub-agent
(the Agent tool with `model: "haiku"`). The sub-agent runs in isolation — only
the result enters the main chat. In claude.ai chat there is no sub-agent: apply
the same lens inline.

There is no API helper: `delegate.py` is removed, and no skill reads
`ANTHROPIC_API_KEY`, which is being retired (unset from the environment after
Baylee reads its last-used date; Grove 0ee04363, `docs/secrets-move/DESIGN.md` §4.2).

## What "mechanical" means

Pattern-matchable, no domain judgment. The criterion is concrete: a tag, a
regex, a question with a stated answer location, a template. If evaluating each
item requires Claude to bring outside knowledge to bear, the work is analytical
→ `delegate-analytical`.

**Harness note (Agent-tool sub-agents in cloud Code sessions).** A sub-agent may
be unable to write files outside its working set ("Subagents should return
findings as text"): brief it to reply with findings as text and save them
yourself. Its final report is recoverable from `tasks/<id>.output` (the
SubagentHandback tool_use input) when the completion notification is lost. A
sub-agent sent to the web carries the global rule's search-first paragraph
verbatim.

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
- A one-liner (`grep`, `jq`) handles it faster than a sub-agent.
- The task requires judgment beyond comprehension → `delegate-analytical` or
  `delegate-adversarial`.

## Workflow

### 1. Assemble the brief

Role, output format and constraints first (under 300 tokens). Example:
"You are a focused assistant. Return only [format]. No reasoning."
Then the task instruction, the content (or its file paths) and the extraction targets.

Do NOT plan to echo the brief, raw input, or sub-agent reasoning back
into the main chat — that defeats the point of delegation. Plan the prompt so
only the extracted result needs surfacing.

### 2. Run the sub-agent

In a Code session, call the Agent tool with `model: "haiku"` and the role,
format and task in its prompt. Bulk input stays in files: name the paths and
let the sub-agent read them (bulk text never rides in tool arguments). A brief
that lets it run shell commands or reach the web carries the global rules'
verbatim Shell and Web paragraphs.

### 3. Verify and return

Sanity-check output. Report concisely:
> Sub-agent (haiku) completed [task].

If the result is bad, retry once with a more specific prompt or fall back to inline.

## Integration

- **→ delegate-analytical:** Filter requires domain judgment, not pattern match.
- **→ delegate-adversarial:** Goal is flaw-finding, not retrieval/extraction.
- **→ fire-routine:** Work is async (results land later in Grove/repo).
- **← idea-vault, grove:** Common upstream sources of bulk content.
