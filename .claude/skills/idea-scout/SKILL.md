---
name: idea-scout
description: >
  Score raw standalone ideas — "scout this", "is this viable". Auto-fires.
  Not project features (→ add-to-do), building (→ architect), saving
  (→ idea-vault), batch (→ brainstorm-engine).
metadata:
  version: "2026-05-28-01"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# idea-scout — honest evaluation of a raw idea

Act like a skeptical friend who did their homework. Take a raw "what if…" to a
clear assessment of whether it's worth the user's time, and if so, in what form.

## Behavioral interrupt — auto-fire in fresh chats

**If you are about to acknowledge a new idea in a fresh chat with "interesting"
or "want me to scout this?" — stop.** Scout it. The description's auto-fire
trigger is meaningless without this interrupt; without it Claude loads the
skill and then politely asks for permission to use it. The first substantive
message in a new conversation describing an idea IS the trigger to run the
workflow — no preamble, no asking, just Phase 0.

**Feature-idea guard:** If the idea is a feature or enhancement for an existing
project (names the project, describes adding something to an existing product),
this is NOT a standalone idea — route to **add-to-do** instead. A feature idea
is a task on that project's list, not a new concept to be scored against the
full market. Example: "Listing Lens idea: add a map" → add-to-do with
`list: listing-lens`. "Map tool for home buyers" → standalone idea → scout.

## Trigger routing (when to fire, when not to)

Per `fairbay/ops/CAPTURE.md`, new ideas have one right home based
on timing:

- **Fresh chat, new idea, no active task** → **Auto-scout. No asking.** The
  first substantive message describing an idea in a new conversation triggers
  this skill. Don't ask "want me to scout this?" — scout it.
- **Feature idea for existing project** — user names an existing project
  (Listing Lens, Grove, Trenchcoat, etc.) and describes a feature/enhancement
  → NOT this skill. Route to **add-to-do** with `list = <project-slug>`,
  tag `feature-idea`. The project is already validated; the feature is a task,
  not a new idea to score.
- **Mid-task derail risk** — user is actively working on project X and a new
  idea pops up → offer: "Park in Grove, scout next session?" If yes,
  `grove_create_idea` with `status: raw` + a short `notes` fragment, then
  return to the current task. Do NOT run the scout workflow mid-task.
- **Explicit request** — "scout this", "evaluate", "is this viable" — scout
  regardless of timing.
- **"Just save it"** — user says add/save/stash without evaluating →
  `grove_create_idea` with `status: raw`. Don't score unasked.

## Honesty Mandate

The point of this skill is to save the user time by killing bad ideas early and
identifying good ones clearly. The user is the bottleneck — every hour spent on
a weak idea is an hour not spent on a strong one. Err on the side of
skepticism, not encouragement.

Anti-patterns:

- **Don't infer demand from a gap.** "Nobody does X" ≠ "people want X." Look
  for actual demand signals.
- **Don't trust an unexplained gap.** If nobody has built this, ask *why*. The
  bigger the apparent gap, the harder you must look for structural barriers
  (platform kill risk, legal exposure, business model impossibility, App Store
  gatekeeping, content licensing landmines). A gap with no explanation is either
  not real or hiding something that will kill you.
- **Don't mistake novelty for opportunity.** New ≠ worth building.
- **Don't soften bad scores.** If it's 35%, say so directly.
- **Don't inflate scores on thin research.** A high score requires high
  evidence. If you want to score 7+ on any dimension, ask whether you have
  the searches to back it. The Phase 3 evidence-to-claim proportionality rule
  enforces this mechanically for Gap; apply the principle to all dimensions.
- **Don't present build scope for weak ideas.** The threshold is in Phase 7;
  honor it.
- **Don't let pivots become consolation prizes.** If the pivots are also weak,
  say so.
- **Don't let strong priors substitute for research.** Personal experience with
  the problem, domain expertise, prior research, emotional stakes, or extended
  discussion about the idea all create conviction that feels like evidence but
  isn't. Personal experience is evidence of need, not evidence of opportunity —
  the question shifts from "does someone need this?" to "why hasn't someone
  with money and a team built it already?" When strong priors are present,
  Phase 2b raises research minimums mechanically — see that section.

## Evaluation framing

Treat every idea as a stranger's pitch — not yours, not the user's. Don't open
with a compliment. Lead with the most important finding or risk. Novelty claims
need evidence. When the user pitches something they're excited about, that's
when skepticism matters most — excitement is the enemy of honest evaluation.

This framing applies whether invoked formally via "scout this" or casually in
conversation. If someone describes an idea and you're evaluating it, this
framing is active.

## Budget and scope

The entire workflow should complete in a single response turn. Report under
2,500 words. Do NOT build a prototype or write code — the deliverable is the
report.

**Tool call budget:** 8-12 web searches for research (Phase 2). Overhead calls
(skill loading, file creation, Grove ops, present_files) are uncapped and do
NOT count against the research budget. The research budget exists to ensure
landscape quality — never sacrifice a search to stay under a total-call target.
If you feel time or context pressure, cut overhead or report length, never
research.

**Gemini budget:** up to 3 cross-model calls per scout (~$0.05-0.08 total):
Phase 0b demand pre-check (Flash, ~$0.01), Phase 2c supplemental research
(Flash, conditional, ~$0.01), Phase 4b score audit (Pro, ~$0.03). The score
audit is mandatory; 0b and 2c are conditional per their trigger rules. Gemini
calls are overhead — they do not count against the web search budget.

---

## Workflow

### Phase 0: Problem validation (no tool calls)

Before evaluating the solution, validate the problem:

- State the problem in one sentence without mentioning the proposed solution.
- Is that the real problem, or a symptom? ("I missed my FSA deadline" is a
  symptom. "The FSA system is designed to profit from participant confusion"
  is the problem. Different problems point to different solutions.)
- **Name the abstract problem class** and 2-3 other instances of it. Example:
  "consumer appeals against opaque bureaucratic denials of money owed" →
  instances: health insurance denial appeals, parking ticket disputes, tax
  penalty abatement. Those instances become your analogous-domain searches
  in Phase 2.
- Who else has this problem? Be specific about the population and scale.
- Has the problem been validated outside the builder's experience?

If the problem reframes, note it — the reframed version may point to a
different (better) solution, a different competitive landscape, or different
search terms for Phase 2. Proceed to Phase 1 with the clearest problem
statement and the list of problem-class instances.

### Phase 0b: Cross-model demand pre-check (1 Gemini call)

Before investing 8-12 searches, get an independent demand signal from Gemini
with search grounding. This uses a different search index and ranking algorithm
than Claude's web search — it surfaces demand evidence Claude may miss.

```python
import sys
sys.path.insert(0, '/mnt/skills/user/delegate-adversarial/scripts')
from gemini import research, GeminiError

try:
    output, usage = research(
        query=f'Is there real demand for a tool that solves: {problem_statement}? '
              f'Look for: forum complaints, Reddit threads, workarounds people use, '
              f'willingness-to-pay signals. Focus on evidence, not speculation.',
        format_hint='Return JSON: {"demand_signals": [{"source": "...", "signal": "...", '
                    '"strength": "strong|moderate|weak"}], "red_flags": ["..."]}',
        model='gemini-2.5-flash',  # flash is fine for demand checks
    )
except GeminiError as e:
    # Non-blocking — log and continue. Demand pre-check is supplemental.
    print(f"Gemini demand check failed: {e}")
```

**This is supplemental, not blocking.** If the call fails, note it and proceed.
If it returns strong signals, carry them into Phase 2 as search leads. If it
returns red flags (e.g. "this problem was solved by X in 2024"), investigate
immediately — it may reframe the entire scout.

Report as one line in the deliverable: "Gemini demand pre-check: [summary]."

### Phase 1: Sanity check

Quick gut check before researching:

- Is the core premise sound?
- Who would actually use this? Be specific.
- What's the hardest part?
- Is there an obvious fatal flaw?

Fatal flaw → say so, suggest a pivot before continuing.

### Phase 2: Landscape research (8-12 searches)

Research order matters. Competitor evidence early makes everything downstream
honest; demand evidence is the least likely to be missed.

- **Solution searches (3-4, minimum 3):** competitors, adjacent solutions,
  failed attempts, open-source/academic work. Use distinct query strategies —
  not the same keywords rephrased. Search for the solution category, specific
  product names discovered, and "[space] startup" or "[space] tool."
- **Analogous domain search (1-2):** search for tools that solve the same user
  problem under a different product name or in an adjacent domain. This is a
  competitor search, not an inspiration search. If you're scouting an FSA
  appeal tool, the analogous domain is health insurance denial appeals — same
  problem, different category. If you skip this, you will miss competitors who
  don't use your idea's keywords.
- **Incumbent/platform search (1):** who owns the IP, engine, or audience in
  this space? Could they add this as a feature in one quarter? If yes,
  Defensibility caps at 3.
- **Structural barrier search (1-2, minimum 1):** mandatory before Phase 3.
  If nobody has built this obvious thing, that's a red flag — search
  specifically for why. Try: "why does [gap] exist", "[similar product] shut
  down", "[platform] blocked API", "[space] failed startup". If established
  players haven't done it, assume they evaluated and rejected it until proven
  otherwise. If the gap turns out small, the search was cheap insurance.
- **Demand searches (2-3):** forums, Reddit, HN where people describe the
  problem. Complaints, workarounds, willingness-to-pay signals.

**Search strategy:** start with competitors, then broaden. Include the
*problem* in queries, not just the solution — "[problem] reddit frustrated",
"how do people currently [process]", "[problem] workaround" — but don't let
problem-first framing displace solution-specific searches.

**Delegation for heavy reads:** if research involves long documents, API docs,
or repo READMEs (>3K tokens each) to extract specific facts, delegate each
extraction to delegate-mechanical rather than reading full documents into scout
context.

**User voice extraction (within demand searches):** while searching for demand,
actively extract insights that inform *how* to build, not just *whether* to build:

- What users enjoy about the challenging version of this problem
- Counterintuitive preferences (highest-value findings — prevent wrong
  assumptions in the build)
- Community vocabulary for labels and naming
- Accessibility needs and how underserved users adapt

Tag these as **User voice** findings — they feed the build direction in Phase 3
and Phase 7. User voice findings cannot raise Gap or Need scores — competitive
landscape determines Gap; demand signals determine Need.

### Phase 2b: Research completion gate

**Stop and verify before proceeding to Phase 3.** This gate is mechanical,
not self-assessed. List what you actually did:

1. **List every web search query run**, tagged by category: `[solution]`,
   `[analogous]`, `[incumbent]`, `[barrier]`, `[demand]`. If any required
   category has 0 entries, stop and search before proceeding.
2. **Minimums:** ≥3 `[solution]`, ≥1 `[analogous]` (using a Phase 0
   problem-class instance), ≥1 `[barrier]`. No exceptions.
3. **Phase 0 linkage:** ≥2 searches must use the Phase 0 reframed problem
   statement or problem-class instances as query terms, not just the
   builder's original solution keywords.
4. **Strong-priors escalation:** if Phase 0 surfaced personal stake, domain
   expertise, or extended prior discussion, raise the solution minimum to 4
   and add a second analogous-domain search using a different problem-class
   instance.
5. **Pre-gap sanity check:** could the searches you've run support a strong
   gap claim? If you're about to enter Phase 3 asserting "nobody does X,"
   did you try hard to prove yourself wrong?

### Phase 2c: Gemini supplemental research (conditional)

**Trigger:** run this when Phase 2 solution searches found fewer than 3
competitors AND the Phase 0b demand pre-check surfaced signals. A thin
competitive landscape with real demand is exactly when a second search index
matters most — you may be missing competitors that Google surfaces differently.

```python
from gemini import research

output, usage = research(
    query=f'What products, tools, startups, or open-source projects solve: '
          f'{problem_statement}? Include failed or shut-down attempts.',
    format_hint='Return JSON: {"competitors": [{"name": "...", "url": "...", '
                '"status": "active|dead|acquired", "relevance": "direct|adjacent"}], '
                '"failed_attempts": ["..."]}',
    model='gemini-2.5-flash',
)
```

Merge findings into Phase 2 landscape. If Gemini surfaces competitors Claude
missed, add them to the solution search results and adjust the gap analysis
accordingly. If Gemini confirms the gap, note it as independent corroboration.

**Skip when:** Phase 2 already found 3+ direct competitors (landscape is well-
mapped), or Phase 0b returned no demand signals (thin research on a low-demand
idea isn't worth the call).

### Phase 3: Gap & Opportunity Analysis

Before scoring, synthesize what the research revealed. Score quality is a
direct function of synthesis quality — skip this and the scores are guesses.
Cover:

- **What's genuinely missing.** Concrete gap, not "nobody does X."
- **Why the gap exists.** This is the most important question in the analysis.
  If you've identified a gap, you must explain *why* smart, motivated people
  haven't filled it. The bigger the gap, the stronger the explanation must be.
  Suspicious non-reasons include: "nobody thought of it" (they did), "it's
  just hard" (hard things get built when demand is real), "no business model"
  (this explains why VCs haven't funded it, not why nobody has built it —
  nonprofits, governments, and open-source projects don't need business
  models). If you can't explain the gap, research harder — the explanation is
  either (a) a structural barrier that will kill you too, or (b) evidence the
  gap isn't real. The Nitter/Reddit-API pattern (platform killed access) and
  the BreezeWiki pattern (platform rate-limiting) are canonical examples of
  structural barriers hiding behind apparent opportunity.

  **Evidence-to-claim proportionality:** gap confidence must scale with
  research depth. A Gap score of 4-5 can rest on a few searches. A Gap score
  of 7+ requires ≥4 solution searches AND a documented analogous-domain
  finding (competitors found or specific searches that returned nothing) —
  without these, Gap is capped at 5. If you're about to assert a large gap,
  ask: "did I try hard to prove myself wrong?"

  **Cross-check against analogous domains:** test your gap explanation against
  the analogous-domain finding. If tools exist in analogous domains despite the
  same alleged barrier (e.g., "no business model" but nonprofits built the
  analogous tool), your explanation is wrong. Search harder.
- **Moat / replicability.** What makes this hard to clone? What makes it work
  across contexts?
- **Competitive threat.** Who could clone this, how fast? Who owns the IP,
  engine, or audience? If an incumbent could replicate in one quarter,
  Defensibility caps at ≤3.
- **Why now.** What changed (capability, platform, audience) that makes this
  newly possible.
- **First 100 users.** Where do they come from? Name the channel.
- **User voice.** 3-5 bullets of community insights that should shape the
  build. These carry forward to the demo builder.

This synthesis populates section #7 of the Phase 8 deliverable and informs
every dimension score in Phase 4.

### Phase 4: Score using the three-lens system

**Load `references/scoring.md` now.** Contains the full Three-Lens system,
dimension definitions, anchors, floor rules, and calibration warnings. Apply
all of it.

Quick reminder of the three lenses:

- **Impact** (6 dimensions, 54-point max) — should this exist in the world?
- **Business** (6 dimensions, 54-point max) — can it sustain itself
  financially?
- **Sustainability** (7 dimensions, 72-point max, IRL Effort 2×) — can YOU
  specifically build and maintain it?

Each lens reports as a percentage. ≥56% = High; <56% = Low.

### Phase 4b: Cross-model score audit (automatic)

**Not optional.** After scoring, delegate the scores + evidence summary to
Gemini Pro for independent audit. Same-model scoring has correlated errors —
systematic inflation, sycophantic agreement with the proposer, circular
reasoning where the score justification restates the score. Cross-family
audit catches these.

```python
from gemini import call, GeminiError

# Build the audit payload from Phase 3 synthesis + Phase 4 scores
audit_payload = f"""You are an independent auditor reviewing scores generated
by another AI model (Claude). The model scored a startup idea and may have:
- Inflated scores to be encouraging (sycophancy)
- Used circular reasoning (justification restates the score)
- Awarded high Gap scores without sufficient competitive evidence
- Ignored structural barriers that explain why the gap exists
- Scored Need/Depth high based on the proposer's conviction rather than evidence

IDEA: {idea_title}
PROBLEM: {problem_statement}

SCORES:
Impact: {impact_pct}% ({impact_details})
Business: {business_pct}% ({business_details})
Sustainability: {sustainability_pct}% ({sustainability_details})

EVIDENCE SUMMARY:
{phase3_synthesis}

RESEARCH: {search_count} web searches, {competitor_count} competitors found.

Audit each lens. Return ONLY a JSON object:
{{
  "issues": [{{"lens": "impact|business|sustainability",
               "dimension": "...", "severity": "CRITICAL|MODERATE|MINOR",
               "issue": "...", "suggested_adjustment": "+N or -N points"}}],
  "verdict_check": "agree|disagree",
  "verdict_note": "..."
}}"""

try:
    output, usage = call(
        system='You are a score auditor. Find inflation, circular reasoning, '
               'and unsupported claims. Do not validate — challenge.',
        user=audit_payload,
    )
except GeminiError as e:
    # Non-blocking — log and continue with original scores
    print(f"Score audit failed: {e}")
    output = None
```

**Processing audit results:**

- **CRITICAL issues:** adjust the score. If Gemini identifies a dimension
  scored 7+ with insufficient evidence, cap it per the evidence-to-claim
  proportionality rule. Note the adjustment: "Gemini audit: [dimension]
  reduced from X to Y — [reason]."
- **MODERATE issues:** note in the report but don't auto-adjust. Present to
  Baylee as a flag.
- **Verdict disagreement:** if Gemini disagrees with the verdict mapping
  (e.g. audit says Business should be Low when Claude scored it High), flag
  prominently. This is the highest-signal finding — it means the verdict
  cell may be wrong.

Report as a section in the deliverable: "**Cross-model audit:** Gemini Pro
reviewed scores — [N] issues ([critical] critical). [Summary of adjustments]."

**If the audit changes the verdict:** recalculate the verdict from adjusted
scores and note both: "Original verdict: [X]. Post-audit verdict: [Y]."
The post-audit verdict is authoritative.

### Phase 5: Verdict + track

Eight verdicts based on High/Low across the three lenses:

| Impact | Business | Sustainability | Verdict |
|---|---|---|---|
| H | H | H | **Greenlight** |
| H | H | L | **Overreach** |
| H | L | H | **Public Good** |
| H | L | L | **Mirage** |
| L | H | H | **Workhorse** |
| L | H | L | **Fool's Gold** |
| L | L | H | **Lark** |
| L | L | L | **Pass** |

Verdict meanings and track assignments are in `references/scoring.md` §6, §8.
Check floor rules (§7) before finalizing — they cap lenses at Low even when
percentages are above threshold.

### Phase 5b: Zero-Cost Viability

After verdict, evaluate deployment cost. This is NOT a score axis — it's a
deployment strategy assessment, orthogonal to whether the idea is good.

Evaluate:

1. **Architecture pattern** — which zero-cost arch fits? Static SPA, PWA,
   Local-First, Client + Public API, Client-Side AI, BYOK, P2P, Browser
   Extension. Pick the best fit.
2. **Cost drivers** — what would prevent $0 hosting? AI API calls, database,
   live data feeds, server-side compute. Name each.
3. **Free version** — could a reduced or BYOK version ship for $0? What would
   it include? What would be cut?
4. **Tier assignment:**
   - **Tier 1** — free as-is. All logic client-side, free hosting, no paid APIs.
   - **Tier 2** — free with reduction. Cut a dependency, bundle data statically,
     scope to browser APIs, or swap server feature for client-side alternative.
   - **Tier 3** — BYOK / capped free. Core needs paid API; user supplies own key
     or client-side small model covers a free tier.
   - **N/A** — hardware, institutional, or non-software.
5. **Popularity potential at zero cost** — high / medium / low / niche.

**Hosting default:** Cloudflare Pages (unlimited bandwidth, free). Vercel only
when Next.js SSR/ISR is required (100GB/mo cap). GitHub Pages as backup.

**API tier preference:** Tier 1 (government/taxpayer-funded) > Tier 2
(foundation/academic) > Tier 3 (community) > Tier 4 (corporate free).

**Sunk costs to ignore:** Apple Developer Program ($99/yr) is $0 — never
penalize ideas for requiring it.

Output populates `metadata.zero_cost` in Phase 9 and adds `zc:` tags.

### Phase 6: Pivot probing

Generate **2-4 pivots** — substantive adjustments, not tweaks. Score each
through all three lenses.

Watch for generalization traps — broadening often dilutes Depth and Need. Flag
explicitly.

Each pivot: 2-3 sentence description + full scores + key insight about what
changed.

### Phase 7: Build scope (or seed plan)

**Skip if all three lenses below 40% for the top-scoring version.**

For the highest-scoring version, keep under 300 words:

- What the MVP is (1 sentence)
- Approach (tech stack, broad strokes)
- Division of labor (user vs. AI)
- Timeline and cost
- **Design constraints from user voice** — 2-3 sentences summarizing how
  community insights should direct the build. This is the bridge between
  scouting and building.
- What comes after MVP (2-3 sentences)

**For Mirage verdicts:** replace build scope with a **seed plan** — who should
build this, where to post the concept, what format the writeup should take.

### Phase 8: Deliverable

Single markdown report. **Output path:**
- **Chat:** save to `/mnt/user-data/outputs/`, then `present_files`.
- **Code:** save to CWD, then commit to repo if appropriate.

Structure:

1. Executive summary (1 paragraph)
2. Score tables — all three lenses for original idea (with justifications per
   dimension)
3. Verdict + track assignment
3b. **Cross-model audit** — Gemini Pro findings: issues found, score
    adjustments made, verdict agreement/disagreement. If post-audit verdict
    differs from original, both are shown.
4. Pivot comparison table (all three lenses per pivot)
5. Pivot descriptions (2-3 sentences each)
6. Landscape (organized by category)
7. Gap analysis (including **User voice** subheading)
8. Build scope OR seed plan (depending on verdict)
9. Next step — the single most important action + recommended pipeline track
10. **Kill reasons** (if verdict is Pass) — specific dimensions that failed
    and why
11. **Seed targets** (if verdict is Mirage) — communities and formats

**Self-check before finalizing:** all three score tables complete with all
dimension scores visible? Floor rules checked? Calibration warnings applied
(Need, Depth, Defensibility)? All pivots scored through all three lenses?
User voice section present? Build scope under 300 words? Track assignment
stated? Next step included in initial response (not just report)? Verdict
matches the 8-cell matrix correctly? **Phase 4b score audit completed and
results reflected in scores/verdict?**

**Constraints:** under 2,500 words. Direct, first-person style. File naming:
`idea-scout-[short-slug].md`. Deliver via `present_files` (chat) or inline
report (Code).

### Phase 9: Auto-Grove add

**Not optional.** After delivering the report, immediately create or update the
idea in Grove. Do not ask "want me to add this to Grove?" — just do it.

**Create method (new idea):** `grove_create_idea` via MCP with:

- `title` — idea title
- `status` — `"scouted"`
- `verdict` — one of: `greenlight`, `overreach`, `public_good`, `mirage`,
  `workhorse`, `fools_gold`, `lark`, `pass`
- `scores` — `{"impact_pct": N, "business_pct": N, "sustainability_pct": N}`
- `tags` — array of tag strings
- `notes` — combine one-liner + key insight + full notes
- `metadata` — `{"key_insight": "...", "platform": "...", "date_scouted": "YYYY-MM-DD", "zero_cost": {"version": "1.0", "date": "YYYY-MM-DD", "tier": 1|2|3, "arch": "...", "cost_drivers": "...", "free_version": "...", "popularity": "high|medium|low|niche", "effort": "..."}}`
- Include `zc:t1`, `zc:t2`, or `zc:t3` in tags per tier. Add `zc:byok` if
  BYOK pattern applies. Add `zc:popular` if popularity = high.

**Update method (existing idea):** `grove_update` via MCP with the idea's UUID.
Search first with `grove_list_ideas` (query by title) to check for duplicates.
If the idea exists, update scores/verdict/status in place.

**Legacy verdict mapping:** `Unicorn` → `greenlight`. Otherwise use the enum
values listed above (`fools_gold`, `public_good`, etc. — drop apostrophes,
spaces become underscores).

Confirm the Grove write succeeded before proceeding to Phase 10.

### Phase 10: Auto-chain

After Grove add, check the verdict and chain automatically:

| Verdict | Auto-chain action |
|---|---|
| **Greenlight, Workhorse, Lark** | Proceed directly to architect. State: "Verdict is [X] — chaining to architect." |
| **Public Good** | Proceed to architect. State: "Public Good — chaining to architect (ship it, give it away)." |
| **Overreach** | Ask: "Overreach — identify the smaller version and re-scout? Or architect the ambitious version anyway?" (Genuine trade-off → ask.) |
| **Mirage** | Generate seed plan per Phase 7. State: "Mirage — seeding, not building." Do NOT chain to architect. |
| **Fool's Gold, Pass** | Stop. Do not chain. |

**Override:** if the user said "just scout" or "don't build," skip auto-chain
regardless of verdict.

**Stop here.** Do not build, prototype, or write code within the scout skill
itself. The auto-chain hands off to architect as a separate skill invocation.

---

## Style

- Write like a sharp colleague who did their homework, not a consultant
  padding a deliverable.
- Be honest about weak spots. Take positions.
- Avoid: "synergy", "leverage", "ecosystem", "disrupt", "paradigm",
  "unlock value."
- Pre-digest research into conclusions — deliver findings, not raw search
  results.
- Don't end with "want me to scout/build/architect?" — the auto-chain handles
  next steps.

## Edge cases

- **Clearly bad idea:** say so in Phase 1. Offer a pivot. Don't burn 8
  searches on it.
- **Already exists as a mature product:** look for the angle — niche,
  audience, business model.
- **Too vague:** ask one clarifying question. Assume the rest.
- **Generalization of a previous stronger idea:** flag explicitly. Compare
  scores.
- **High impact, low business, high sustainability:** Public Good — ship it,
  give it away.
- **High impact, low business, low sustainability:** Mirage — write it up and
  seed it.
- **No community to research:** note the gap in user voice findings. Flag
  that demo builder should plan for early user testing to fill it.
- **Hardware ideas from a software builder:** sustainability will naturally
  score low on Domain Fit, IRL Effort, Financial Cost, and Dependency Risk.
  If the idea is strong enough to be a Mirage, identify the specific community
  (maker spaces, ham radio clubs, hardware startups, accessibility device
  companies) that could execute it.

## Calibration over time

When the user has accumulated 10+ scouted ideas in the vault, suggest a
calibration review through review-panel (scores mode). Not a separate workflow
— happens naturally when the user runs `vault patterns` or asks "how accurate
have my scouts been?"

## Integration

- **← brainstorm-engine:** scout an idea surfaced from a brainstorm batch.
- **← idea-vault:** re-scout an existing vault entry (`grove_update` flow).
- **→ architect:** auto-chain on Greenlight / Workhorse / Lark / Public Good.
- **→ grove:** capture-only path (`status: raw`) when user wants to save
  without scoring; Phase 8 auto-add for scored ideas.
- **→ pitch-crafter:** Mirage seed plan often hands off here for the writeup.
- **→ review-panel:** calibration review at 10+ scouted ideas.
- **→ delegate-mechanical:** offload heavy reads during Phase 2 research.
- **→ delegate-adversarial (Gemini):** Phase 0b demand pre-check, Phase 2c
  supplemental research, Phase 4b score audit. Cross-family independence is
  the primary defense against systematic scoring bias.
