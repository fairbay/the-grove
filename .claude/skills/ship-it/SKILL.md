---
name: ship-it
description: >
  Set up deployment — "ship it", "deploy this", "host this", "App Store",
  "Claude Code handoff". Not for fixes to live sites (→ git-ops), prototyping
  (→ build), or planning (→ architect).
metadata:
  version: "2026-06-02-01"
---
**Version gate (chat only):** In claude.ai, compare this skill's `metadata.version` against `fairbay/baylee-skills` via git-ops. If behind, warn once and continue. If fetch fails, skip silently. In Claude Code / Routines, skip — skills are synced from source.

# ship-it — deploy or hand off

Three transitions, share no code path. Pick the mode first.

| User signal | Mode |
|---|---|
| "deploy this", "put this online", "make this live" (web) | **A — Web** |
| "App Store", "TestFlight", "iOS", "mobile app" | **B — Mobile** |
| "take this to Claude Code", "export this project", "make this a real project" | **C — Handoff** |

If ambiguous, ask once: *"Web deploy, mobile app, or Claude Code handoff?"* Don't ask twice.

When the user just wants a push (existing host, no setup work), → git-ops. ship-it is when **deployment is the goal** — picking a host, running the checklist, verifying live.

## Philosophy

- **Free tier first.** Don't recommend paid infra without a reason.
- **Simplest path that works.** Static on Vercel beats Kubernetes.
- **One target at a time.** Pick one, get it live, expand later.
- **Research before recommending.** Config formats and free-tier limits change. Web-search before giving stack-specific instructions.

---

## Mode A — Web deploy

### Phase 1 — Assess

1. **App type** — static, SPA, full-stack (API routes), PWA.
2. **What it needs** — hosting only, server runtime, database, custom domain.
3. **Scale** — personal tool vs. public launch.
4. **Budget** — free tier vs. paid.

### Phase 2 — Pick a target

Default for Baylee: **Vercel** (his stack lives there; auto-deploy on push to `main` is already wired).

| Project type | Default | When to switch |
|---|---|---|
| Static / SPA | Vercel | Cloudflare Pages if bandwidth-heavy |
| Next.js full-stack | Vercel | — |
| Full-stack + DB | Railway or Render | When Postgres is needed |
| PWA (offline, home-screen) | Vercel | — |

For broader comparison, see `references/deployment-options.md`.

### Phase 3 — Deploy checklist

Tailor it, number it, make it copy-pasteable.

1. **Prerequisites** — host account exists, `npm run build` succeeds locally, env vars documented.
2. **Prepare build** — output dir confirmed, env vars in place, hardcoded `localhost` URLs removed, meta tags set, no temporary HF image URLs embedded (replace any with stored `publicUrl`s — see `build/references/image-store.md`; a temp URL baked into a live page 404s within minutes).
3. **Push to Git** — follow git-ops's push protocol (`git-ops/references/push-protocol.md`: test → present → push → verify). Repo must exist with `auto_init: true`.
4. **Connect host** — Vercel project created and linked; build command, output dir, env vars set. The Vercel MCP can list projects and fetch deploy status — see git-ops `references/vercel-mcp.md`.
5. **Supabase keep-alive** (if project uses Supabase free tier) — push `.github/workflows/supabase-keep-alive.yml` (template in `CONVENTIONS.md § Infrastructure Patterns`) and add three GitHub Actions secrets: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and `SUPABASE_PING_TABLE` (any table in the public schema). Trigger manually once to verify. Without this, free-tier projects pause after 7 days of no database activity.
6. **Claude infrastructure setup** (for repos that will use Claude Code or
   have skills synced). Create `.claude/global.md` (copy from
   `fairbay/code-extensions/global-CLAUDE.md`), ensure root `CLAUDE.md`
   starts with `@.claude/global.md`, and create `.claude/settings.json`
   with the SessionStart hook (template in CONVENTIONS.md § Session-
   continuity gates). **Then sync skills immediately** — read all files
   from `fairbay/baylee-skills/.claude/skills/` via git-ops and push them
   to the new repo's `.claude/skills/` in the same commit (or the next).
   Do not defer to a future `sync-skills.py` run; the repo needs skills
   before its first Claude Code session.
7. **Custom domain** (optional) — DNS, SSL auto-provisions.
8. **Verify** — test live URL on mobile and desktop, confirm core functionality works, check the version number shown in the UI.

### Hard-won lessons

- **PWA caching kills iteration.** `vite-plugin-pwa` with `registerType: 'autoUpdate'` caches aggressively. Strip PWA from anything under active development. If removing PWA from a project that had it, ship a service-worker killer that unregisters SW and clears caches on load — otherwise old clients stay broken.
- **Version must be visible in UI.** Footer / header / settings. Bump on every push. Without this, "is my new code live?" is guesswork.
- **Streaming needs the streaming flag.** Vercel serverless functions need `export const config = { supportsResponseStreaming: true }` to actually stream. Missing this is a silent failure.
- **Runtime deps in `dependencies`.** Vercel only installs production deps at runtime; anything serverless functions reach for must be in `dependencies`, not `devDependencies`.
- **Artifact ≠ deployed app.** Claude.ai artifacts block most external API calls. Skip artifact preview for anything that needs external APIs — go straight to real deployment.
- **Supabase free tier pauses silently.** After 7 days of no database activity, the project pauses and all API calls fail. Dashboard visits don't count — only real SQL queries against actual tables register as activity (the `/rest/v1/` root endpoint does not count). Every Supabase free-tier project needs a keep-alive cron (see deploy checklist step 5).

---

## Mode B — Mobile (iOS via Expo)

Default path for any React-built prototype.

### Phase 1 — Migrate to Expo

```
npx create-expo-app <name> --template blank
```

Drop the React component logic in. Most transfers directly. Swap HTML → React Native:

- `<div>` → `<View>`
- `<p>`, `<span>` → `<Text>`
- `<button>` → `<Pressable>` or `<TouchableOpacity>`
- `<img>` → `<Image>` (requires `require()` or URI)
- CSS classes → `StyleSheet.create` or NativeWind (Tailwind-on-RN)

For native widgets (lock screen, home screen): `@bacons/apple-targets` — Swift inside the Expo project, EAS builds it.

### Phase 2 — EAS

```
npx eas-cli login          # Baylee's Expo account
eas build:configure
eas build --profile preview --platform ios       # TestFlight-installable
eas build --profile production --platform ios
eas submit --platform ios
```

Apple Developer account at $99/yr is required for any device install.

### Phase 3 — App Store

Realistic timeline: 1-3 days if Mac + Apple Developer account exist; 1-2 weeks from scratch.

1. Apple Developer enrollment ($99/yr).
2. App Store Connect listing — name, screenshots (EAS build + simulator), privacy labels, age rating.
3. TestFlight beta — internal testers first, external optional.
4. Submit for review — typical approval 1-3 days for new apps.

### PWA as a middle ground

If App Store overhead isn't worth it: add `manifest.json` + service worker to a web app. Users "install" to home screen. Works offline with caching. No approval. Limited hardware access on iOS.

---

## Mode C — Claude Code handoff

> **Scope:** This mode generates a complete handoff *package* for transitioning
> a project to local Claude Code development. Individual manual action items
> (env var setup, dashboard clicks, device actions) follow the action-item
> formatting rules in chat-archive Step 6 (numbered steps, deep links inline,
> grouped by destination, state what's already done).

Take a working Claude.ai prototype and generate everything needed to continue locally in Claude Code.

### Phase 1 — Inventory

Scan the conversation (and any linked scout / architect / build outputs):

1. **What's built** — artifact code, data models, UI components, business logic.
2. **Stack** — React, HTML/CSS/JS, Python, Expo.
3. **Project identity** — one-sentence description, primary user, core feature.
4. **Context that already exists** — scout reports, specs, decisions made in conversation.
5. **What's faked** — mock data, hardcoded values, placeholder APIs.

### Phase 2 — Confirm target stack

| Artifact | Likely target | Project structure |
|---|---|---|
| React → web | Vite + React | Standard React project |
| React → mobile | Expo | Expo managed workflow |
| HTML/CSS/JS page | Vite static | Minimal build |
| Python script | Python package | `src/`, `requirements.txt` |
| React → both | Expo + Expo Web | Unified |

Ask the user to confirm the stack before generating files. Wrong stack wastes hours.

### Phase 3 — Generate handoff package

Saved to `/mnt/user-data/outputs/<project-name>/`.

**1. `CLAUDE.md`** — project brief for Claude Code. Most important file. Must contain enough context that someone reading only it (without the chat) understands the project.

```markdown
# <Project>

## What This Is
[One paragraph: what, who, core insight]

## Origin
Prototype in Claude.ai. This CLAUDE.md captures the context so Claude Code can continue without losing history.

## Current State
- [What's working]
- [What's faked/mocked]
- [Known issues]

## Architecture Decisions
[Stack, data model, UX patterns — and why]

## Key Files
[File map with what each does]

## Development Priorities
1. [Most important next step]
2. ...

## Style & Conventions
[Patterns from the prototype]

## Data Model
[Core entities + relationships]

## External Dependencies
[APIs, services — and which are mocked]

## Deployment Target
[web / iOS / both / internal]
```

**2. Source code** — extract artifact, decompose into proper structure (typical React: `src/{App.jsx,components,hooks,utils,data,styles}` + `public/index.html` + `package.json` + `README.md`; typical Python: `src/__init__.py`, `src/main.py`, `tests/`, `requirements.txt`, `README.md`).

**3. `setup.sh`** — bash script that gets the project running from scratch:

```bash
#!/bin/bash
command -v node >/dev/null || { echo "Node.js required"; exit 1; }
npm install
echo "Run 'npm run dev' to start."
```

**4. `FIRST_PROMPT.md`** — exact prompt to paste into Claude Code on first run:

```markdown
I'm continuing development on <project> — [one-line description]. This started as a prototype in Claude.ai and I've exported it into this project structure. Please read CLAUDE.md for full context.

The prototype works but needs: [top 2-3 priorities].

Let's start with [specific first task].
```

### Phase 4 — Deliver

Deliver the package:
- **Chat:** `present_files` for all files. Baylee downloads and unzips.
- **Code:** files are already in the repo CWD. No download needed.

Brief commentary:
- "Here's your handoff package for &lt;project&gt;."
- What's inside.
- First step: "Download these, unzip, run `setup.sh`, then `claude`."

---

## Required conventions (every mode)

- **Version visible in UI** — footer / header / settings. Human-readable. Bump on every push.
- **No PWA caching on actively-developed projects** — strip `vite-plugin-pwa` unless offline is a stable, explicit feature.
- **`.gitignore` from day one** — `node_modules`, `dist`, `.env`, `.DS_Store`, `.expo/`.
- **GitHub repos use `auto_init: true`** — empty repos break the Git Data API. git-ops handles this on `create`.

## Handling different starting points

- **From build:** prototype is one artifact. Extract, decompose, build CLAUDE.md from the demo's build context.
- **From architect (interview mode):** there's a `SPEC.md` already. CLAUDE.md references it as the source of truth for *what the product is*.
- **From architect (express mode):** the plan defines file structure, data model, build sequence. Use those directly.
- **Long iterative conversation:** scan for the final working version; ignore earlier iterations. Capture *decisions* (why things changed) in CLAUDE.md.
- **Multiple artifacts in one conversation:** ask which to develop, or generate separate packages.

## Integration

- **← build:** "Want to put this online / take this to Claude Code?" is the natural follow-up.
- **← architect:** pulls deployment target, file structure, stack from the prior plan.
- **← pitch-crafter:** a live URL is the best pitch material.
- **→ git-ops:** ship-it's push step (Phase 3) follows `git-ops/references/push-protocol.md` and uses `scripts/git_push.py` for the push call. ship-it is by definition mid-workflow when it pushes.
- **→ idea-vault / Grove:** on successful web deploy, update the idea's `deploy_url` and mark `status = deployed`.

## What this skill does NOT do

- Write application code (→ build, or Claude Code locally).
- Make stack decisions without user confirmation.
- Manage ongoing DevOps (CI/CD, monitoring, scaling).
- Handle payment / Stripe setup.
- Actually submit to App Stores (provides the checklist; Baylee executes the human steps).
- Teach Claude Code installation (point to the Mac/PC setup guides).

## References

- `references/deployment-options.md` — broader host comparison + cost summary.
