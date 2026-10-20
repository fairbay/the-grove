"""
pr_state.py — land-and-leave entry-gate reader (docs/land-and-leave-SPEC.md §10).

Commands:

    report [--repo owner/name]            Classify every open PR on the default branch into
                                          the gate rows G1–G13 (§7.5). JSON on stdout. Exit 0 always.
    check N[,N…] [--repo owner/name]      Per PR: state, merged_at, merge_sha, deploy_state, deploy_ok,
                                          commits_after_cal, continues_from, continued_by, converting.
                                          JSON. Exit 0 always.
    report --table                        Same report as a compact Markdown table (for Phase 0 / hooks).

Report-only: it reads GitHub and writes nothing. Grove lookups (owner tasks, markers) are the
session's job; a non-stale draft is reported as G8 with "owner_required": a session that finds no
`owns: fairbay/<repo>#<n>` task treats it as G7.

Transport, first that works: `gh api` (Code sessions and attached-repo chats, where the session
proxy authenticates), then GH_TOKEN / GITHUB_TOKEN against api.github.com, else `unreachable`.
Repo-scoped endpoints only; pages manually (`gh api --paginate` fails through the proxy). Stdlib only.
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import time

API = "https://api.github.com"

DEFAULT_POLICY = {
    "merge_policy": "tap",
    "merge_method": "squash",
    "pre_ready": [],
    "ci_checks": [],
    "checks_start_within": 20,
    "redeploy": None,
    "deploy_check": "none",
    "stale_draft_days": 14,
    "bot_prs": {"dependabot": "offer_merge_when_green", "block_major": True},
}

CAL_RE = re.compile(r"^Close-at-land:\s*\d{4}-\d{2}-\d{2}T", re.M)  # the trailer, not a line quoting it
BILLING_RE = re.compile(r"spending limit|payments have failed", re.I)
FAILED_CONCLUSIONS = {"failure", "cancelled", "timed_out", "action_required", "startup_failure", "stale"}
PASSED_CONCLUSIONS = {"success", "skipped", "neutral"}


class Unreachable(Exception):
    pass


# --- transport ---------------------------------------------------------------

class Client:
    def __init__(self, repo: str):
        self.repo = repo
        self.mode = None
        errors = []
        if shutil.which("gh"):
            try:
                self.mode = "gh"
                self.get(f"/repos/{repo}")
                return
            except Unreachable as e:
                errors.append(f"gh: {e}")
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            try:
                self.mode, self.token = "token", token
                self.get(f"/repos/{repo}")
                return
            except Unreachable as e:
                errors.append(f"token: {e}")
        self.mode = None
        raise Unreachable("; ".join(errors) or "no gh CLI and no GH_TOKEN/GITHUB_TOKEN")

    def get(self, path: str):
        if self.mode == "gh":
            try:
                out = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=30)
            except Exception as e:
                raise Unreachable(f"{path}: {e}")
            if out.returncode != 0:
                msg = (out.stderr or out.stdout).strip().splitlines()
                raise Unreachable(f"{path}: {msg[-1] if msg else 'exit ' + str(out.returncode)}")
            return json.loads(out.stdout or "null")
        if self.mode == "token":
            import ssl
            import urllib.error
            import urllib.request
            req = urllib.request.Request(API + path, headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "fairbay-pr-state",
            })
            ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
            ctx = ssl.create_default_context(cafile=ca) if ca else None
            try:
                with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                    return json.loads(r.read() or b"null")
            except urllib.error.HTTPError as e:
                raise Unreachable(f"{path}: HTTP {e.code}")
            except Exception as e:
                raise Unreachable(f"{path}: {e}")
        raise Unreachable("no transport")

    def get_404_ok(self, path: str):
        try:
            return self.get(path)
        except Unreachable as e:
            if "404" in str(e) or "Not Found" in str(e):
                return None
            raise

    def pages(self, path: str, key: str | None = None):
        sep = "&" if "?" in path else "?"
        out, page = [], 1
        while True:
            data = self.get(f"{path}{sep}per_page=100&page={page}")
            items = data.get(key, []) if key else data
            out.extend(items)
            if len(items) < 100:
                return out
            page += 1


# --- policy ------------------------------------------------------------------

def _scalar(v: str):
    v = v.strip()
    if v in ("", "~", "null"):
        return None
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if v.startswith("[") and v.endswith("]"):
        return [_scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        return v[1:-1]
    return v


def parse_policy_yaml(text: str) -> dict:
    """The landing.yaml subset: top-level scalars, inline lists, block lists, one nested map."""
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass
    data: dict = {}
    key = None
    for raw in text.splitlines():
        line = re.sub(r"\s+#.*$", "", raw).rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line.startswith(" ")
        s = line.strip()
        if not indented:
            k, _, v = s.partition(":")
            key = k.strip()
            data[key] = _scalar(v) if v.strip() else None
        elif key and s.startswith("- "):
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(_scalar(s[2:]))
        elif key and ":" in s:
            if not isinstance(data[key], dict):
                data[key] = {}
            k, _, v = s.partition(":")
            data[key][k.strip()] = _scalar(v)
    return data


MERGE_POLICIES = ("tap", "self", "policy")
# tap: Baylee's tap merges every PR. self: the session merges its own PRs. policy: the repo's
# .claude/policy.json decides (fairbay/ops docs/decision-routing/DESIGN.md §2): the session merges
# ruled upkeep itself and keeps the tap for a change of direction. When that file is missing or
# does not parse, `policy` falls back to `tap` and the report says so.


def resolve_merge_policy(policy: dict, routing: dict | None, routing_error: str | None = None) -> dict:
    """Normalise merge_policy against MERGE_POLICIES and attach the routing policy (or the fallback reason)."""
    declared = policy.get("merge_policy")
    if declared not in MERGE_POLICIES:
        policy["merge_policy_declared"] = declared
        policy["merge_policy"] = "tap"
        policy["merge_policy_fallback"] = f"unknown merge_policy {declared!r}; one of {', '.join(MERGE_POLICIES)}"
        return policy
    if declared == "policy":
        policy["merge_policy_declared"] = "policy"
        if isinstance(routing, dict) and routing.get("classes"):
            policy["routing"] = routing
        else:
            policy["merge_policy"] = "tap"
            policy["merge_policy_fallback"] = routing_error or ".claude/policy.json missing; merge_policy: policy falls back to tap"
    return policy


def load_routing_policy(c: Client, default_branch: str):
    """The repo's .claude/policy.json as a dict, or (None, reason)."""
    meta = c.get_404_ok(f"/repos/{c.repo}/contents/.claude/policy.json?ref={default_branch}")
    if not meta or "content" not in meta:
        return None, ".claude/policy.json missing; merge_policy: policy falls back to tap"
    text = base64.b64decode(meta["content"]).decode("utf-8", "replace")
    try:
        data = json.loads(text)
    except ValueError as e:
        return None, f".claude/policy.json does not parse ({e}); merge_policy: policy falls back to tap"
    if not isinstance(data, dict) or not isinstance(data.get("classes"), dict):
        return None, ".claude/policy.json has no classes map; merge_policy: policy falls back to tap"
    return data, None


def load_policy(c: Client, default_branch: str):
    meta = c.get_404_ok(f"/repos/{c.repo}/contents/.claude/landing.yaml?ref={default_branch}")
    if not meta or "content" not in meta:
        return dict(DEFAULT_POLICY), "default"
    text = base64.b64decode(meta["content"]).decode("utf-8", "replace")
    policy = dict(DEFAULT_POLICY)
    policy.update(parse_policy_yaml(text))
    policy["bot_prs"] = {**DEFAULT_POLICY["bot_prs"], **(policy.get("bot_prs") or {})}
    for k in ("pre_ready", "ci_checks"):
        policy[k] = policy.get(k) or []
    routing, err = (None, None)
    if policy.get("merge_policy") == "policy":
        routing, err = load_routing_policy(c, default_branch)
    return resolve_merge_policy(policy, routing, err), "file"


# --- facts per commit / PR -----------------------------------------------------

def _now():
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_ts(s: str):
    return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def deploy_state(c: Client, sha: str, policy: dict):
    """success | pending | failure | error | missing for the `Vercel` status context; None when deploy_check is none."""
    if policy.get("deploy_check") != "vercel":
        return None
    st = c.get(f"/repos/{c.repo}/commits/{sha}/status")
    states = [s.get("state") for s in st.get("statuses", []) if s.get("context") == "Vercel"]
    return states[0] if states else "missing"  # statuses are newest first


def check_status(c: Client, sha: str, head_age_min: float, pr: dict, policy: dict) -> tuple[str, list]:
    """green | not_run | pending | failed | billing_failed (§5 Check status), plus the named runs."""
    runs = c.pages(f"/repos/{c.repo}/commits/{sha}/check-runs", key="check_runs")
    names = policy.get("ci_checks") or []
    latest: dict = {}
    for r in runs:
        if names and r["name"] not in names:
            continue
        if r["name"] not in latest or r["id"] > latest[r["name"]]["id"]:
            latest[r["name"]] = r
    named = list(latest.values())
    summary = [f"{r['name']}:{r.get('conclusion') or r['status']}" for r in named]

    ms, mergeable = pr.get("mergeable_state"), pr.get("mergeable")
    if ms in ("dirty", "blocked", "behind"):
        return "failed", summary + [f"mergeable_state:{ms}"]
    failed = [r for r in named if r["status"] == "completed" and r.get("conclusion") in FAILED_CONCLUSIONS]
    if failed:
        billing = all(_is_billing(c, r) for r in failed)
        return ("billing_failed" if billing else "failed"), summary
    if any(r["status"] != "completed" for r in named) or mergeable is None or ms == "unknown":
        return "pending", summary
    if not named:
        if head_age_min < (policy.get("checks_start_within") or 0) and not _actions_settled(c, sha, head_age_min):
            return "pending", summary
        # Without named checks `unstable` is the only failure signal; with them it can also mean
        # an unnamed check failing, which policy says does not define Green.
        if ms == "unstable" and not names:
            return "failed", summary + ["mergeable_state:unstable"]
        return "not_run", summary
    if ms == "unstable" and not names:
        return "failed", summary + ["mergeable_state:unstable"]
    return "green", summary


ACTIONS_GRACE_MIN = 2  # Actions creates a triggered workflow's suite within seconds of the push


def _actions_settled(c: Client, sha: str, head_age_min: float) -> bool:
    """True when GitHub Actions has nothing left to start for this commit.

    Every workflow the push triggers gets its suite at once, so finished suites with no named run mean
    the path filter skipped the named check: Not run now, without waiting out checks_start_within.
    No Actions suite at all means no workflow matched the change's paths (ops #64, 2026-10-14: no
    SKILL.md touched, so the trigger tests never started), once the head is older than
    ACTIONS_GRACE_MIN; younger than that, a suite may still be on its way. Other apps' suites are
    ignored: some stay queued forever (MBN #368: claude, vercel).
    """
    suites = c.pages(f"/repos/{c.repo}/commits/{sha}/check-suites", key="check_suites")
    actions = [x for x in suites if (x.get("app") or {}).get("slug") == "github-actions"]
    if not actions:
        return head_age_min >= ACTIONS_GRACE_MIN
    return all(x.get("status") == "completed" for x in actions)


def _is_billing(c: Client, run: dict) -> bool:
    out = run.get("output") or {}
    if BILLING_RE.search(f"{out.get('title') or ''} {out.get('summary') or ''}"):
        return True
    if not out.get("annotations_count"):
        return False
    anns = c.get(f"/repos/{c.repo}/check-runs/{run['id']}/annotations")
    return any(BILLING_RE.search(a.get("message") or "") for a in anns or [])


def _major(frm: str, to: str):
    """True/False for a parsed version pair; None when unparsable."""
    a = re.findall(r"\d+", frm or "")
    b = re.findall(r"\d+", to or "")
    if not a or not b:
        return None
    if a[0] != b[0]:
        return True
    if a[0] == "0" and len(a) > 1 and len(b) > 1 and a[1] != b[1]:
        return True
    return False


def dependabot_bumps(body: str):
    """[(package, from, to)] from the Package/From/To table first, then `Updates `x` from a to b` lines."""
    bumps = []
    lines = (body or "").splitlines()
    for i, line in enumerate(lines):
        cells = [x.strip().lower() for x in line.strip().strip("|").split("|")]
        if cells[:3] == ["package", "from", "to"]:
            for row in lines[i + 2:]:
                if not row.strip().startswith("|"):
                    break
                p = [x.strip() for x in row.strip().strip("|").split("|")]
                if len(p) >= 3:
                    pkg = re.sub(r"^\[(.*?)\]\(.*\)$", r"\1", p[0]).strip("`")
                    bumps.append((pkg, p[1].strip("`"), p[2].strip("`")))
            break
    if not bumps:
        for m in re.finditer(r"Updates `([^`]+)` from (\S+) to (\S+?)(?:\s|$)", body or ""):
            bumps.append((m.group(1), m.group(2), m.group(3).rstrip(".")))
    return bumps


def has_major(body: str) -> tuple[bool, list]:
    bumps = dependabot_bumps(body)
    if not bumps:
        return True, []  # F7: nothing parsed counts as major
    majors = []
    for pkg, frm, to in bumps:
        m = _major(frm, to)
        if m is None or m:
            majors.append(f"{pkg} {frm}→{to}")
    return bool(majors), majors


# --- classification (§7.5 step 6) ----------------------------------------------

def _pr_full(c: Client, n: int) -> dict:
    pr = c.get(f"/repos/{c.repo}/pulls/{n}")
    if pr.get("state") == "open" and not pr.get("draft") and (pr.get("mergeable") is None or pr.get("mergeable_state") == "unknown"):
        time.sleep(2)  # GitHub computes mergeability lazily; the first read starts it
        pr = c.get(f"/repos/{c.repo}/pulls/{n}")
    return pr


def classify(c: Client, n: int, policy: dict) -> dict:
    pr = _pr_full(c, n)
    sha = pr["head"]["sha"]
    head = c.get(f"/repos/{c.repo}/commits/{sha}")
    committed = _parse_ts(head["commit"]["committer"]["date"])
    age_min = (_now() - committed).total_seconds() / 60
    cal = bool(CAL_RE.search(head["commit"]["message"]))
    bot = pr["user"].get("type") == "Bot"
    login = pr["user"].get("login")
    item = {
        "number": n,
        "title": pr["title"],
        "url": pr["html_url"],
        "author": login,
        "bot": bot,
        "draft": bool(pr.get("draft")),
        "head_ref": pr["head"]["ref"],
        "head_sha": sha,
        "cal": cal,
        "checks": None,
        "check_detail": [],
        "mergeable_state": pr.get("mergeable_state"),
        "head_age_days": round(age_min / 1440, 1),
        "major_bump": None,
        "row": None,
        "recommendation": None,
        "blocks": True,
    }

    if not bot and item["draft"]:
        if item["head_age_days"] > policy["stale_draft_days"]:
            item.update(row="G7", recommendation="adopt_or_close", state="D-orphan", stale=True)
        else:
            item.update(row="G8", recommendation=None, state="D-owned", blocks=False, owner_required=True)
        return item

    checks, detail = check_status(c, sha, age_min, pr, policy)
    item["checks"], item["check_detail"] = checks, detail
    green = checks in ("green", "not_run")

    if not bot:
        if cal:
            row = {"pending": "G4", "failed": "G5", "billing_failed": "G5b"}.get(checks, "G3")
            rec = {"G3": "merge", "G4": "merge_when_green", "G5": "fix_first", "G5b": "merge_on_local_tests"}[row]
            item.update(row=row, recommendation=rec, state="R-current")
        else:
            commits = c.pages(f"/repos/{c.repo}/pulls/{n}/commits")
            had_cal = any(CAL_RE.search(x["commit"]["message"]) for x in commits)
            if had_cal:
                item.update(row="G6", recommendation="back_to_draft", state="R-dirty")
            else:
                item.update(row="G6b", recommendation="hand_off_now", state="R-dirty")
        return item

    if login == "dependabot[bot]":
        major, majors = has_major(pr.get("body") or "")
        item["major_bump"], item["majors"] = major, majors
        mode = policy["bot_prs"].get("dependabot", "offer_merge_when_green")
        block_major = policy["bot_prs"].get("block_major", True)
        if mode == "ignore":
            item.update(row="G9-ignored", recommendation=None, blocks=False)
        elif mode == "close":
            item.update(row="G12", recommendation="close")
        elif major and block_major:
            item.update(row="G10", recommendation="close_and_upgrade_task")
        elif checks == "pending":
            item.update(row="G11", recommendation="merge_when_green")
        elif green:
            item.update(row="G9", recommendation="merge")
        else:
            item.update(row="G12", recommendation="close")
        item["state"] = "B-open"
        return item

    item.update(row="G13", recommendation="close_and_review_task", state="B-open")
    return item


def build_report(repo: str) -> dict:
    rep = {"repo": repo, "checked_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "reachable": False,
           "reason": None, "transport": None, "policy": None, "policy_source": None,
           "default_head": None, "prs": [], "rows": {}}
    try:
        c = Client(repo)
        rep["transport"] = c.mode
        info = c.get(f"/repos/{repo}")
        default = info["default_branch"]
        policy, src = load_policy(c, default)
        rep.update(policy=policy, policy_source=src, default_branch=default)
        head_sha = c.get(f"/repos/{repo}/commits/{default}")["sha"]
        state = deploy_state(c, head_sha, policy)
        bad = state not in (None, "success", "pending")  # pending: a deploy still building is re-checked, not fixed
        rep["default_head"] = {"sha": head_sha, "deploy_state": state,
                               "deploy_ok": None if state is None else state == "success",
                               "row": "G2" if bad else None,
                               "recommendation": "redeploy" if bad else None,
                               "redeploy": policy.get("redeploy") if bad else None}
        prs = c.pages(f"/repos/{repo}/pulls?state=open&base={default}")
        for p in sorted(prs, key=lambda x: x["number"]):
            rep["prs"].append(classify(c, p["number"], policy))
        rep["reachable"] = True
    except Unreachable as e:
        rep["reason"] = str(e)
        rep["prs"] = []
        rep["row"], rep["recommendation"] = "G1", "stop"
    for p in rep["prs"]:
        rep["rows"].setdefault(p["row"], []).append(p["number"])
    rep["blocking"] = (not rep["reachable"]) or bool(rep["default_head"] and rep["default_head"]["row"]) \
        or any(p["blocks"] for p in rep["prs"])
    return rep


def build_check(repo: str, numbers: list[int]) -> dict:
    out = {"repo": repo, "checked_at": _now().strftime("%Y-%m-%dT%H:%M:%SZ"), "reachable": False,
           "reason": None, "prs": []}
    try:
        c = Client(repo)
        info = c.get(f"/repos/{repo}")
        policy, _ = load_policy(c, info["default_branch"])
        for n in numbers:
            pr = c.get_404_ok(f"/repos/{repo}/pulls/{n}")
            if pr is None:
                out["prs"].append({"number": n, "state": "missing"})
                continue
            body = pr.get("body") or ""
            state = "merged" if pr.get("merged_at") else pr["state"]
            entry = {
                "number": n,
                "state": state,
                "draft": bool(pr.get("draft")),
                "merged_at": pr.get("merged_at"),
                "closed_at": pr.get("closed_at"),
                "merge_sha": pr.get("merge_commit_sha") if state == "merged" else None,
                "deploy_state": None,
                "deploy_ok": None,
                "commits_after_cal": [],
                "head_ref": pr["head"]["ref"],
                "continues_from": None,
                "continued_by": None,
                "converting": body.startswith("Converting to draft"),
            }
            m = re.match(r"Continues #(\d+)", body)
            if m:
                entry["continues_from"] = int(m.group(1))
            if state == "merged":
                entry["deploy_state"] = deploy_state(c, entry["merge_sha"], policy)
                entry["deploy_ok"] = None if entry["deploy_state"] is None else entry["deploy_state"] == "success"
            commits = c.pages(f"/repos/{repo}/pulls/{n}/commits")
            cal_at = max((i for i, x in enumerate(commits) if CAL_RE.search(x["commit"]["message"])), default=None)
            if cal_at is not None:
                entry["commits_after_cal"] = [x["sha"][:8] for x in commits[cal_at + 1:]]
            if state == "closed":
                # §7.4: the continuing draft shares the head branch, in any state (it may have merged since)
                owner = pr["head"].get("repo", {}).get("owner", {}).get("login") or repo.split("/")[0]
                same_head = c.pages(f"/repos/{repo}/pulls?state=all&head={owner}:{pr['head']['ref']}")
                for o in same_head:
                    if o["number"] != n and re.match(rf"Continues #{n}\b", o.get("body") or ""):
                        entry["continued_by"] = o["number"]
            out["prs"].append(entry)
        out["reachable"] = True
    except Unreachable as e:
        out["reason"] = str(e)
    return out


# --- output --------------------------------------------------------------------

ROW_TEXT = {
    "G1": "PRs unchecked",
    "G2": "main not deployed",
    "G3": "ready, green",
    "G4": "ready, checks pending",
    "G5": "ready, checks failed",
    "G5b": "ready, Actions minutes out",
    "G6": "ready, pushed after hand-off",
    "G6b": "ready by hand, never handed off",
    "G7": "draft, stale or no owner",
    "G8": "draft in progress",
    "G9": "Dependabot, green",
    "G9-ignored": "Dependabot, ignored by policy",
    "G10": "Dependabot, major bump",
    "G11": "Dependabot, checks pending",
    "G12": "Dependabot, failed",
    "G13": "other bot",
}


def to_table(rep: dict) -> str:
    lines = [f"**PR gate — {rep['repo']}** (report-only, {rep['checked_at']})"]
    if not rep["reachable"]:
        lines.append(f"- G1 {ROW_TEXT['G1']}: {rep['reason']}")
        return "\n".join(lines)
    if rep["policy_source"] == "default":
        lines.append("- Policy: unconfigured (no .claude/landing.yaml; defaults)")
    pol = rep.get("policy") or {}
    if pol.get("merge_policy_fallback"):
        lines.append(f"- Policy: merge_policy falls back to tap — {pol['merge_policy_fallback']}")
    elif pol.get("merge_policy") == "policy":
        ver = (pol.get("routing") or {}).get("version")
        lines.append(f"- Policy: merge_policy policy (.claude/policy.json v{ver}; ruled upkeep merges itself, direction keeps the tap)")
    dh = rep["default_head"]
    if dh and dh["row"]:
        lines.append(f"- G2 {ROW_TEXT['G2']}: {dh['sha'][:7]} Vercel {dh['deploy_state']}; remedy `{dh['redeploy']}`")
    elif dh and dh.get("deploy_state") == "pending":
        lines.append(f"- Deploy of {dh['sha'][:7]} still building; re-check after orientation")
    if not rep["prs"]:
        lines.append("- No open PRs.")
        return "\n".join(lines)
    lines += ["", "| # | Row | State | Checks | Age (d) | Recommendation | Title |", "|---|---|---|---|---|---|---|"]
    for p in rep["prs"]:
        extra = f" (majors: {', '.join(p['majors'])})" if p.get("majors") else ""
        if p.get("owner_required"):
            extra += " (needs an `owns:` task, else G7)"
        title = p["title"].replace("|", "/")
        if len(title) > 60:
            title = title[:57] + "…"
        lines.append(f"| {p['number']} | {p['row']} {ROW_TEXT.get(p['row'], '')} | {p.get('state', '')} | "
                     f"{p['checks'] or '—'} | {p['head_age_days']} | {p['recommendation'] or '—'}{extra} | {title} |")
    return "\n".join(lines)


def _repo_from_git() -> str | None:
    try:
        url = subprocess.run(["git", "config", "--get", "remote.origin.url"], capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:
        return None
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?/?$", url) or \
        re.search(r"/git/([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return m.group(1) if m else None


def main(argv: list[str]) -> int:
    args = list(argv)
    repo = None
    if "--repo" in args:
        i = args.index("--repo")
        repo = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    table = "--table" in args
    args = [a for a in args if a != "--table"]
    repo = repo or _repo_from_git()
    if not args or args[0] not in ("report", "check"):
        print(__doc__.strip())
        return 0
    if not repo:
        print(json.dumps({"reachable": False, "reason": "no --repo and no GitHub origin remote", "row": "G1"}))
        return 0
    try:
        if args[0] == "report":
            rep = build_report(repo)
            print(to_table(rep) if table else json.dumps(rep, indent=1))
            return 0
        nums = [int(x) for x in ",".join(args[1:]).split(",") if x.strip().isdigit()]
        print(json.dumps(build_check(repo, nums), indent=1))
    except Exception as e:  # report-only and never fatal: an internal error reads as G1, not as all clear
        rep = {"repo": repo, "reachable": False, "reason": f"pr_state internal error: {type(e).__name__}: {e}",
               "row": "G1", "recommendation": "stop", "prs": [], "blocking": True}
        print(to_table(rep) if table else json.dumps(rep, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
