# Vercel MCP — post-push deploy verification

After a push to a Vercel-connected repo, the deploy kicks off automatically. This doc covers how to check on it.

## Tool discovery

Vercel tools are deferred. Load them via `tool_search`:

```
tool_search(query="vercel list deployments")
tool_search(query="vercel get deployment build logs")
```

## Baylee's team and projects

- Team: `fairbay's projects` — id `team_hDPlehxYhRW7Hrq8ddre65Qg`
- Known projects (IDs change rarely — re-check with `Vercel:list_projects` if unsure):
  - `listing-lens-api` — `prj_WrAbt6aaWwB8A3XBwUppK5qugf4O`
  - `the-grove` — `prj_UTlAFO32wQuq55BOA9sooRvRNcCB`
  - `dateweave` — `prj_7D7mX6VUaDzahmzld6p2C4QqkdP1`
  - `variant-forge` — `prj_U5JrjGiRdQd4WQNEFGFJ5PhBHLgR`
  - `story` — `prj_q4lBUlBfhyoOCRuZUd7suVRlbhX1`
  - `pushcraft` — `prj_LiuFeivdzyz985dKooj39I1tmdQQ` *(being retired — don't push to this)*

If `.vercel/project.json` exists in the repo, it has both `orgId` and `projectId`. Prefer that over hardcoded values.

## Standard verify flow

After `push_files()` returns a commit sha:

1. `Vercel:list_deployments(teamId=..., projectId=...)` — find the deployment with `meta.githubCommitSha` matching your push.
2. If `state` is `BUILDING` or `QUEUED`, wait and poll.
3. If `state` is `ERROR`, fetch `Vercel:get_deployment_build_logs(deploymentId=...)` to diagnose.
4. If `state` is `READY`, report the `url` to Baylee.

## When NOT to use Vercel MCP

- Repo has no Vercel integration (e.g., `fairbay/idea-vault` — it's a data repo, not a web app).
- Commit is tiny (README tweak, docs fix) and doesn't need deploy verification.
- Push is to a non-production branch that's not configured for preview deploys.

In those cases just report the commit URL and stop.

## Publishing a new site

### Deploy gap

The Vercel MCP `deploy_to_vercel` tool only returns CLI instructions — it cannot deploy. The Vercel CLI requires a token not stored in `ops/secrets/`. New repos require a one-time dashboard import at vercel.com/new; only already-imported projects auto-deploy on push.

**Pipeline for a brand-new repo:**
1. Push the repo to GitHub (git-ops handles this).
2. Baylee imports at [vercel.com/new](https://vercel.com/new) — one-time, takes ~30 seconds.
3. From that point on, every push to `main` triggers an auto-deploy; use the standard verify flow above.

### Custom subdomains (bayleemiller.org)

Each new subdomain needs one CNAME record added in Route 53 (the zone's current DNS host):
- **Name:** the subdomain label (e.g., `warroom` for `warroom.bayleemiller.org`)
- **Value:** the exact project-specific value shown in the Vercel project's Settings → Domains panel

Copy the CNAME value from the project's Domains panel verbatim, trailing period included.

Values are project-specific (e.g., `d1d4fc829fe7bc7c.vercel-dns-0XX.com.`) — don't guess or reuse a previous project's value.

### Wildcard constraint

A wildcard (`*.bayleemiller.org`) cannot be done with a Route 53 CNAME — per Vercel docs, wildcard domains require moving the zone's nameservers to Vercel (`ns1/ns2.vercel-dns.com`). **This is a Baylee-approved operation only.** `vault.bayleemiller.org` (Grove MCP) lives in this zone, so any NS migration requires a full record inventory and recreation in Vercel DNS before cutover. Never initiate an NS migration without an explicit Baylee directive.

---

## Guardrails

- Never trigger `Vercel:deploy_to_vercel` unless Baylee explicitly asks. The standard flow is push → auto-deploy, not manual deploy.
- Don't chase flaky builds more than once. If a deploy fails twice in a row with the same error, stop and surface the build logs to Baylee for human decision.
