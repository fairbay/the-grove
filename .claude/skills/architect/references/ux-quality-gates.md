# UX Quality Gates — Reference

Loaded on demand by architect Phase 3/6 and ship-it Phase 2.5. Contains
evaluation frameworks, prompt templates, model routing, and surface-aware
guidance distilled from academic research and practitioner reports (June 2026).

## Table of Contents

1. User Story Interview
2. Heuristic UX Review
3. Domain-Specific Heuristic Sets
4. Plain Language / Readability
5. Model Routing for UI Generation
6. Cross-Model Review Strategy
7. Surface-Aware Routing
8. Model Selection Summary

---

## 1. User Story Interview

User stories are an **interview turn**, not a generation step. Claude proposes
personas and draft stories; Baylee corrects. Only Baylee knows whether the
personas reflect real user behavior.

### Quality framework: QUS (not INVEST)

**QUS** (Lucassen et al. 2016): 13 criteria across syntactic, semantic, and
pragmatic dimensions. The academic gold standard for user story quality
evaluation. **INVEST** is the practitioner mnemonic (6 criteria) — useful for
quick recall but less rigorous.

The 3 QUS criteria LLMs fail most (Sakib et al. 2026; Sharma et al. 2025):

1. **Independent** — stories overlap, sharing acceptance criteria. The #1
   AI failure mode. Claude self-checks before presenting draft to Baylee.
2. **Unique** — stories restate the same need in different words.
3. **Unambiguous** — acceptance criteria that restate the story instead of
   adding testable conditions.

### Interview flow (fits inside architect Phase 3)

**Turn N (Claude proposes):**

> Based on the problem statement and user flow, here are 3-4 personas and
> draft user stories. Each has acceptance criteria. I've checked for
> independence — no two stories share acceptance criteria.
>
> **Personas:**
> 1. [Name] — [context, including accessibility need if applicable]
> 2. [Name] — [expert/power user context]
> 3. [Name] — [different relationship to the product]
>
> **Stories:**
> - US-001: As a [persona], I want to [action], so that [outcome].
>   - Given [context], when [action], then [result].
> - US-002: ...
>
> What's wrong with these? Which personas am I missing? Which stories
> don't match how these people actually think?

**Turn N+1 (Baylee corrects):** Baylee adjusts personas, cuts/adds stories,
corrects behavioral assumptions. Claude revises and updates FRs to align.

### Persona requirements

- 3-4 named personas grounded in the problem statement
- At least one with accessibility needs (low vision, cognitive load
  sensitivity, limited literacy, non-native speaker)
- At least one expert/power user
- Never use "the user" — always a name with context

### Post-draft quality check (Claude runs before presenting)

- [ ] No two stories share the same "then" clause (Independent)
- [ ] No two stories restate the same need differently (Unique)
- [ ] Every acceptance criterion adds a testable condition beyond the story
      text (Unambiguous)
- [ ] At least one story covers an error or edge case
- [ ] At least one story is from the accessibility persona
- [ ] Stories cover the full happy path (entry → core value → exit)

---

## 2. Heuristic UX Review

### The case for structured heuristics (and against generic AI critique)

Jakob Nielsen and Baymard Institute tested generic ChatGPT-4 screenshot
review: only 19% of recommendations were sound UX advice; 9% were directly
harmful. But Baymard's purpose-built UX-Ray (346 domain-specific heuristics)
achieved 95% accuracy across 79 websites. The difference isn't AI vs human —
it's generic prompting vs domain-specific evaluation.

Implication: never ask an LLM "what's wrong with this UI?" without a
structured framework. Always provide the specific heuristics to evaluate
against.

### Prompt template for heuristic evaluation

Use with Gemini (AI Studio for screenshots, delegate-adversarial for URL
Context in Claude Code). Gemini's multimodal visual understanding is
stronger than Claude's for layout/design assessment.

```
You are a senior UX evaluator conducting a heuristic evaluation.

Target audience: [describe — e.g., "Medicaid members choosing health plans,
primarily mobile, often low digital literacy"].

Evaluate the interface against EACH heuristic below. For each, report:
1. Heuristic name and ID
2. Status: PASS | MINOR | MAJOR | CRITICAL
3. Finding: specific issue (or "No issues found")
4. Evidence: what you see that demonstrates the issue
5. Recommendation: specific fix

[INSERT DOMAIN-SPECIFIC HEURISTICS FROM SECTION 3 BELOW]

Additionally evaluate:
- Reading level: estimate Flesch-Kincaid grade level of all visible text
- Jargon: list terms the target audience might not understand
- Cognitive load: flag screens with >7 actions or >3 info hierarchy levels

Output as a structured table, one row per heuristic.
```

### Severity scale

| Level | Label | Meaning |
|-------|-------|---------|
| 0 | PASS | No issue |
| 1 | MINOR | Cosmetic. Fix if time allows. |
| 2 | MAJOR | Impacts task completion. Fix before launch. |
| 3 | CRITICAL | Blocks task. Must fix immediately. |

Pass criteria for launch: no severity-3 findings. Severity-2 findings
should be addressed or have a documented deferral reason.

---

## 3. Domain-Specific Heuristic Sets

Use the set that matches the project. Combine with the base prompt template
in Section 2. These supplement (not replace) Nielsen's 10 — include both
the domain set and the relevant Nielsen heuristics.

### Health literacy / civic tech (Medicaid, public-good tools)

H-HL1. **Plain language** — No jargon, acronyms, or technical terms in
        user-facing text. "MCO" → "your health plan." Acronyms expanded on
        first use, then avoided entirely if possible.
H-HL2. **Reading level** — All UI text ≤8th grade Flesch-Kincaid. Error
        messages and instructions ≤6th grade.
H-HL3. **Cultural sensitivity** — No assumptions about literacy, language,
        income, or technology access. Default to the lowest-confidence user.
H-HL4. **Action clarity** — Every screen has one obvious next step. No
        ambiguous CTAs. "Compare plans" not "View options."
H-HL5. **Trust signals** — Data source attribution visible. "Updated [date]"
        on factual content. No claims without source.
H-HL6. **Mobile-primary** — Touch targets ≥48px (not just 44px — larger for
        users with motor difficulties). No horizontal scroll. Key info
        above the fold on a 375px screen.
H-HL7. **Cognitive load** — ≤5 choices per screen. Progressive disclosure
        for complex information. No decision fatigue.
H-HL8. **Error recovery** — Clear path back from dead ends. No blank
        states without guidance. Every "no results" has a next step.

### E-commerce / product tools

H-EC1. **Purchase confidence** — Price, availability, and shipping visible
        without scrolling. No surprise costs at checkout.
H-EC2. **Comparison support** — Side-by-side comparison of options with
        consistent attributes.
H-EC3. **Decision simplification** — Defaults, recommendations, and "most
        popular" signals to reduce choice overload.
H-EC4. **Trust and credibility** — Reviews, ratings, return policy visible.
H-EC5. **Cart/state persistence** — Selections preserved across sessions.
H-EC6. **Mobile checkout** — Minimal form fields, autofill support,
        single-page checkout preferred.

### Developer tools

H-DT1. **Code/technical accuracy** — Examples compile/run. API references
        match current version.
H-DT2. **Copy-paste readiness** — Code blocks, commands, config values
        selectable and copyable.
H-DT3. **Progressive complexity** — Quick start → detailed docs → reference.
H-DT4. **Error messages** — Include the error code, what went wrong, and
        how to fix it. Link to relevant docs.

---

## 4. Plain Language / Readability

### Metrics and targets

| Project type | FK Grade | Reading Ease | Notes |
|---|---|---|---|
| Public-good / health / civic | ≤8th grade | ≥60 | Medicaid population |
| Consumer app | ≤10th grade | ≥50 | General public |
| Developer tool | ≤12th grade | ≥40 | Technical audience |

### Programmatic check (preferred when code is available)

```bash
pip install textstat --break-system-packages
python3 -c "
import textstat
text = '''[paste extracted UI text]'''
print(f'FK Grade: {textstat.flesch_kincaid_grade(text):.1f}')
print(f'Reading Ease: {textstat.flesch_reading_ease(text):.1f}')
print(f'SMOG: {textstat.smog_index(text):.1f}')
"
```

### Common failure patterns in AI-built UIs

- Variable names leaking into labels (camelCase in user-facing text)
- Acronyms without expansion (MCO, VAS, ILOS)
- Passive voice in instructions ("Benefits can be viewed" → "View benefits")
- Information density too high on mobile

---

## 5. Model Routing for UI Generation

### The evidence

Gemini consistently outperforms Claude on visual design quality:

- WebDev Arena (human-preference): Gemini 2.5 Pro #1 at 1420 ELO, Claude
  3.7 Sonnet at 1357 — a 60+ point gap.
- Landing page redesign benchmark: Gemini 85 pts (1st), Claude 75 (3rd).
- 7-model dashboard test: Gemini 3 Pro won 1st over Claude Sonnet 4.5.
- Google's Generative UI study: users preferred AI-generated UI 90% of the
  time vs regular websites.

Meanwhile, Claude produces cleaner, more idiomatic code, handles large
codebases better, and is the stronger orchestrator/debugger.

### Division of labor

| Responsibility | Model | Why |
|---|---|---|
| Spec, data layer, business logic | Claude | Architectural reasoning, code quality |
| API integration, testing | Claude | Better at debugging, large codebases |
| UI component design, layout, styling | Gemini | Visual design quality, design fidelity |
| Integration of UI with data/logic | Claude | Architectural coherence |
| Deployment, DevOps | Claude | Existing skill infrastructure |

### Practical surfaces for Gemini UI work

**Google AI Studio** (manual, full capability):
Paste spec + user stories + reference screenshots into the "Build" section.
Select Gemini 3 Pro. Gemini generates React/Tailwind components. Copy output
back to Claude for integration. Best for: initial component design, visual
iteration, when you want to see and adjust the visual output directly.

**Gemini MCP Server** (automated, Claude Code):
MCP server at glama.ai/mcp/servers/bobvasic/gemini-mcp-server lets Claude
Code call Gemini for UI design work. Claude orchestrates, Gemini designs.
Best for: integrated workflow where you don't want to context-switch.

**Google Stitch** (wireframe → polished UI):
Free tool. Upload screenshots, wireframes, or sketches → get polished UI
designs. Generates up to 5 interconnected screens. Best for: converting
rough sketches or existing meh UIs into polished versions.

**Antigravity CLI** (terminal):
Gemini CLI's successor (June 2026). Can run alongside Claude Code in a
separate terminal for UI-specific tasks. Best for: developers comfortable
with dual-terminal workflows.

---

## 6. Cross-Model Review Strategy

### Why cross-model review matters

A model reviewing its own output retraces the same reasoning paths.
Research consistently shows cross-model review catches different issues.

### Baylee's system mapping

| Phase | Builder | Reviewer | Why |
|-------|---------|----------|-----|
| User stories | Claude (architect) | Baylee (interview) | Only Baylee knows if personas match reality |
| UI components | Gemini (AI Studio) | Claude (integration) | Claude catches architectural issues |
| Built interface | — | Gemini (heuristic eval) | Gemini's visual understanding for design critique |
| Plain language | Claude (inline) | Programmatic (textstat) | Readability scores are objective |

### Context isolation for reviews

When running heuristic review:
- Do NOT include spec or interview context. The reviewer sees the built
  artifact fresh, like a real user would.
- DO include: target audience description, readability targets, the
  domain-specific heuristic set.
- DO provide: screenshots of key screens or live URL.
- DO NOT provide: reasoning for why things were built that way.

---

## 7. Surface-Aware Routing

**Terminology note:** `delegate-adversarial` is the skill that calls the
Gemini API. It handles text review, URL-based review, and file-based review
— all via Gemini. When this document says "use Gemini" in Claude Code, the
mechanism is always `delegate-adversarial`. When it says "use AI Studio,"
Baylee pastes the prompt directly — no skill involved.

### Heuristic review

| Surface | Approach |
|---------|----------|
| **Chat (claude.ai)** | Output a copy-paste prompt (Section 2 template + domain heuristics from Section 3) for Baylee to paste into Google AI Studio with screenshots. Claude cannot pass screenshots to Gemini from chat. |
| **Claude Code** | Use `delegate-adversarial` with URL Context (live URL). Gemini evaluates the live site directly. |
| **Manual (Baylee)** | Open AI Studio, paste the prompt, upload screenshots, review findings directly. Most control. |

### UI generation

| Surface | Approach |
|---------|----------|
| **Chat** | Claude generates spec + user stories. Output a handoff prompt for Google AI Studio or Stitch. Baylee brings components back. |
| **Claude Code** | Gemini MCP server if available. Otherwise, Claude builds data/logic, outputs a handoff for Gemini UI generation. |
| **Mixed** | Claude Code for data layer + Claude AI Studio for Gemini UI iteration. Combine in the repo. |

---

## 8. Model Selection Summary

| Task | Best model | Surface | Notes |
|------|-----------|---------|-------|
| User story draft | Claude | Architect interview | Interactive — Baylee validates |
| UI component design | Gemini 3 Pro | AI Studio / Stitch / MCP | Visual design quality |
| Data layer / API | Claude | Claude Code / chat | Code quality, debugging |
| Heuristic eval (visual) | Gemini | AI Studio (screenshots) | Visual understanding |
| Heuristic eval (live URL) | Gemini | delegate-adversarial | URL Context |
| Plain language check | textstat + Claude | Programmatic + scan | Objective scores |
| Accessibility audit | Lighthouse + Claude | CLI + code review | WCAG compliance |
| Integration / wiring | Claude | Claude Code | Architectural coherence |
| Debugging | Claude | Claude Code | Better at error diagnosis |
