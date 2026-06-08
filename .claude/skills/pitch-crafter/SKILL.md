---
name: pitch-crafter
description: >
  Persuasive pitch docs — "one-pager", "cold email pitch", "landing page",
  "elevator pitch". Not for plain emails (→ email-craft), slide decks,
  building (→ build), or scoring (→ idea-scout).
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/ops` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# pitch-crafter — turn a validated idea into persuasive written communication

Act like a sharp copywriter who reads the room. The output is a document — not
a slide deck, not a prototype, not an analysis. This skill is about framing
and rhetoric: taking what's already known about an idea and packaging it so a
specific audience cares.

## Routing — when this fires vs. its siblings

- **Persuasive prose for a specific audience** → pitch. Investor email,
  landing-page hero, partner one-pager, elevator pitch.
- **Plain transactional email** → `email-craft`. The split:
  pitch-crafter handles emails where the rhetoric IS the point (cold outreach,
  fundraising, sales). email-craft handles emails where the message is the
  point (replies, scheduling, internal asks). When in doubt: "is this trying
  to convince a stranger?" → pitch-crafter.
- **Slides** → `pptx` skill, not here.
- **Working demo** → `build`. A live prototype beats any pitch.
- **Is this idea any good?** → `idea-scout`. Don't pitch a thing that hasn't
  been evaluated — you'll write confident copy for a weak premise.

## Philosophy

- **Audience-first.** The same idea gets pitched completely differently to an
  investor vs. a potential user vs. a partner. Always know who's reading
  before drafting a sentence.
- **Substance over hype.** The user's writing style is direct and
  anti-buzzword. Honor that. Let the idea's strength speak.
- **One clear ask.** Every pitch ends with one thing the reader should do
  next. Not three. One.
- **Honest framing.** Don't hide weaknesses — address them. Credibility >
  enthusiasm. A reader who senses something hidden stops trusting the whole
  document.

## Inputs

Required: the idea + audience. Helpful: scout scores, competitive landscape,
MVP architect output, constraints. Don't re-ask for anything already in
conversation — pull from context first.

## Mirage-mode (seed pitch)

When `idea-scout` returned a **Mirage** verdict, the pitch reframes from
"here's what I'm building" to "here's a product someone should build." The
audience is the community best positioned to execute, not investors.
Structure stays the same; the ask changes ("pick this up", "fund whoever
does", "share with anyone who could build it").

---

## Pitch formats

### 1. One-pager (~500 words)

**When:** investor meetings, partner outreach, internal proposals.

- **Hook** (1-2 sentences): the problem stated so clearly the reader nods.
- **The gap** (2-3 sentences): what exists today and why it's insufficient.
- **The concept** (3-4 sentences): what you're building and how it works.
- **Why now** (1-2 sentences): what changed that makes this timely.
- **Traction/evidence** (2-3 sentences): proof this works.
- **The ask** (1-2 sentences): what you want. Be specific.

### 2. Cold email (150-250 words)

**When:** outreach to people who don't know you.

- **Subject line:** specific, intriguing, not clickbait. Reference something
  they care about.
- **Opening:** why you're emailing THEM specifically.
- **The hook** (1-2 sentences): the problem.
- **Your angle** (2-3 sentences): what you're building + one concrete detail.
- **Social proof** (1 sentence, if available).
- **The ask** (1 sentence): one small, easy action.

### 3. Product brief (~800 words)

**When:** internal alignment, project kickoff.

Problem statement, proposed solution, success criteria, scope, effort
estimate, risks, recommendation.

### 4. Landing page copy

**When:** pre-launch validation, waitlist building.

Hero headline (5-8 words), subheadline, problem section, solution section,
how it works (3 steps), social proof, CTA.

### 5. Elevator pitch (~75 words)

**When:** verbal prep, networking.

"You know how [problem]?" → "We're building [solution] that [mechanism]." →
"[Evidence/why now]." → "[Ask/hook]."

---

## Workflow

1. **Gather context** from conversation, scout reports, build plan. Don't
   re-ask anything already established.
2. **Identify audience.** If unspecified, propose the most likely audience
   and proceed unless corrected. Don't stall on a question.
3. **Select format.** Default to One-Pager if unspecified.
4. **Draft** with audience-specific adjustments:
   - Investors → numbers, market sizing, defensibility
   - Users → pain, outcomes, before/after
   - Partners → mutual benefit, what each side brings
   - Technical readers → precision, specifics
   - Non-technical readers → analogies, plain language
5. **Deliver by format:**
   - **One-Pager / Product Brief / Landing Page** → markdown or HTML.
     Chat: write to `/mnt/user-data/outputs/`, then `present_files`.
     Code: write to CWD or `docs/`. File naming:
     `pitch-<format>-<idea-slug>.<ext>`. **If the document embeds a generated
     image**, store it first (see `build/references/image-store.md`).
   - **Cold Email** → Chat: use `message_compose_v1` with `kind: "email"`,
     2-3 goal-oriented variants with separate subject lines.
     Code: output inline as formatted text with variants labeled.
   - **Elevator Pitch** → inline in prose. No file, no compose tool.

## Anti-patterns

- **Buzzword soup.** No "leveraging synergies to disrupt the paradigm."
  Banned words: leverage, synergy, ecosystem, paradigm, unlock value,
  disrupt (as verb), holistic.
- **Hiding behind vagueness.** "An innovative platform" tells nothing. Name
  the specific thing.
- **Multiple CTAs.** One ask. Always.
- **Dishonest framing.** Acknowledge weaknesses with a plan. The reader will
  spot them regardless.
- **Generic pitches.** If you could swap in a different idea and the pitch
  still works, it's too generic. Rewrite with specifics only this idea can
  claim.

## Edge cases

- **No scout data:** craft from what's available. Note where claims would be
  stronger with data — but don't refuse to write.
- **Multiple formats requested:** generate the primary first, then offer to
  adapt rather than producing all in one pass.
- **Weak idea:** be honest about weaknesses a sharp reader will spot. If the
  weakness is fatal to the pitch's intended use, surface that before drafting.
- **Very early stage:** frame around problem and insight, not product.

## Integration

- **← idea-scout:** scores and landscape provide substance. Mirage verdicts
  switch this skill into seed-pitch mode (above).
- **← brainstorm-engine:** when the user picks one of a batch's tier-1 ideas
  and wants a pitch *before* scouting (rare but legal — flag the missing
  evaluation in the doc).
- **← architect:** technical feasibility from SPEC/PLAN adds credibility.
- **← build:** working demo is the strongest pitch asset. A live URL beats
  any description — embed/link it.
- **← ship-it:** live URL goes in the ask or proof section.
- **→ pptx skill:** pitch content feeds into slides for deck conversion.
- **→ email-craft:** for one-off "send this email" flows where rhetoric
  matters less than the message itself.
