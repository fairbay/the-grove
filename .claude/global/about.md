Part of the Fairbay global rules (the core, `.claude/global.md`, and the files in `.claude/global/`); 'this file', 'below' and 'above' in these sections mean the global rules as a whole.

## Identity & Workflow

Fairbay is a solo builder brand. `fairbay` is a GitHub **User** account (not an Org) — use `POST /user/repos`, not `/orgs/fairbay/repos`.

**Baylee does not write code.** Claude is the sole coder across all surfaces. Baylee reviews, approves, and steers. Three Claude surfaces operate on Fairbay projects:

- **Claude Code** — filesystem, git, builds, debugging, testing, deploys. Best for repo-level work, multi-file changes, and git operations.
- **Claude.ai Chat** — planning, architecture, idea evaluation, communication, research, artifacts, skills. Best for cross-project thinking and skill-driven workflows.
- **Routines** — API-triggered fire-and-forget batch work (e.g., skill-worker-r, grove-prune-r). No interactive feedback. Convention: `-r` suffix on Routine names.

## Mission Model

Three domain missions, one umbrella. Full definitions in `fairbay/ops/MISSION.md` (umbrella) and `fairbay/ops/missions/*/MISSION.md` (domains). System architecture in `fairbay/ops/SYSTEM.md`. **Read the MISSION.md docs when making decisions about what belongs where or what should be public — the summaries below are orientation, not the source of record.**

**Mission 1 — Personal Operating System.** Run day-to-day life (kids, workouts, taxes, every obligation) so nothing drops, AND so handling obligations protects room for enrichment. Judged on both halves. Product: **Earmark**. **Never public** — no Mission 1 content reaches any public surface by any path.

**Mission 2 — Public Presence.** Give finished work a real public home. Surface: **bayleemiller.org**. A destination, not an origin — nothing originates here. Contains **only** Mission 3 content that has graduated.

**Mission 3 — Development & Collaboration System.** Build and operate everything as a solo human working with AI. Output is **the artifacts** (apps, papers, games) — not the process. Skills, routines, the War Room method, and the platform are **means of production, not product**. A polished skill is not an output; the app it helped ship is.

**The edges** (the reason the umbrella exists):
- **1→3 (intake):** Ideas caught in daily life (Earmark/Mission 1) become Mission 3 work. Mission 1 owns capture; Mission 3 does the work.
- **3→2 (graduation):** Finished Mission 3 artifacts move to bayleemiller.org. Two classes with opposite defaults: *infrastructure* (skills, routines, plumbing) is default-private, opt-in per artifact — War Room white paper is canonical; *projects/ideas* (apps, games, papers) are default-public-eligible, gated only by readiness.
- **1→2 does not exist.** Personal data never reaches the public surface. No path, no exception.

## Project Documentation

- **Code lives in git; memory lives in Grove.** Repos are for source files. Decisions, project state, tasks, ideas, and session history live in Grove. Non-code projects (research threads, design work, workflow projects) are first-class Grove `project` rows — `repo` null, planning docs in `notes` — NOT GitHub repos. A project gets a repo when and because it has source files to version. Artifacts are windows, not stores: disposable projections over Grove, regenerated on demand.
- **Skills** live in `fairbay/ops` (source of truth) and are synced to `.claude/skills/` in every repo via `ops/scripts/sync.py`. **Never edit `.claude/skills/` in individual repos** — the sync overwrites it.
- **Doc skeleton hierarchy:** MISSION.md (authority, WHY) → SPEC.md (requirements, WHAT) → PLAN.md (technical approach, HOW). BRIEF.md is the lightweight alternative — when no planning artifacts exist, the build skill generates one from 5 interview questions. Not every project needs all layers; BRIEF.md is valid on its own for small or early-stage work. HANDOFF.yaml is session state (who worked last, what's next), not part of the doc skeleton.
- **Interview-mode engagement is the documentation trigger.** If a topic is worth interviewing about, the output becomes a durable artifact, not ephemeral chat context. Architect creates MISSION/SPEC/PLAN via interview; build creates BRIEF.md via quick interview; brainstorm-engine captures ideas durably.
- **Before editing any skill file**, stop and load skill-creator-b first.
- **Before working on a named project**, session-start (Non-Negotiable Rule 8); if the skill is unavailable, load HANDOFF.yaml and read `next:` directly — don't start cold.
- **Read PLAN.md (or BRIEF.md) before executing work** in any repo that has one. PLAN prescribes technical approach; SPEC prescribes requirements; BRIEF.md covers both lightly for smaller projects. "Build" tasks reference PLAN (or BRIEF) only. "Test," "debug," or "fix" tasks reference both PLAN and SPEC (or BRIEF if no SPEC exists).
- **If work reveals a spec, plan, or skill is wrong**, flag the conflict and propose the update — don't modify upstream artifacts without confirmation.

## Cost Assumptions

- Apple Developer Program ($99/yr) is a sunk cost. Never penalize scores, viability, or cost analysis for requiring it. Treat as $0.

## About This File

**This is the single source of truth for cross-project preferences.** It lives in `fairbay/ops/global-CLAUDE.md` and is synced to `.claude/global.md` in every active repo. Each repo's root `CLAUDE.md` imports it via `@.claude/global.md` — except `fairbay/ops` itself, whose `CLAUDE.md` imports `@global-CLAUDE.md` directly, because `sync.py` excludes the source repo and its copy went stale (found 2026-10-19).

**Stop growing it** (Grove f21b91ed step 6, 2026-11-06). A new incident or sighting goes to the ledger (chat-archive's encoding gate), not into this file; a rule enters here only when it replaces or merges one, and a rule said in two places is merged into one with a pointer.

**To update cross-project preferences:** Edit this file and land it on `main` by PR — the `sync.yml` Action in `fairbay/ops` runs `scripts/sync.py` to land it in every active repo on the merge and in every repo weekly, by one pull request per repo that sync merges once that repo's checks pass. Never edit `.claude/global.md` in individual repos directly — sync overwrites it.

**Per-repo, not synced:** each repo's `.claude/policy.json` (who decides what: classes, routes, the decision table, signal thresholds; schema and template in `fairbay/ops` docs/decision-routing/) and `.claude/landing.yaml` belong to the repo and are edited in the same PR as the ruling that changes them. A `policy:` pointer in any rule sentence names a class in that repo's file.

**Why repo-committed, not just `~/.claude/CLAUDE.md`:** Cloud Claude Code web sessions run in ephemeral VMs cloned from GitHub. `~/.claude/` does not persist between web sessions. The repo-committed file is the only reliable persistence layer. A `~/.claude/CLAUDE.md` on a local machine is read only when Claude Code runs on that machine (CLI, VS Code, desktop local mode); cloud sessions never read it (Claude Code docs, "Configure cloud environments", checked 2026-10-19). Baylee runs everything in the cloud, so any local copy is a breadcrumb, not a rule source. Evaluated 2026-10-26 (`docs/global-rules-delivery/DESIGN.md`, Results): the GitHub cloud environment's setup script writes a one-page rules card to `~/.claude/CLAUDE.md`, and a fresh repo-less **Code** session has it; a fresh **chat** does not run that script (its `~/.claude/` is provisioned empty at launch), so a chat with no repo attached is covered only by Claude's standing memory preferences until `add_repo` + `register_repo_root` load this file.
