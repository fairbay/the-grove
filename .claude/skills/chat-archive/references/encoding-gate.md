# Encoding gate reference

How to route findings from Step 3 (learnings) into the right destination.
Narrating a finding is NOT encoding it — every finding needs a tool call.

## Routing decision tree

| Finding type | Destination |
|---|---|
| Procedure or workflow with steps/conditions | Skill update (never memory edit) |
| Platform fact or API quirk | Skill reference file, or project CLAUDE.md |
| Behavioral principle (catches a recurring failure mode) | Memory edit (only if not covered by an existing edit/skill) |
| Preference or convention | Auto-memory or skill |
| One-off fix specific to this session | Session summary only |

Memory edits are reserved for behavioral overrides and essential reference data
that prevents real errors across all sessions. Anything that's a procedure goes
to a skill — skills trigger at the right moment; memory edits don't trigger,
they're always-on context that may not be consulted.

## Memory edit design principles

Use whichever form is shorter:
- **Directive:** "Do X first, then Y."
- **Interrupt:** "If about to X, stop. Do Y instead."

Before adding or modifying any memory edit:

1. **View current edits** (`memory_user_edits command=view`).
2. **Classify.**
   - **Behavioral override** = catches a failure mode or enforces a principle.
     Use directive or interrupt — whichever is shorter.
   - **Essential reference data** = prevents real errors if wrong (API
     quirks). Short, factual, no methodology.
   - Anything else (preferences, methodology, procedures, rationale,
     examples) → does NOT belong in memory edits. Route to a skill or
     auto-memory.
3. **Target: 9-12 edits total.** If adding would push past 12, something
   must be cut or moved to a skill. Count before adding.
4. **When folding into existing edits:** keep edits atomic and short. Do not
   append methodology, examples, or rationale. If new info doesn't fit in one
   line, it belongs in a skill.
5. **When replacing:** the replacement must be shorter or equal length. Every
   word competes for attention with every other word.

## Duplicate check

Before adding any new edit, run `conversation_search` with 1-3 content
keywords. If a prior session already encoded the same finding, don't
duplicate.

## Skill update conventions

When creating or updating skills during archive, route through `skill-creator-b`
for the full workflow (description testing, packaging, install ceremony). Key
rules that apply even outside skill-creator-b:

- **Trigger descriptions** must include "Not for..." routing arrows that
  disambiguate from similar skills.
- **Keep trigger descriptions focused** on when to fire, not what the skill
  does. Body handles methodology; description handles activation.
- **Bump `metadata.version`** on every change.

## When to defer skill work to a Routine

If applying skill changes would blow the remaining tool budget, create a Grove
task tagged `routine:skill-worker` with contractor-grade notes:

- Exact file path
- Exact change (before/after, or precise instructions)
- Rationale (why this change, what it catches)

Then narrate the deferral in the archive output. The routine picks it up async.

## Late-breaking lessons

If Baylee's response to the archive reveals a new lesson (or flags one missed),
apply it immediately — the archive isn't closed until Baylee stops responding.
