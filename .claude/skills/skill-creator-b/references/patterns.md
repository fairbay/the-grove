# Skill Authoring Patterns

Reference patterns distilled from Anthropic's official guide, the skill-creator
example, Anthropic engineering posts, and community analysis. Read this file when
writing or reviewing a skill body — it is not loaded at trigger time.

## Discovery patterns

These decide whether a skill fires at all.

### 1. Activation Metadata

The description field is the only signal Claude has at selection time. It is not a
summary — it is a set of conditions for when the skill should trigger.

Pack the description with both what the skill does and specific trigger phrases
users would say. Claude has a measured tendency to under-trigger, so descriptions
should be slightly "pushy" — include contexts where the skill should fire even
when the user hasn't named it.

**Baylee convention:** Trigger phrases + routing arrows + "use proactively" if
the skill auto-fires. Under 200 characters for Baylee's system (measured with
`echo -n '...' | wc -c`). The open Agent Skills spec caps at 1024 chars; Claude
Code truncates at 1536 chars. Baylee's budget is tighter because he has 30+ skills.

Good: `Plan trips, itineraries, restaurants, entertainment — "plan a trip",
"what should we do in X", "date night ideas". Not for calendar scheduling.`

Bad: `Helps with travel and entertainment planning using web search, maps, and
restaurant tools to create comprehensive itineraries.` (methodology, not triggers)

### 2. Exclusion Clause

A description that only says when to fire misses half the job. Without exclusions,
the skill triggers on tangentially related requests or hijacks work from siblings.

End descriptions with explicit routing: "Not for X (→ other-skill)." Positive
triggers pull a skill in; exclusions push it out. Both are needed.

**When to add exclusions:** Every skill that shares vocabulary with another skill
needs them. As the library grows, exclusion clauses must stay in sync.

### 3. Mode-Switch Resilience

Skills that fire at session boundaries (wrap-up, archive, review) are most likely
to be skipped because Claude is in build-mode. The casual instinct to summarize
inline is strongest right after shipping code — exactly when these skills matter
most.

Add "CRITICAL: fires even in build-mode" to the description for boundary skills.
Back it up with a behavioral interrupt in the body.

---

## Context economy patterns

Every token in a skill crowds out tokens from other skills, conversation history,
and the user's request. These patterns manage that budget.

### 4. Context Budget

Default assumption: Claude is smart. Don't explain what Claude already knows.
Each paragraph must justify its token cost. Test: "would removing this sentence
cause Claude to make a mistake?" If not, cut it.

Consistent terminology reduces cognitive load: pick one term ("field", not
"field / box / element") and use it everywhere. Avoid time-sensitive phrasing
("before August 2025...") that dates the skill.

### 5. Progressive Disclosure

Three loading levels:
1. **Frontmatter** (name + description) — always in context (~100 words)
2. **SKILL.md body** — loaded when triggered (under 500 lines)
3. **Bundled resources** — loaded on demand (references/, scripts/, assets/)

Keep the reference graph one hop deep. `SKILL.md → reference.md` is fine;
`SKILL.md → advanced.md → details.md` is not. Claude may partially read nested
chains and miss critical content.

Long reference files (300+ lines) get a table of contents at the top so Claude
can see the full scope even from a truncated read.

Scripts in `scripts/` can execute without loading their source into context.

---

## Instruction calibration patterns

These dial instruction specificity up or down.

### 6. Control Tuning

Match instruction freedom to task fragility:

- **High freedom** (text instructions, "use your judgment"): Open-ended tasks
  like code review, brainstorming, writing. Many valid approaches exist.
- **Medium freedom** (pseudocode, parameterized scripts): Preferred-but-flexible
  flows like deploy runbooks. The happy path is defined; edges are Claude's call.
- **Low freedom** (exact scripts, "do not modify this command"): Fragile
  operations like database migrations, secret handling, destructive actions.
  One wrong step is catastrophic.

Persona framing is part of the dial: "Act like a senior code reviewer focused on
correctness over style" sets the judgment rubric for the whole skill.

### 7. Explain-the-Why

Skills written as strings of ALWAYS, NEVER, MUST in capital letters give Claude
rigid rules with no context. The model follows the letter but misses edge cases.

State the rule, then explain why. The reasoning becomes the rubric for
unanticipated cases.

Good: "Use Supabase RLS policies for row-level access control. Client-side
filtering alone leaks data because the raw API is publicly accessible."

Bad: "MUST use RLS policies. NEVER filter client-side only."

**When bare imperatives are still correct:** Genuinely fragile steps where no
judgment call exists — exact CLI commands, secret handling, destructive actions.

### 8. Known Gotchas

The most valuable content in any skill. Based on real problems Claude encounters
when executing the skill. Update the gotchas section as new failure modes appear.

Place gotchas near the step where they apply, not in a separate section. Claude
is more likely to apply a gotcha when it appears in context right before the
relevant action.

---

## Workflow control patterns

### 9. Plan-Validate-Execute

For destructive or high-stakes skills: plan → show user → confirm → execute.
Never act before confirmation on destructive actions.

Tier the skill explicitly:
- **Tier 1:** Non-destructive, proceed without asking (reading, listing)
- **Tier 2:** Reversible actions, state assumption and proceed unless corrected
- **Tier 3:** Destructive/irreversible, plan-confirm required every time

### 10. Autonomy Calibration

When to ask vs. when to proceed. The worst failure mode is asking too many
questions — the user hired Claude to DO things. Default to action for decisions
that are easy to undo; pause for decisions that aren't.

Pattern: "If ambiguous, make a reasonable assumption and build. State the
assumption. Never ask more than 2 questions."

### 11. Memory Hygiene

For skills that interact with persistent data: "Always start completely fresh.
Never carry over [context-specific data] from prior conversation. DO use memory
to recall known preferences."

### 12. Behavioral Interrupts

For proactive skills (auto-fire without being named), the description gets Claude
to LOAD the skill; interrupts in the body get Claude to USE it.

Format: "**If you are about to [recognizable action], stop.** [What to do instead.]"

These fire on recognizable task shapes. Both the description trigger and body
interrupt are needed.

---

## Structure patterns

### 13. Executable Helpers

If Claude would reinvent the same helper script across multiple invocations,
bundle it in `scripts/`. Code serves as both tool and documentation.

For data-heavy skills, include a library of functions. Claude generates scripts
on the fly that compose those functions rather than reimplementing from scratch.

### 14. Template Scaffold

For skills that produce structured output, provide the exact output template.
Claude follows a template more reliably than it follows prose describing the
structure.

```markdown
## Scout output structure
ALWAYS use this exact template:
# [Idea Name]
## One-line pitch
## Impact score (1-5) with rationale
## Sustainability score (1-5) with rationale
## Business score (1-5) with rationale
## Verdict: [Greenlight | Workhorse | Lark | ...]
```

### 15. In-Skill Examples

Show concrete Input → Output pairs for format-sensitive skills. Keep them short
and representative of the target format — not exhaustive.

```markdown
## Commit message format
**Example:**
Input: Added user authentication with JWT tokens
Output: feat(auth): implement JWT-based authentication
```

### 16. Integration References

When a skill depends on or hands off to other skills, document the connections:

```markdown
## Integration
- **← idea-scout:** Reuse scout's user voice data.
- **→ ship-it:** Guide deployment after build.
```

---

## Review checklist

Use this when reviewing a skill (your own or someone else's). Each item maps
to a pattern above — the pattern number is in parentheses.

- [ ] Description has positive triggers AND exclusion clauses (1, 2)
- [ ] Description fits the character budget (1)
- [ ] SKILL.md body under 500 lines (5)
- [ ] No content Claude already knows (4)
- [ ] Rules explain why, not just what — unless genuinely fragile (6, 7)
- [ ] Gotchas placed near relevant steps, not in a separate section (8)
- [ ] Autonomy matches task fragility (6, 9, 10)
- [ ] Imperative voice throughout
- [ ] No time-dependent phrasing
- [ ] Integration references for skill dependencies (16)

## Anti-patterns

1. **Enumeration bloat.** Listing every task shape in the description instead of
   stating the cognitive mode. Body handles task shapes; description handles when.
2. **Methodology in description.** "Uses a 5-phase process to..." — this is HOW,
   not WHEN. The description answers WHEN; the body answers HOW.
3. **Explaining Claude to Claude.** "As an AI language model, you should..." — cut
   it all. Claude knows what it is.
4. **ALL CAPS imperatives as default.** MUST/ALWAYS/NEVER without reasoning.
   Reserve for genuinely fragile steps.
5. **Nested reference files.** SKILL.md → A.md → B.md. Keep it one hop.
6. **Testing after shipping.** Untested descriptions ship broken.
7. **Self-graded gates.** Checkpoints that ask "did you do X?" or "was the
   research thorough?" fail exactly when they're needed — a model that didn't
   notice its work was shallow will rubber-stamp the self-assessment too.
   Replace with mechanical gates: require enumerating what was actually done
   (list queries by category, count outputs) against hard minimums, failing
   if a category is empty.
