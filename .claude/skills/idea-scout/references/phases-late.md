# idea-scout — late-phase detail

Moved verbatim from SKILL.md to keep it under 500 lines. SKILL.md names each phase and says when to load its section here; follow the section as if it were inline.


## Phase 4b: Cross-model score audit (automatic)

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


## Phase 5b: Zero-Cost Viability

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


## Phase 8: Deliverable

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


## Phase 9: Auto-Grove add

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

**Update method (existing idea):** `grove_update_idea` via MCP with the idea's UUID.
Search first with `grove_list_ideas` (query by title) to check for duplicates.
If the idea exists, update scores/verdict/status in place.

**Legacy verdict mapping:** `Unicorn` → `greenlight`. Otherwise use the enum
values listed above (`fools_gold`, `public_good`, etc. — drop apostrophes,
spaces become underscores).

**Write-failure fallback.** If the Grove MCP call fails:

1. Retry once with a fresh call.
2. If still failing, report the error explicitly — never skip silently.
3. Include the full idea data (title, verdict, scores, notes) in the response
   body so Baylee can manually add it or the next session can retry.
4. Create a Grove task noting the failed write so it doesn't get lost.

Confirm the Grove write succeeded before proceeding to Phase 10.
