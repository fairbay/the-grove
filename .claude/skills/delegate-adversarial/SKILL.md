---
name: delegate-adversarial
description: >
  Gemini Pro for adversarial review + research — "tear this apart",
  security audit, score audit, demand validation. Not for standard
  review (→ delegate-analytical) or panel (→ review-panel).
metadata:
  version: "2026-06-02-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's
`metadata.version` against `fairbay/baylee-skills` via git-ops. If behind,
warn once and continue. If fetch fails, skip silently. In Claude Code /
Routines, skip — skills are synced from source.

# delegate-adversarial — cross-family flaw-finding and research via Gemini

Offload adversarial review and research tasks to Google's Gemini Pro via
the Google AI API. The reviewer runs in a **different model family** with
different training data, different biases, and access to Google Search
grounding. That independence IS the value — Claude reviewing Claude shares
blind spots; Gemini reviewing Claude doesn't.

Three modes:

- **Review mode** (`call` / `call_with_urls`): adversarial review of code,
  scores, specs, artifacts. Optionally fetches public URLs (repos, docs)
  via Gemini's URL Context tool.
- **Research mode** (`research`): search-grounded investigation for demand
  validation, competitive landscape, market signals.
- **Project review mode** (`multi_pass_review`): multi-pass adversarial
  review with context caching — upload data once, run multiple focused
  passes at 90% token discount.

Model: `gemini-2.5-pro` by default. The reasoning depth justifies the
cost for adversarial work — Flash misses security-relevant findings that
Pro catches. Use `gemini-2.5-flash` only for research where speed matters
more than depth.

## What "adversarial" means

The reviewer's job is to *find flaws*, not to weigh the deliverable. Trigger
language: "tear this apart," "what's wrong with," "find issues," "security
audit," "what could break," "what am I missing," architecture critique, spec
gap-finding, score audit, demand validation. Distinguished from:

- **delegate-analytical:** weighs and grades; verdict can be "good enough."
- **review-panel:** multi-agent, multi-round; this skill is solo, single-pass.

## Behavioral interrupts

**If you are about to flaw-find a spec, code, architecture, or scoring output
inline, stop.** Delegate to Gemini. Pass the deliverable + the standards it
should meet. The sub-agent has no access to the builder's context — that
isolation IS the value.

**If you are about to security-audit code or configuration inline, stop.**
Delegate to Gemini with explicit audit targets (injection, auth flaws, secrets,
data handling, access control). Without explicit targets Gemini pattern-matches
to generic "common vulnerabilities" and misses domain-specific risks.

**If you are about to gap-find a spec or architecture inline, stop.** Delegate
to Gemini with "find what's missing, contradictory, or unstated."

**If you are about to self-review a score you just generated (idea-scout
Phase 3b, or any scoring output), stop.** Delegate to Gemini. A model
auditing its own scores catches formatting errors but misses systematic
bias. Cross-family audit catches both.

**If you are about to research competitive landscape or demand signals
for a high-stakes scout, consider also delegating to Gemini.** Google Search
grounding surfaces different results from different ranking algorithms. Not
mandatory for every scout — but for Greenlight candidates, the incremental
cost is justified.

**If a review target includes a full database, large codebase, or multi-file
project, stop.** Use the multi-pass project review workflow (below) instead
of a single call. Raw dumps produce unfocused output — structured input
packaging reduces irrelevant findings by ~60%.

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
- Input is small or the stakes are low — API overhead isn't justified.
- The task needs conversation history, tools, or memory → handle inline.
  Gemini has none of this context.

## Workflow: Single-pass review

### 1. Assemble payload

System prompt (under 300 tokens): adversarial role, output format, constraints.
Instruct the sub-agent to be a critic, not a helper. Without explicit framing,
Gemini defaults to balanced, helpful responses — same tendency as Claude,
independently evolved.

**Input packaging (critical for quality):**

- **Constraints block first.** Define scope, severity ladder, and evidence
  requirements before presenting the review material. This reduces irrelevant
  findings dramatically.
- **Evidence requirement.** Always include: "Only report findings you can
  support with evidence from the provided context. Do not suggest stylistic
  changes or speculative improvements."
- **Severity ladder.** Define CRITICAL/HIGH/MEDIUM/LOW/INFO with project-
  specific meanings. Gemini uses these consistently when provided.

Templates:

Code/artifact review system prompt:
> You are a senior independent reviewer from a different team. Your job
> is to find flaws, gaps, and risks. Do not praise what works. Do not
> suggest style improvements. Return ONLY issues found, as a JSON array:
> [{"severity": "CRITICAL|MODERATE|MINOR", "location": "...",
> "issue": "...", "fix": "..."}]

Score audit system prompt:
> You are an independent auditor reviewing scores generated by another AI.
> Check for: inflated scores, missing evidence, circular reasoning,
> sycophantic agreement with the proposer, inconsistent weighting across
> categories. Return ONLY issues found as JSON.

### 2. Choose call method

**Small input (< 100K tokens), no URLs needed:**
```python
output, usage = call(system=system_prompt, user=user_message)
```

**Input references public URLs (GitHub repos, docs):**
```python
output, usage = call_with_urls(
    system=system_prompt,
    user=user_message,
    urls=['https://github.com/fairbay/repo-name'],
)
```
URL Context: Gemini fetches up to 20 public URLs (34MB each) and uses
them as context. Reference URLs in both the `urls` param AND the prompt.
Public URLs only — no auth, no localhost.

### 3. Parse and return

Strip markdown fences from JSON output (Gemini wraps in ```json blocks):

```python
import json
clean = output.strip()
if clean.startswith('```'):
    clean = clean.split('\n', 1)[1]
    clean = clean.rsplit('```', 1)[0]
issues = json.loads(clean)
```

Report concisely:
> Gemini (pro) reviewed [target] — {usage['prompt_tokens']} in /
> {usage['output_tokens']} out ({usage['thinking_tokens']} thinking).
> Found {len(issues)} issues: {critical} critical, {moderate} moderate,
> {minor} minor.

## Workflow: Multi-pass project review

Use when reviewing a full project (database + codebase + methodology).
Structured multi-pass review with context caching.

### 1. Assemble the review package

```python
from review_package import assemble_package, generate_tree_map

# Claude gathers these components first:
# - schema_ddl from Supabase MCP (execute_sql on information_schema)
# - data_sample from Supabase MCP (execute_sql with LIMIT)
# - file_list from GitHub API (list_files)
# - architecture_summary from project knowledge

package = assemble_package(
    tree_map=generate_tree_map(file_list),
    schema_ddl=schema_ddl,
    data_sample=data_json,
    architecture_summary='A consumer-facing web app...',
    methodology_notes='Data collected from MCO benefit guides...',
    metadata={'project': 'medicaid-benefits-navigator', 'states': 10},
)
```

### 2. Run the multi-pass review

```python
from project_review import multi_pass_review, format_report

findings, summary = multi_pass_review(
    package=package,
    repo_urls=['https://github.com/fairbay/medicaid-benefits-navigator'],
    passes=['schema', 'data_quality', 'methodology'],
    scope='Medicaid MCO benefits database — 10 states, 11-entity schema',
)

report = format_report(findings, summary)
```

Available passes: `schema`, `data_quality`, `architecture`, `methodology`,
`full`. Default: schema + data_quality + methodology.

Cost: ~$0.10-0.30 total for a 3-pass review (pass 1 at full price,
passes 2-3 at 90% token discount via caching).

### 3. Present findings

Report findings ranked by severity. Include cost/token summary. The
`format_report()` function produces markdown ready for presentation.

## Workflow: Research mode

### 1. Construct query

Research queries should be specific and structured. Include what you need
to know and in what format.

Good: "What AI-powered home inspection tools exist? Include pricing,
features, and user complaints. Return as JSON with products, market_signals,
and pain_points arrays."

Bad: "Tell me about home inspection AI." (too vague, Gemini will ramble)

### 2. Call API with search grounding

```python
from gemini import research, GeminiError

try:
    output, usage = research(
        query='What products exist for AI-powered home inspection?',
        format_hint='Return JSON: {"products": [...], "signals": [...]}',
        model='gemini-2.5-flash',  # flash is fine for research
    )
except GeminiError as e:
    print(f"Gemini error: {e}")
```

### 3. Parse and report

Research output includes grounding sources in `usage['sources']`. Report:
> Gemini (flash + search) researched [topic] — {usage['prompt_tokens']} in /
> {usage['output_tokens']} out, {usage.get('grounding_chunks', 0)} sources.

## Cost reference

| Mode | Typical cost | When to use |
|------|-------------|-------------|
| Single review (Pro) | ~$0.03 | Code review, score audit |
| Single review w/ URLs | ~$0.05 | Repo review, doc analysis |
| Multi-pass (3 passes, Pro) | ~$0.15 | Full project audit |
| Research (Flash + search) | ~$0.01 | Demand validation, competitive intel |

Gemini 2.5 Pro: $1.25/M input, $10/M output, 90% cache discount.
Context cache storage: $1/M tokens/hour. Default TTL: 30 min.

## Setup

### First-time setup (Baylee action)

1. Get API key at [aistudio.google.com](https://aistudio.google.com).
2. Create `secrets/gemini.env` in `fairbay/baylee-skills`:
   ```
   GOOGLE_AI_KEY=AIza...
   ```
3. Ensure `generativelanguage.googleapis.com` is in claude.ai's egress
   allowlist (Settings → Network). The `*.googleapis.com` wildcard covers
   this.

### How the key is loaded

`scripts/gemini.py` reads `secrets/gemini.env` from `fairbay/baylee-skills`
via git-ops on every call. Same pattern as other API key storage.
If the key is missing or invalid, `GeminiError` surfaces a clear message.

## Scripts reference

| Script | Purpose |
|--------|---------|
| `gemini.py` | Core API helper: call, call_with_urls, research, caching, files |
| `review_package.py` | Assemble structured review packages from project data |
| `project_review.py` | Multi-pass review orchestrator with caching |

## Integration

- **← idea-scout:** Phase 0b demand validation (research mode), Phase 3b
  score audit (review mode). The skill that most benefits from independence.
- **← architect:** Architecture critique and spec gap-finding.
- **← build:** Phase 7 code review for complex artifacts (>100 lines).
- **← review-panel:** Independent external reviewer after Round 1 panelists.
- **→ delegate-analytical:** Different job. Analytical weighs and grades;
  adversarial finds what same-family review misses.
- **→ delegate-mechanical:** Different job. Mechanical does rote extraction.
