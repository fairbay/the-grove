Part of the Fairbay global rules (the core, `.claude/global.md`, and the files in `.claude/global/`); 'this file', 'below' and 'above' in these sections mean the global rules as a whole.

## Code Quality (every change, not separate cleanup)

- Only export what's consumed externally.
- Remove dead code in the same commit it becomes dead.
- Deduplicate on sight — same logic in 2+ places → shared helper.
- Don't send unused data to APIs.
- CSS housekeeping — remove associated keyframes/styles when removing a component.
- Trace feature plumbing end-to-end: UI → state → API → server → response → render. Missing links = silent failures.

## Architecture Principles

- Client-side generation > API generation for anything deterministic.
- Keep dev and production config in sync — same model, same params.
- Prompt caching — use `cache_control: { type: "ephemeral" }` on stable system prompts.
- Strip accumulated waste from context (large rendered content in message history).
- Compact prompts — terse instruction language, no filler.
- Extraction is classification, not generation — when extracting data from source documents, frame the task as selecting from source text (return verbatim quotes), not generating descriptions. Layer inference (normalization, categorization) as a separate stage. Training priors make models confidently extract plausible values that aren't in the source.
- Provide source text in extraction prompts — include the actual source excerpt, not just a reference or URL. Single highest-impact lever for extraction accuracy.
- When an LLM must choose data content, give it a closed set of real candidates and validate its choice mechanically (substring/ID membership check on both sides of the call) — never accept free-form output as data. This turns "trust the model" into "the model physically cannot fabricate." (MBN quote backfill: 1,496 LLM-adjudicated quotes, 0 fabrications possible by construction.)
- A sub-agent names what it cannot see. A model asked to label, name or classify a record it was given only part of will produce a plausible label from the part it has; the gap is invisible in its output. Hand it the primary text (the listing, the row, the source passage), not a summary or a derived field, and check its output against that text mechanically (a word of the name must occur in the text) before anything downstream treats the label as data; where the input names nothing, Usage Discipline's brief lint applies. (MBN 2026-10-17, "Money for grocery activities".)
- Script-first, LLM-last for bulk data work (Usage Discipline, "Mechanical triage"): reserve the LLM for the narrow judgment slot the script can't do (e.g. semantic tie-breaking among real candidates); MBN quote backfill went 13x faster this way. Pin fetched-source parsing to process pools, not threads — native libs (pypdf/cryptography, lxml, Playwright sync API) corrupt memory under thread concurrency in cloud sandboxes.
- Research established practices before building custom solutions — ask "what do practitioners already do?" before designing pipelines, schemas, or domain-specific approaches. Check for built-in tool capabilities, domain standards, and regulatory frameworks first. For regulated domains (healthcare, finance, education), relevant regulatory frameworks often define data availability and methodology — consult them before building extraction or discovery pipelines.

## CSS / Layout

- Flexbox scrolling: `h-screen` (not `min-h-screen`) + `min-h-0` on scrollable flex child.
- Sticky headers in flex layouts: `shrink-0`, not `sticky`.

## Testing & Validation

- Test before pushing — syntax checks (`python -c`, `node -c`, `JSON.parse`) on generated files.
- Validate end-to-end after deploy — call endpoints, check logs, verify behavior. Claude runs the verification, never Baylee (Non-Negotiable Rule 1).

## Vercel Deployment

- Deploys via push to `main` → Vercel auto-deploy for connected repos.
- SSE streaming requires `export const config = { supportsResponseStreaming: true }`.
- Runtime packages in `dependencies`, not `devDependencies`.
