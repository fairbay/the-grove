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

## Guardrails

- Never trigger `Vercel:deploy_to_vercel` unless Baylee explicitly asks. The standard flow is push → auto-deploy, not manual deploy.
- Don't chase flaky builds more than once. If a deploy fails twice in a row with the same error, stop and surface the build logs to Baylee for human decision.
