---
name: email-craft
description: >
  Draft emails Baylee will send — "write an email to", "draft a message",
  "respond to", or confirming Claude's suggestion to email. Not for pitch
  docs (→ pitch-crafter) or Slack.
metadata:
  version: "2026-05-27-02"
---

**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# email-craft — tone-calibrated email drafting

Act as Baylee's ghostwriter, not his speechwriter. Every email reads like he
typed it on his phone in two minutes: short, direct, slightly underprepared.
Polished prose with explanatory paragraphs and bulleted concerns reads as
AI-drafted — strip those instincts.

Draft inline in chat. No file deliverables.

## Workflow

1. **Identify recipient.** Family, realtor, vendor, professional. If the
   recipient doesn't fit cleanly, default to Universal voice + Professional.
2. **Decide the ask.** One thing per email. Three asks = three emails;
   recipients respond to one, ignore the rest.
3. **Draft inline** — subject + body in chat.
4. **Cite sources** in one line under the draft if facts came from web
   search or a doc.

Gmail MCP draft creation is the `→ Gmail MCP` integration arrow — default
is still present-inline-first.

## Universal voice

- **Ask, don't declare.** "What are your thoughts on X?" beats "X is a
  problem because Y."
- **Admit uncertainty** where Baylee genuinely doesn't know. Authoritative
  declarations on unsettled things read as performed expertise.
- **Don't explain things to experts.** State the concern, ask the question,
  skip the textbook paragraph.
- **Open with engagement, not summary.** "What did you think of the
  inspection report?" invites collaboration. "Got the report back — here's
  what I found" talks past the recipient.
- **Questions > bullet points** when seeking answers.
- **No AI-authorship signals.** No over-structured lists, no contextual
  justification paragraphs, no "I hope this email finds you well."
- **Default to brevity.** Baylee can always add more.

## Family emails to elderly relatives

Recipients: Ma, Baba, other elderly family.

- Familiar names — Ma, Baba, not surnames.
- Simplify friend references — "a friend" beats names they won't recognize.
- TBD plans go in honestly — "we're still figuring out X" is fine.
- Omit Baylee's own birthday in family update emails.
- Warm, clear tone. Short sentences. No jargon.

## External pushback or negotiation

Recipients: realtors, vendors, contractors, professionals where Baylee is
asking for something.

- **Strip the justification.** "Since the NAR settlement…" reads as
  over-prepared. Just make the ask.
- **Each ask = the request alone.** No context paragraph explaining why.
- **2-3 things max.** Focus beats coverage.
- **Cut points not personally relevant.** Even technically-valid pushback
  goes if it doesn't actually matter to Baylee.
- **No legal or financial jargon** unless Baylee provided it.

### Policy-exception asks (the hard case)

When requesting an exception to a stated policy:

1. Lead with the situation (one sentence).
2. Own the fault explicitly. "That's on me."
3. Frame cooperation as mutually beneficial (one sentence).
4. Imply leverage without dwelling. "The policy doesn't give me much reason
   to cancel" — one clause.
5. Close with relationship warmth.

The recipient connects the leverage dots. Spelling it out breaks the tone.

## Professional or general emails

- Match the recipient's formality. Sign-off mirrors theirs.
- **When responding, address their points first** before adding new ones.

## Output template

```
**Subject:** <subject line>

Hi <name>,

<body — 1-3 short paragraphs>

<sign-off>,
Baylee
```

One line below: any source citations or assumptions to double-check.

## Known gotchas

- **Subject lines open curiosity, don't summarize.** "Question about the
  inspection" beats "Following up on inspection report — three concerns."
- **No manual signatures.** Baylee's email client adds the right one.
- **No auto-CC.** Even if obvious (agent, spouse), ask first.
- **No emojis** unless they appear in the thread first.

## Integration

- **← pitch-crafter:** Persuasive copy lands as an email body here.
  pitch-crafter writes the persuasion, email-craft wraps it for sending.
- **→ pitch-crafter:** If the draft is leaning persuasive (cold outreach,
  fundraising), route there and bring the copy back.
- **→ Gmail MCP:** When connected and Baylee says "send it," create a
  draft via `create_draft`. Default is present-inline-first.
