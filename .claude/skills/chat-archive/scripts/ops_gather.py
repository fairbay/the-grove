#!/usr/bin/env python3
"""Gather the weekly ops read's inputs (project-health SKILL.md "Ops read", step 1) into one directory.

Writes decisions.json, cards.json, tasks.json, activity.json, runs.json and minutes.json, then prints
a JSON summary with the counts, the window and every truncation or read failure it met. The read
itself stays offline (ops_read.py, process_gate.py); this script is the only part that talks to
Grove (grove.py, GROVE_TOKEN from the environment) and GitHub (the gh CLI the session already has).

Usage:
  python3 ops_gather.py OUT_DIR [--repo fairbay/ops --repo fairbay/<other> ...] [--days 7]
      [--until YYYY-MM-DD] [--decision-ref REF ...]

--repo: the repos whose commits, workflow runs and Actions minutes are read (default: fairbay/ops and
fairbay/medicaid-benefits-navigator, the two with a .claude/policy.json). Each needs GitHub read access
in the session (add_repo); a repo that cannot be read is named in the summary, never silently skipped.
--decision-ref: the project_ref values dumped (default: each --repo plus "ops").

Python 3.11, stdlib only. The policy files are not gathered: a clone has ops's, and another repo's comes
from `gh api repos/<repo>/contents/.claude/policy.json -H "Accept: application/vnd.github.raw"`.
"""
import argparse
import importlib.util
import json
import math
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_REPOS = ["fairbay/ops", "fairbay/medicaid-benefits-navigator"]
RUN_WORKFLOWS = {"fairbay/ops": ["sync.yml"], "*": ["rules.yml"]}  # the newest run of each: ops syncs, the others lint rules
EVENT_TYPES = ["task", "idea", "decision", "project"]
EVENT_PAGE = 200  # /api/events returns at most 200 rows and has no paging


def load_grove():
    """grove.py from the grove skill beside this one (synced into every repo together)."""
    path = HERE.parent.parent / "grove" / "scripts" / "grove.py"
    if not path.exists():
        raise SystemExit(f"grove.py not found at {path}; the grove skill is synced with chat-archive")
    spec = importlib.util.spec_from_file_location("grove", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def gh_json(path, notes, gh=None):
    gh = gh or (lambda p: subprocess.run(["gh", "api", p], capture_output=True, text=True))
    r = gh(path)
    if r.returncode:
        notes.append(f"gh {path}: {(r.stderr or '').strip()[:160]}")
        return None
    try:
        return json.loads(r.stdout)
    except ValueError:
        notes.append(f"gh {path}: not JSON")
        return None


def iso_z(dt):
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def run_minutes(run):
    """Whole minutes of one Actions run, rounded up (the plan bills per run, rounded up)."""
    s, u = run.get("run_started_at"), run.get("updated_at")
    if not s or not u:
        return None
    secs = (parse_iso(u) - parse_iso(s)).total_seconds()
    return max(1, math.ceil(secs / 60))


def event_row(e):
    diff = e.get("diff") if isinstance(e.get("diff"), dict) else {}
    ref = diff.get("project_ref") if isinstance(diff, dict) else None
    return {"repo": ref or "grove", "date": e["created_at"], "kind": e["kind"], "ref": e["entity_id"][:8],
            "message": f"{e['kind']} {e['entity_type']} ({e.get('source')})"}


def gather(out, repos, decision_refs, days, until, grove, gh=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    notes = []
    until_dt = datetime.combine(until, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
    since = until_dt - timedelta(days=days)
    month_start = until.replace(day=1)

    decisions = []
    for ref in decision_refs:
        rows = grove.list_items("decision", project_ref=ref, current_only=False, limit=grove.DECISION_LIMIT)
        if len(rows) >= grove.DECISION_LIMIT:
            notes.append(f"decisions {ref}: hit the {grove.DECISION_LIMIT}-row cap; S4's window may be truncated")
        decisions += rows
    (out / "decisions.json").write_text(json.dumps(decisions))
    (out / "cards.json").write_text(json.dumps(grove.list_items("task", tag="wrong_question", limit=100)))
    (out / "tasks.json").write_text(json.dumps(grove.list_items("task", tag="ledger", status="open", limit=100)))

    activity = []
    for repo in repos:
        commits = gh_json(f"repos/{repo}/commits?since={iso_z(since)}&per_page=100", notes, gh) or []
        for c in commits:
            activity.append({"repo": repo, "date": c["commit"]["committer"]["date"], "kind": "commit",
                             "ref": c["sha"][:8], "message": c["commit"]["message"].splitlines()[0]})
    for et in EVENT_TYPES:
        evs = grove.events(entity_type=et, limit=EVENT_PAGE)
        if evs and evs[-1]["created_at"] > since.isoformat():
            notes.append(f"events {et}: {EVENT_PAGE}-row cap reached at {evs[-1]['created_at'][:19]}; earlier events in the window unread")
        activity += [event_row(e) for e in evs if e["created_at"] >= since.isoformat()]
    (out / "activity.json").write_text(json.dumps(activity))

    runs = []
    for repo in repos:
        for wf in RUN_WORKFLOWS.get(repo, RUN_WORKFLOWS["*"]):
            d = gh_json(f"repos/{repo}/actions/workflows/{wf}/runs?per_page=1", notes, gh)
            if d and d.get("workflow_runs"):
                r = d["workflow_runs"][0]
                runs.append({"repo": repo, "workflow": wf, "name": r.get("name"), "path": r.get("path"),
                             "conclusion": r.get("conclusion"), "status": r.get("status"),
                             "created_at": r.get("created_at"), "html_url": r.get("html_url"), "head_sha": r.get("head_sha")})
    (out / "runs.json").write_text(json.dumps(runs))

    minutes = []
    for repo in repos:
        page = 1
        while True:
            d = gh_json(f"repos/{repo}/actions/runs?created=>={month_start.isoformat()}&per_page=100&page={page}", notes, gh)
            if not d:
                break
            rows = d.get("workflow_runs", [])
            for r in rows:
                m = run_minutes(r)
                if m is not None:
                    minutes.append({"repo": repo, "date": r["run_started_at"][:10], "minutes": m, "workflow": r.get("name")})
            if len(rows) < 100:
                break
            page += 1
    (out / "minutes.json").write_text(json.dumps(minutes))

    return {"window": f"{since.date().isoformat()} to {until.isoformat()}", "decisions": len(decisions),
            "activity": len(activity), "runs": len(runs), "minutes_rows": len(minutes),
            "minutes_total": sum(m["minutes"] for m in minutes), "notes": notes}


def main(argv=None):
    p = argparse.ArgumentParser(prog="ops_gather.py", description="Gather the weekly ops read's inputs.")
    p.add_argument("out_dir")
    p.add_argument("--repo", action="append", default=[])
    p.add_argument("--decision-ref", action="append", default=[])
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--until")
    a = p.parse_args(argv)
    repos = a.repo or DEFAULT_REPOS
    refs = a.decision_ref or (repos + ["ops"])
    until = date.fromisoformat(a.until) if a.until else datetime.now(timezone.utc).date()
    if not os.environ.get("GROVE_TOKEN"):
        print("GROVE_TOKEN is not set in the environment", file=sys.stderr)
        return 2
    summary = gather(a.out_dir, repos, refs, a.days, until, load_grove())
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
