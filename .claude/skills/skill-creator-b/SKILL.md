---
name: skill-creator-b
description: >
  Create, modify, audit, or sync skills — "new skill", "update skill",
  "sync skills", "isn't triggering", "add that to [skill]." Fires on ANY skill
  file edit. Not for using skills or memory edits.
metadata:
  version: "2026-06-09-01"
---

# skill-creator — build and maintain skills for Baylee's system

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

Skills source of truth: `fairbay/ops` (`.claude/skills/<name>/SKILL.md`).
Read `CONVENTIONS.md` from that repo via git-ops before any skill work.

**CRITICAL — stale snapshot interrupt.** If you are about to copy, read, or
edit a skill file from a stale source, stop.
- **Chat:** `/mnt/skills/user/` is a read-only snapshot frozen at session
  start. Always read from `fairbay/ops` via git-ops instead.
- **Code:** `.claude/skills/` in the repo is the synced copy. Read from it
  directly — it's current as of the last sync. For the authoritative
  version, read from `fairbay/ops` via git-ops.

This applies everywhere: inside this skill's workflow, inside other skills'
workflows (chat-archive encoding gate, build, etc.), and in ad-hoc edits.

Before writing or reviewing a skill body, read `references/patterns.md` for the
full pattern library — 16 patterns covering discovery, context economy,
instruction calibration, workflow control, and structure, distilled from
Anthropic's official guides and community best practice.

## When to create a new skill vs other options

| Signal | Action |
|--------|--------|
| Repeating the same workflow across sessions | New skill |
| A behavioral failure mode keeps recurring | Memory edit (behavioral override) |
| A one-off preference or fact | Auto-memory or project CLAUDE.md |
| A procedure within an existing skill's domain | Update existing skill |
| Two skills with overlapping triggers | Merge or sharpen routing |

---

## Phase 1 — Define before writing

### 1. Name concrete triggers

Write 2-3 actual prompts a user would type to trigger this skill. Not abstract
use cases — words someone would say in a chat. These become the test cases later.

### 2. Check for overlap

Read the current installed skill list. Would updating an existing skill be
better than creating a new one? If two skills could match the same input, the
trigger descriptions must explicitly route between them.

### 2b. Replace-vs-create check (family skills)

When the new skill belongs to an existing family (delegate-*, idea-*, etc.),
explicitly evaluate: should this REPLACE an existing family member rather than
add alongside it? Signs it should replace:

- The new skill's triggers are a superset of an existing sibling's.
- The existing sibling has never fired (check telemetry/skill-usage.yaml).
- Adding the skill would make the family >4 members (routing complexity).
- The new skill does the same job better, not a different job.

If replacing: rename or merge, don't leave both. Update all routing arrows in
sibling descriptions that reference the old skill.

### 3. One skill, one job

If the use cases serve different audiences or produce fundamentally different
output types, they are two skills. A skill that blurs categories (reference vs.
task, review vs. build, proactive vs. invoked) confuses both the agent and the
user.

---

## Phase 2 — Write the trigger description

The description is the highest-leverage text in the skill. Claude sees every
installed skill's description at startup. Wrong description = wrong firing.

### Budget: 200 characters

Not a guideline — a hard limit. Every character competes with every other
skill's description. Measure with `echo -n '...' | wc -c`.

Claude has a measured tendency to under-trigger skills. To counteract this,
descriptions should be slightly "pushy" — include contexts where the skill
should fire even when the user hasn't named it. But keep it under budget.

### What the description IS

The description states the role and trigger conditions — what cognitive mode
this skill represents and when to activate. It is NOT an enumeration of every
task shape, and it is NOT a methodology description.

### Required elements

1. **Trigger phrases.** 2-3 specific phrases a user would say. Written as
   natural language, not commands. More than 3 won't fit in the 200-char budget
   alongside routing arrows.
2. **Routing arrows.** "Not for X (→ other-skill)." Every skill sharing keywords
   with another skill needs these. Positive triggers pull in; exclusions push out.
   Both are needed.
3. **"Use proactively"** if the skill should auto-fire without being named.

### Examples

Good (concierge skill): `Plan trips, itineraries, restaurants, entertainment —
"plan a trip", "what should we do in X", "date night ideas", "weekend plans".
Not for routine calendar scheduling or quick errands.`

Bad: `Uses web search, maps API, and restaurant databases to create
comprehensive travel itineraries with day-by-day schedules.` (methodology, not
triggers; no routing arrows)

### Mode-switch resilience

Skills that fire at session boundaries (wrap-up, archive, quality review) are
most likely to be skipped. Add "CRITICAL: fires even in build-mode" to the
description for these skills.

---

## Phase 3 — Write the SKILL.md body

Read `references/patterns.md` before writing. It covers the full theory —
explain-the-why, control tuning, context budget, progressive disclosure, gotcha
placement, output templates, and more. This section covers the structural
template, conventions, and Claude.ai-specific guidance.

### Template

```markdown
---
name: skill-name
description: >
  [trigger description from Phase 2, under 200 chars]
metadata:
  version: "YYYY-MM-DD-NN"
---

# skill-name — one-line purpose

**Version gate:** Compare this skill's `metadata.version` against
`fairbay/ops/.claude/skills/<name>/SKILL.md` via git-ops
before doing anything else. If behind, warn once and continue.
If fetch fails, skip silently.

[Role framing: 1-2 sentences. Set the persona or cognitive mode.
Good example: "Act like a concierge — warm, organized, always thinking
two steps ahead." Bad example: "You are an AI assistant that helps with..."]

## [Workflow sections]

[Instructions. Imperative voice. Concise.]

## Integration
- **← source-skill:** What this skill receives.
- **→ target-skill:** What this skill hands off.
```

**Exemplars in Baylee's system:** When writing a new skill, read `build` for
philosophy sections + sandbox limitations + integration references, and
`cancel-unsubscribe` (examples dir) for autonomy tiering + concierge persona.

### Body conventions

- **Imperative voice.** "Check the repo" not "you should check the repo."
- **Version in metadata.** Bump on every change. Format: YYYY-MM-DD-NN.
- **Progressive disclosure.** Core in SKILL.md (under 500 lines), reference
  material in supporting files one hop away. Long reference files (300+ lines)
  get a table of contents. SKILL.md body stays in context for the entire
  session — every line is a recurring token cost.
- **Consistent terminology.** Pick one term and use it everywhere.
- **No time-dependent phrasing.** "Before August 2025..." dates the skill.

### Behavioral interrupts (proactive skills only)

For skills that auto-fire without being named, the description gets Claude to
LOAD the skill; body interrupts get Claude to USE it. Format:

"**If you are about to [recognizable action], stop.** [What to do instead.]"

Both are needed. The description is a trigger; the interrupt is the action.

### Autonomy tiering

Decide how much the skill asks vs. acts:
- **Tier 1:** Non-destructive. Proceed without asking.
- **Tier 2:** Reversible. State assumption and proceed.
- **Tier 3:** Destructive/irreversible. Plan-confirm required every time.

Default to action for reversible decisions. "If ambiguous, make a reasonable
assumption and proceed. State the assumption."

### Surface-specific guidance

Baylee's system runs across Claude.ai chat, Claude Code, and Routines. When
writing skills, keep instructions surface-neutral where possible. Known
surface-specific capabilities (see CONVENTIONS.md § Surface-Awareness):

- **No subagents → use delegate-* skills.** Can't spawn parallel runners.
  Instead: `delegate-adversarial` for skill body review (independent flaw-
  finding), `delegate-analytical` for description comparison across skills,
  `delegate-mechanical` for batch description length analysis or format checks.
  These ARE the subagent substitute — use them during skill creation, not just
  as things you teach other skills to use.
- **No hooks.** Can't attach PreToolUse/PostToolUse hooks. Use behavioral
  interrupts in the body instead.
- **No `/skill-name` invocation.** Skills fire from description matching only.
  The description must be good enough to trigger without explicit invocation.
- **`ask_user_input_v0` is available.** The best Claude.ai skills use it for
  structured input gathering — present tappable options instead of asking the
  user to type. Use for multi-step workflows where user choices shape the path.
- **`present_files` for deliverables.** Always present output files so the user
  can see and download them.

### Skill emerged mid-build

Skills often emerge from real failure modes during build sessions, not from
abstract planning. When a build session reveals a repeating pattern:

1. Note the pattern but finish the current build first.
2. At session wrap, if the pattern is real (happened 2+ times or will clearly
   recur), create the skill in the same session while the context is fresh.
3. If the session is too long, capture the pattern in the chat-status checkpoint
   and create the skill in a fresh session.

### Executable helpers

If Claude would reinvent the same helper script across invocations, bundle it
in `scripts/`. Scripts execute without loading source into context.

---

## Phase 4 — Test triggers

**Mandatory before Phase 5.** Untested descriptions ship broken.

### Generate test config

Create a JSON config for `scripts/test_skill_triggers.py`:

```json
{
  "target_skill": {
    "name": "skill-name",
    "description": "the description being tested"
  },
  "competing_skills": [...],
  "positive_cases": [...],
  "negative_cases": [...]
}
```

### Test case rules

**Positive cases** (should trigger): Write as natural prompts, not skill-aware
commands. "Which of my ideas would benefit from Workflows?" not
"delegate-analytical scan my vault." Don't nudge toward the skill with
size/bulk language. Include at least 3 cases covering different task shapes.

Make prompts realistic — include personal context, file paths, typos, casual
speech. A little backstory. Mix lengths. Focus on edge cases rather than
clear-cut matches. (Anthropic's official guidance: vague or short queries won't
trigger skills regardless of description quality because Claude handles them
directly. Test with substantive prompts.)

**Negative cases — false positive traps** (must NOT trigger): These are the
highest-value test cases. For each competing skill, write 1-2 prompts that
*sound* like they could match but belong to the competitor. Include: browse/
display requests, open-ended reasoning, build requests, queries using the
skill's keywords in a different domain. Include at least 5 — more than the
positive cases. False positives are harder to catch and more damaging.

**Competing skills list:** Include ALL skills that share keywords or task
domains. At least 3-4 most likely to cause confusion. Use their ACTUAL current
descriptions.

### Run and iterate

```bash
python3 scripts/test_skill_triggers.py config.json
```

- **All pass:** Proceed to Phase 5.
- **False negatives:** Description too narrow or abstract. Add specificity
  without exceeding 200 chars.
- **False positives:** Description overlaps. Add or sharpen routing arrows.
- **Iterate up to 3 times.** If still failing, the description may need a
  fundamentally different framing, or the skill needs splitting.

### Composability gap

Delegation skills that process data from other skills (e.g. "audit my vault
for X" = idea-vault + delegate-analytical) may not fire from description alone.
The data-access skill fires first; the delegation skill fires from body
interrupts after data is loaded. Test these cases as informational, not hard
failures.

---

## Phase 5 — Push and install

1. Write SKILL.md (and any supporting files) to `/home/claude/`.
2. Push to `fairbay/ops` via `git-ops`.
3. **Deliver per surface:**

   **Chat:**
   1. `present_files` so Baylee can review the raw SKILL.md.
   2. Package via `bash_tool`:
      ```bash
      cd /home/claude && zip -r <skill-name>.skill <skill-name>/
      cp <skill-name>.skill /mnt/user-data/outputs/
      ```
      Include supporting files (references/, scripts/) in the zip.
   3. `present_files` the `.skill` file. Only `.skill` gets the install
      button in Claude's UI. Baylee taps to install.

   **Code / Routines:**
   Git push IS delivery — skills are auto-discovered from `.claude/skills/`
   in the repo. No zip packaging or manual install needed. If the skill
   needs to reach other repos, run `sync-skills.py` (see CONVENTIONS.md
   § Skill sync).

---

## Skill sync workflow

When syncing ("sync skills", "are my skills up to date?"):

```bash
cd /home/claude/ops
PYTHONPATH=".claude/skills/git-ops/scripts:$PYTHONPATH" python3 scripts/skill_sync.py check
```

If drifted, run `package` to build `.skill` zips, then `present_files` for
batch install. Requires the repo to be cloned first and `GITHUB_PAT` exported.

---

## Skill modification workflow

**If you are about to edit a SKILL.md file as part of a broader implementation
plan (build, spec execution, migration) without routing through this skill's
workflow, stop.** Skill files have an installation ceremony (Phase 5: zip +
present .skill) that generic file pushes skip. Route the skill-modification
steps through this workflow, then return to the broader plan.

1. **Read current skill** from `fairbay/ops` via git-ops. **NEVER**
   from the session snapshot at `/mnt/skills/user/` — it may be stale and you
   will silently overwrite changes from other sessions. This is the #1 skill
   modification footgun.
2. **Make targeted edits.** Don't rewrite unless the fundamental approach is
   changing. Use the pattern library (`references/patterns.md`) to improve
   specific sections.
3. **Bump `metadata.version`.**
4. **Check description.** Does the modification change when the skill should
   fire? If so, update and re-test (Phase 4).
5. **Push and deliver** per Phase 5 (chat: zip + present; Code: push only).

---

## Skill audit workflow

When auditing ("audit my skills", "are my skills healthy?"):

1. List all installed skills.
2. For each, check:
   - **Description budget.** Over 200 chars? Flag for compression.
   - **Trigger overlap.** Shares keywords without routing arrows?
   - **Staleness.** References obsolete tools or time-dependent phrasing?
   - **Missing exclusions.** No "Not for..." or routing arrows?
   - **Instruction calibration.** Overuse of ALL CAPS imperatives without
     reasoning? Over-constrained where high freedom fits?
   - **Body size.** Over 500 lines? Split into references.
3. **Collision zone analysis.** For each pair of skills that share vocabulary,
   build a table:

   | User says | Correct skill | Why |
   |-----------|---------------|-----|
   | "build this" (after scout) | architect | Scout chains to architect |
   | "build this" (pointing at concept) | build | Wants working code |
   | "how would I build this?" | architect | Question = wants planning |

   Each row is a potential test case. The "Why" column reveals whether the
   routing arrow in the description is sufficient. If the distinction requires
   session context (what came before), that's a composability gap — note it
   but don't try to solve it with the description alone.
4. For flagged skills, generate test configs and run the harness.
5. Present findings as a table with recommended actions.

### Memory → skill migration

When Baylee says "audit memory edits" or the audit reveals procedural edits:

1. View current memory edits.
2. For each, classify: behavioral override? Essential reference data? Or
   procedure that should be a skill?
3. **Procedures** are instructions with steps, conditions, or decision trees.
   They belong in skills because skills trigger at the right moment; memory
   edits don't trigger — they're always-on context that may not be consulted.
4. Create the skill, verify it works, then remove the memory edit in the
   same session. Don't leave both — the duplication wastes context budget.

### Batch skill operations

When modifying 3+ skills in one session:

1. Pull all descriptions first. Check for overlap across the batch.
2. Write or modify descriptions before bodies — descriptions interact with
   each other; bodies don't.
3. Run collision zone analysis across the affected skill family.
4. Write/modify bodies.
5. Push all to git in one commit.
6. **Chat:** package each as a separate .skill zip, present all together.
   **Code:** push is delivery — no packaging needed.

---

## Memory edit conventions (quick reference)

When this skill creates or modifies a skill that replaces a memory edit:
- Remove the memory edit in the same session.
- Memory edits are behavioral overrides or essential reference data. Nothing else.
- Target: 9-12 edits. Count before adding.
- Full conventions: read CONVENTIONS.md from fairbay/ops.
