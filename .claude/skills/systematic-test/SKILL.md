---
name: systematic-test
description: >
  Verify built code works — "test this", "QA this", "does this work". Auto-fires
  after build. Not for bugs (→ systematic-debug) or code review (→ review-panel).
metadata:
  version: "2026-05-27-02"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# systematic-test — verify before declaring done

Act like a QA lead pushing back on a developer who just said "ship it." Untested features are unfinished features. Claude's failure mode is declaring "done" after writing code that compiles, without verifying it actually works under real inputs. This skill enforces a test methodology that maximizes coverage while minimizing tool cost and session instability.

**Core principle: test each layer via the cheapest available tool.** Bash/curl can verify more than you think. Browser automation is expensive (context window, session stability, time). Manual testing by Baylee is the most expensive of all. Allocate accordingly.

## Task-shape interrupt

**If you are about to tell the user a build is "done," "shipped," or "ready" without running tests, stop.** Code that compiled or deployed without errors is not verified code. Run Phase 1 decomposition first — at least the bash-testable layers — before any "done" claim.

## Phase 1: Decompose into testable layers

Before writing any test, list every changed component and classify it:

| Layer | Tool | Examples |
|-------|------|----------|
| API endpoints | bash (curl) | Response codes, JSON shape, error handling, edge cases |
| Server-side logic | bash (curl/scripts) | Data transformation, cache behavior, search/filter |
| Static files deployed | bash (curl + grep) | File exists, contains expected content, version strings |
| Prompt content | Code review (in-context) | Prompt sections present, calibration language correct |
| Client-side state machine | Code review (trace) | Every state value → what triggers it → what renders for it |
| Client-side JS logic | Browser (MCP or manual) | DOM manipulation, localStorage, routing, UI rendering |
| Bookmarklet/extension | Browser (manual only) | Runs in page context, extracts data, redirects |
| Visual/UX | Browser (manual only) | Layout, responsiveness, copy buttons, interactions |

**State machine trace (required for multi-state UI):** Before pushing any UI that has multiple phases, views, or modes, list every state value and trace what the render function produces for each. Walk the transitions: user clicks X → state becomes Y → render shows Z. Any state that produces empty output, falls through without a return, or doesn't have a matching render block is a bug. This is a code review task, not a browser task — do it before pushing, not after deploying.

**Rule: never open a browser for something curl can answer.** API responses, file existence, content checks, error codes, data shape validation — all curl. The browser adds DOM rendering, JS execution, and screenshot overhead for zero additional signal on those questions.

## Phase 2: Write and run bash tests

For each bash-testable component, write a curl/script test that checks:

1. **Happy path:** Expected input → expected output (status code + key fields)
2. **Error path:** Missing/invalid input → correct error response
3. **Edge cases:** Boundary conditions specific to the feature (empty results, partial matches, case sensitivity, missing optional fields)

### Test output format

Each test prints a single line: test ID, what was tested, pass/fail, key detail.
```
T1: GET /api/cache?list=1 → 200, 27 listings ✓
T2: GET /api/cache?search=215+W+12th&zip=49684 → 200, matched zpid=91701303 ✓
T3: GET /api/cache?search=ab → 400, "too short" ✓
```

Run ALL bash tests before touching any browser tool. Fix failures in-session if they're server-side bugs (chain to systematic-debug). If a bash test reveals a client-side-only issue, note it and move on — it'll be caught in browser testing.

### Code review as testing

When source code is in context (uploaded files, repo contents), grep/verify key content directly. This replaces fetching deployed source when the deployment pipeline is trusted. Note: "verified from in-context source" is weaker than "verified from deployed endpoint" — state which one.

## Phase 3: Classify browser-only remainder

After bash tests pass, list what's left. For each remaining item, classify:

- **Trivial** (< 30 seconds, single action): e.g., "click copy button, verify clipboard"
- **Standard** (1-3 minutes, multi-step flow): e.g., "run bookmarklet on listing page, verify extraction and redirect"
- **Complex** (> 3 minutes, requires specific preconditions): e.g., "trigger a cache-miss AND ScraperAPI failure to see Tier 3 fallback UI"

### Routing decision

| Remainder size | Route |
|---------------|-------|
| 0-2 trivial items | Chrome MCP in-session (low context cost) |
| 3+ items or any complex | Write manual test instructions for Baylee |
| Mix | Chrome MCP for trivial, manual instructions for the rest |

When Chrome MCP sessions are unstable (context wipes, tool-heavy workflows), bias toward manual instructions even for standard items.

## Phase 4: Write manual test instructions

When browser tests route to Baylee, produce a structured test document:

```markdown
### B1. [Test Name] (severity: critical|standard|trivial)

1. [Exact step — what to open, click, type]
2. [Next step]
3. **Expected:** [What should happen — specific enough to distinguish pass/fail]
4. **Verify:** [What to check — specific UI element, console output, network request]
```

Include:
- Pre-conditions (what needs to be true before the test)
- Which tests are critical vs nice-to-have
- What to report back if something fails (screenshot? console error? network tab?)

Do NOT include:
- Vague instructions ("verify it works")
- Steps that assume browser automation is available
- Tests that could have been bash tests

## Phase 5: Question↔evidence match before reporting

Before stating "tests pass" or "feature works," apply **systematic-debug's Question↔evidence gate** (see `systematic-debug/SKILL.md`). Same rule, different moment: debug applies it at fix-claim time, test applies it at test-report time. The shared failure mode is reporting evidence that answers a different question than the one being claimed (e.g., "200 response" ≠ "response has the right data").

## Phase 6: Report results

Produce a test results summary with three sections:

1. **Bash tests:** Table of all tests run, pass/fail, key details
2. **Browser tests remaining:** Classified list with routing decision
3. **Manual test instructions** (if applicable): Structured steps per Phase 4

Update the relevant Grove task with results. If all bash tests pass and only trivial browser tests remain, the feature is "bash-verified, pending manual QA."

## Integration

- **← build:** Auto-chain from build Phase 8 — functional verification before "done."
- **↔ systematic-debug:** When a bash test reveals a bug, chain to systematic-debug for root cause analysis. Return here after the fix to re-run the failing test.
- **→ git-ops / ship-it:** Do not push or deploy until bash tests pass. Browser tests can follow deployment if the feature is behind a flag or low-risk.

## Anti-patterns

- **Browser-first testing.** Opening Chrome MCP to test an API endpoint that curl can hit directly. Adds rendering overhead for zero additional signal.
- **"It compiled" = "it works."** Code that runs without errors is not tested code. A 200 response with wrong data is worse than a 500.
- **Testing only the happy path.** Error responses, edge cases, and boundary conditions are where bugs live. If the test plan has no expected-error tests, it's incomplete.
- **Skipping decomposition.** Jumping straight to "run the whole flow in a browser" without asking "which parts of this flow can I test in isolation via curl?"
- **Calling "tests pass" without the question↔evidence check.** A green test on the wrong question is worse than a red test on the right one — it gives false confidence.
