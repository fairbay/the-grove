Part of the Fairbay global rules (the core, `.claude/global.md`, and the files in `.claude/global/`); 'this file', 'below' and 'above' in these sections mean the global rules as a whole.

## Delegation Routing

Before escalating any question to Baylee, determine if it can be routed to a specialist:

- **UX / design judgment** → delegate-analytical (Sonnet)
- **Risk, security, feasibility challenges** → a fresh Claude reviewer; Gemini only as 953b370b allows
- **Fact-gathering, summarization, extraction** → delegate-mechanical (Haiku)
- **Search-grounded research** → Claude's web tools; Gemini where they can't reach

Escalation itself is the Decision Ladder's rung 4. In claude.ai (where delegation skills aren't available as sub-agents), apply the same lens yourself: reason analytically for UX questions, adversarially for risk questions, mechanically for fact-gathering.

## Usage Discipline

Baylee's weekly allowance is the budget every session spends from (35 percent of a week went to two MBN sessions on 2026-10-17; the lessons, 2026-10-18):

- **Settle a rule on a sample, and surface rulings, before running it on the set.** A grammar, a template or a classification rule is designed and reviewed on a stratified sample (every class represented) shown to Baylee; the pilot finds the questions a brief cannot answer, he rules, and the full set runs once, after (`policy: owner_context`). Four full regenerations of 1,500 names is the failure; rulings that arrive mid-run cost a referee pass.
- **Mechanical triage before any model.** Normalization, a synonym table, a set check: what a script can settle never reaches a model; a referee sees only what the script could not decide.
- **Tier the judges, not only the workers.** First-pass judging on Sonnet; Opus only on what the cheap judges split on. Bulk work on the expensive tier is the costliest shape there is.
- **One adversarial review per deliverable, at the end** (its material: Task Closure Gate). Between, validators (free to rerun). A review budget is part of the plan, not an instinct.
- **Every review brief carries what was already rejected.** Any adversarial or review prompt (Gemini through the doorway, a Claude sub-agent reviewer, a review panel, a later design round) carries the findings already considered and rejected, each with its reason; the reviewer contests one only with a valid counterpoint the reason does not already answer, and otherwise does not raise it again. Fewer repeated findings, fewer rounds (Baylee, 2026-10-19). The Gemini bundle helper is `review_package.rejected_section()`.
- **Archive at phase boundaries** (Session Scope, end condition 4): design, bulk run, repair and encoding are separate sessions; every turn pays for the whole context, so a long session is most expensive exactly when the work is heaviest. A good handoff loses nothing.
- **Brief lint.** Every generation brief says what to return when the input does not state the thing asked for (null, a flag), never "write a generic one" or a "catch-all" label, which is an instruction to make one up; such a record goes to a read of the source instead.
- **Instrument the cost.** The archive step records the session's cost shape: sub-agents by model, full-regeneration count, review passes, and the doorway's `llm.spend_by_session` row.
- **Bound every loop** — see "Loops and Spin-Out" below.

## Agent Delegation & Token Efficiency

**Default to inline execution.** Delegation has real overhead — instruction prep, context
bootstrap (the sub-agent rebuilds understanding from scratch), and result interpretation add
~30-40% more tokens than doing the work directly. A single agent matches or outperforms
multi-agent systems on the majority of tasks when given equivalent tools and context. Delegate
only when one of the triggers below fires — never because a task "could" be parallelized or
"might" benefit from a fresh context window.

### When to delegate — decision framework

Evaluate in this order. The first matching rule wins.

**1. Established methodology exists → follow it.**
Check project docs (`CLAUDE.md`, `docs/agent-templates/`, skill references) for a documented
methodology that covers this task type. If one exists, follow it — including its delegation
guidelines, model tier assignments, and verification steps. This prevents re-deriving decisions
that have already been made and validated. Methodologies are living artifacts: update them when
results reveal a flaw, but follow them until then.

**2. Bulky → delegate always.**
If the task will consume or generate large volumes where only a filtered signal matters to the
orchestrator, delegate regardless of model tier. The value is context protection, not cost
savings — keeping noise out of the orchestrator's window preserves reasoning quality for
decisions that matter. Examples: reading many files to find one relevant passage, processing
large SQL results, reviewing verbose logs. Same-tier delegation is justified here.

**3. Repetitive → pilot, codify, then delegate.**
If the task has multiple instances of structurally similar work:
  1. **Pilot:** Execute the first instance inline to prove the methodology and catch edge cases.
  2. **Codify:** Extract the proven steps into a reusable artifact — an agent prompt template
     (in `docs/agent-templates/`), a script, or methodology notes in project docs. Include
     slot variables, verification checks, and the model tier assignment.
  3. **Delegate the remainder:** Spawn sub-agents for all remaining instances using the
     codified methodology. The orchestrator's role shifts to quality-gating results.
  4. **Spot-check:** After delegation, verify a sample of results against the methodology.
     If drift is detected, update the methodology and re-delegate — don't revert to inline.

The trigger: "Have I done something structurally identical to this already?" If yes, you
should be delegating, not repeating. Similarity is the signal to codify, not to keep going.

**4. Novel → execute inline.**
If none of the above apply, the task is genuinely novel. Do it yourself. Novel work benefits
from the orchestrator's full context, produces more traceable results when surprises arise,
and — critically — is the raw material for future methodologies. Do it well enough to codify.

### Model tiering

When delegating, tier the model to the task — pass `model:` explicitly on every Agent call.

- **Haiku** — mechanical work: apply a reviewed file, verify, lint, format, search, validation
  scripts, export regeneration, git ops, PR management.
- **Sonnet** — structured transformation: extraction, text→code/SQL, reconciliation, staging
  loader construction, regex-span work.
- **Opus** — proven multi-step protocols with documented methodology: cluster closure, source
  discovery, re-anchoring, feature implementation.
- **Fable** — genuinely novel reasoning: new methodology design, cross-concept decomposition,
  structural data-model decisions, contamination detection in unfamiliar patterns, research
  synthesis. If you can describe the steps before starting, it's not fable-tier work.

**Orchestration-only rule.** The orchestrator decides WHAT to do and handles novel problems;
sub-agents DO the proven execution. Direct execution of proven patterns on the orchestrator's
model tier is wasted spend. This applies universally — not just on expensive models.

### Delegation techniques

When delegating, use the right technique for the shape of the work:

- **Parallelize independent sub-tasks** for wall-clock savings, once Rules 1-3 above call for
  delegation.
- **Maker-checker** for quality-sensitive generation: cheap model generates, capable model
  validates. Inverts the usual tier assumption — useful when generation is straightforward but
  correctness matters. Reported 40-60% cost reduction vs all-premium.
- **Batch trivial operations into one cheap agent** rather than one agent per item (per-agent
  startup + retry overhead compounds, especially when infra is flaky).

### Delegation quality loop

Three checkpoints prevent batch delegation from burning tokens on diminishing returns:

1. **Pre-flight triage.** Before dispatching ≥3 agents on the same workstream, run a data query
   to categorize work items by expected yield (source quality, access likelihood, prior success
   patterns in this session). Select clusters data-first, not intuitively — one query costs less
   than one wasted agent. If the workstream has prior-batch results, use observed yield by
   category to prioritize.

2. **Post-batch triage.** When a delegation batch returns, the orchestrator processes findings
   BEFORE dispatching the next batch. Three mandatory steps:
   - **Capture:** File Grove tasks for concrete follow-ups (source repairs, re-anchoring) and
     adjudication cards for ambiguous findings in the SAME TURN they surface. Sub-agent output
     is a crystallization moment — the "capture at crystallization" rule applies here, not just
     to decisions made in conversation.
   - **Yield check:** Compute loadable results / total checked. Note the dominant failure mode.
   - **Decide:** Explicitly choose continue, pivot, or escalate (see below). Log the choice.

3. **Pivot-or-continue gate.** After the yield check, choose one:
   - **Continue** — yield is acceptable OR specific high-yield clusters remain (identified by
     the pre-flight triage, not by hope).
   - **Pivot** — dominant failure mode is structural (wrong sources, stale docs, naming
     mismatches); switch to the upstream fix before more downstream attempts.
   - **Escalate** — pattern is unclear; surface to Baylee (`policy: owner_context`).
   "Dispatched another batch" without a yield assessment is not a decision, it's momentum.

(MBN Session 46: 8 agents across 2 batches checked 47 extractions, 15% yield. Post-batch 1
the 18% yield and dominant NOT_FOUND pattern should have triggered a pivot to source repair;
instead batch 2 repeated the same approach for 12% yield. A pre-flight triage query grouping
by `source_type` would have steered toward high-yield PDF/grid sources and away from generic
plan websites.)

### Efficiency rules

- **Text-first, not visual.** Prefer extracted text (`pdftotext -layout`, HTML/text scrapes) over
  rendering PDFs/pages/screenshots as images. Visual inputs are the single largest token multiplier;
  use them only when text genuinely fails, and only for the specific page.
- **Keep the orchestrator thin.** Large files go to a sub-agent (Rule 2, Bulky); no repeated
  status polls and no per-step narration.
- **Make delegated work resumable & idempotent.** Persist artifacts (commit generated files) so an
  infra/usage-limit failure costs a cheap retry, not a full re-spend. Decouple expensive generation
  from cheap application.
- **Background-agent notifications can be lost.** Especially after context summarization, completion
  notifications may never arrive. Never conclude agents died without checking their output files —
  agents write results to disk regardless of whether the notification reaches the orchestrator
  (`tasks/<id>.output`, the SubagentHandback tool_use input).
  Check output paths (mtimes) before re-dispatching or reporting failure.
  The reverse holds too: **never report an agent as running from memory.** An interrupt stops
  background agents along with the turn. That includes "[Request interrupted by user]" when Baylee
  only queued a message while a tool call was running. After any interrupt, a container restart or a
  long gap, check each agent's output file (mtime, last line) before saying it is running, and
  relaunch what stopped. (2026-10-19: a reviewer stopped at 15:28 by a queued message, then
  reported as "still running" for 30 minutes.)
- **Bulk data never rides in LLM-constructed tool arguments.** An agent relaying a 50KB UPDATE
  statement silently dropped 39% of its VALUES rows while keeping valid syntax and the correct
  prefix/suffix — partial success invisible to status checks. Ship bulk rows via script (REST/file)
  into a staging area and apply server-side; the LLM may carry small hand-typed statements only.
  Corollary: **verify row/record counts against the target after every bulk write**, no matter who
  or what applied it — "operation succeeded" does not mean "all rows landed."
  (MBN Session 25, Grove decision `20a2b209`.)
