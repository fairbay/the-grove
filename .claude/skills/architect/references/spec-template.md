# SPEC.md template

The exact file architect's interview mode (Phase 5) writes. Copy the block verbatim, fill every bracket, keep the section numbering — the Self-check in SKILL.md counts against these headings. Unresolved items stay inline as `[NEEDS CLARIFICATION: ...]`.

```markdown
# [Project] — Product Spec

**Status:** draft | active | deprecated
**SDD Level:** spec-anchored
**Mission:** See [MISSION.md](MISSION.md) (authority for why this project exists)
**Created:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD
**Repo:** fairbay/...

---

## 1. What + Why

### Identity
[One sentence: "Type that helps user do action so they can outcome"]

### Primary User
[Named, specific]

### Problem Statement
[Concrete pain, 2-4 sentences]

### Non-Goals
- ...

---

## 2. Constraints

### Platforms
- ...

### Hard Constraints
- ...

### Dependencies
- ...

### Risk Flags
- ...

---

## 3. Data + Behavior

### Entities
| Entity | Fields | Notes |
|---|---|---|
| ... | ... | ... |

### User Flow (Happy Path)
1. [Entry]
2. [Step]
3. [Core value]
4. [Exit]

### User Stories (consumer-facing only)
- **US-001**: As a [persona], I want to [action], so that [outcome].
  - *Given* [context], *when* [action], *then* [result].
- **US-002**: ...

### Functional Requirements
- **FR-001**: System MUST ...
- **FR-002**: System MUST ...

### Edge Cases
- **When X fails:** [behavior]

---

## 4. Quality Contract

### Acceptance Criteria
- **FR-001**: Done when [observable].
- **FR-002**: Done when ...

### Success Criteria
- **SC-001**: [metric]

### Out of Scope (v1)
- [Feature] — revisit when X
- [Feature] — no

### Assumptions (unvalidated)
- ...

### Rules for Future Changes
- All changes must preserve FR-###, FR-###.

---

## 5. Open Questions
- [NC-001]: ...

---

## Changelog
- **YYYY-MM-DD**: Initial spec.
```
