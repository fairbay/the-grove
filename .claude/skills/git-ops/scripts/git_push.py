#!/usr/bin/env python3
"""
Atomic multi-file GitHub push via Git Data API or native git CLI.
Shipped with the git-ops skill.

Usage (CLI):
  git_push.py <owner/repo> <branch> <commit_msg> <remote_path>:<local_path> [...]

Usage (Python):
  from git_push import push_to_pr, push_files, read_file, list_files, delete_repo, api

Every surface lands by pull request (Baylee's ruling 3fa9a61e, 2026-10-21):
push_files() refuses any branch outside claude/*, so no session pushes a
repo's main. push_to_pr() opens the branch and its draft PR in one call.

Environment auto-detection:
  If the target repo is cloned locally (e.g., in a Routine), push_files()
  uses native git CLI through the authenticated git proxy — 1 network call.
  Otherwise, it falls back to the Git Data API — 6 network calls.

Auth resolution (API path only):
  1. $GITHUB_PAT env var (Routines and Code sessions whose environment sets one)
  2. The session's agent proxy ($HTTPS_PROXY set): a placeholder token; the
     proxy injects real credentials for repos attached with add_repo. This is
     the chat path — no session reads the Vault PAT.
  In Routines, read_file/list_files/push_files auto-detect the local clone
  and read from disk — no token needed.
"""
import os
import posixpath
import sys
import json
import base64
import shutil
import subprocess
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Git identity — hardcoded to match GitHub account + Vercel Hobby plan owner.
# Vercel Hobby blocks deploys when the commit author email can't be resolved
# to the team owner's GitHub account. The noreply email is guaranteed linked.
# Every push path (CLI, API, native fallback) uses these constants.
# ---------------------------------------------------------------------------
GIT_AUTHOR_NAME = "fairbay"
GIT_AUTHOR_EMAIL = "104952098+fairbay@users.noreply.github.com"

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

def _find_repo_clone(owner_repo):
    """Return the local path to a git clone of owner_repo, or None.

    Checks common clone locations used by Claude Code cloud sessions and
    Routines. Confirms via git remote URL match to avoid false positives.
    """
    _, name = owner_repo.split("/", 1)
    candidates = [
        os.path.join(os.path.expanduser("~"), name),
        os.path.join("/home/user", name),
        os.path.abspath(name),
        os.path.abspath(os.path.join("..", name)),
    ]
    for path in candidates:
        if not os.path.isdir(os.path.join(path, ".git")):
            continue
        try:
            result = subprocess.run(
                ["git", "-C", path, "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and name in result.stdout:
                return path
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None

# ---------------------------------------------------------------------------
# Git CLI push (Routine / cloud session path)
# ---------------------------------------------------------------------------

def check_remote_path(remote_path, clone_path=None):
    """Refuse a remote_path that would write outside the intended tree, or that
    `git add` would read as a flag or pathspec magic (ba29ce5b).

    Rejected: empty or not a str, absolute, a backslash, `:` or NUL, a leading
    `-`, a glob character (`*?[`), a `.`, `..` or `.git` segment (any case,
    trailing dots or spaces ignored), or a path that is not already normalized
    (`./x`, `a//b`, a trailing slash). With clone_path, a path component that
    is a symlink is refused too, so a copy can't follow it out of the clone.
    Returns the path.
    """
    if not isinstance(remote_path, str):
        raise RuntimeError(f"refused: remote_path must be a str, got {type(remote_path).__name__}")
    if not remote_path:
        raise RuntimeError("refused: empty remote_path")
    if remote_path.startswith("/") or "\\" in remote_path:
        raise RuntimeError(f"refused: remote_path {remote_path!r} must be relative, forward slashes only")
    if remote_path[0] in "-:" or any(c in remote_path for c in "*?[:\0"):
        raise RuntimeError(f"refused: remote_path {remote_path!r} would read as a git option or pathspec magic")
    if posixpath.normpath(remote_path) != remote_path or remote_path.startswith("./"):
        raise RuntimeError(f"refused: remote_path {remote_path!r} is not normalized")
    for seg in remote_path.split("/"):
        if seg in (".", "..") or seg.lower().rstrip(". ") == ".git":
            raise RuntimeError(f"refused: remote_path {remote_path!r} has a {seg!r} segment")
    if clone_path:
        cur = clone_path
        for seg in remote_path.split("/"):
            cur = os.path.join(cur, seg)
            if os.path.islink(cur):
                raise RuntimeError(f"refused: remote_path {remote_path!r} passes through symlink {seg!r}")
    return remote_path


def _write_files(clone_path, files):
    """Check every remote_path against the clone, then write each file there.
    Shared by the clone and native-fallback routes."""
    for remote_path, _ in files:
        check_remote_path(remote_path, clone_path)
    for remote_path, local in files:
        dest = os.path.join(clone_path, remote_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if isinstance(local, bytes):
            with open(dest, "wb") as f:
                f.write(local)
        elif os.path.exists(dest) and os.path.samefile(local, dest):
            pass  # already in place in the clone (copy2 would raise SameFileError)
        else:
            shutil.copy2(local, dest)


def _push_via_cli(clone_path, branch, message, files):
    """Push files using native git add/commit/push in a local clone.

    This path uses the authenticated git proxy provided by Claude Code cloud
    sessions. It avoids the 6-call Git Data API sequence entirely.
    """
    def _run(cmd, **kw):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           cwd=clone_path, **kw)
        if r.returncode != 0:
            raise RuntimeError(f"git {cmd[1]} failed: {r.stderr.strip()}")
        return r

    # The commit lands on whatever is checked out, and `git push origin
    # <branch>` pushes the local ref of that name. If they differ, the commit
    # never reaches <branch> (or a rebase rewrites the wrong branch). Refuse
    # before touching anything.
    current = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=clone_path, capture_output=True, text=True,
    ).stdout.strip()
    if current != branch:
        raise RuntimeError(
            f"clone at {clone_path} is on '{current}', not the target "
            f"branch '{branch}'. Check out '{branch}' first, or pass the "
            f"checked-out branch as the target."
        )

    # Pull latest to avoid conflicts with concurrent vault updates
    try:
        _run(["git", "pull", "--rebase", "origin", branch])
    except RuntimeError as e:
        # A new branch has no remote yet: safe to proceed. A rebase that
        # stopped on a conflict is not: undo it and refuse.
        git_dir = os.path.join(clone_path, ".git")
        if any(os.path.isdir(os.path.join(git_dir, d))
               for d in ("rebase-merge", "rebase-apply")):
            subprocess.run(["git", "rebase", "--abort"], cwd=clone_path,
                           capture_output=True)
            raise RuntimeError(f"pull --rebase of {branch} conflicted; "
                               f"aborted, nothing pushed: {e}")

    # Copy files into the clone at their remote paths
    files = list(files)
    _write_files(clone_path, files)

    # Stage, commit, push
    remote_paths = [rp for rp, _ in files]
    _run(["git", "--literal-pathspecs", "add", "--"] + remote_paths)

    # Check if there are changes to commit
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=clone_path, capture_output=True,
    )
    if status.returncode == 0:
        raise RuntimeError("No changes to commit — files may already match HEAD")

    # Set identity before committing — prevents sessions from using
    # whatever stale or invented email happens to be in git config
    subprocess.run(
        ["git", "config", "user.name", GIT_AUTHOR_NAME],
        cwd=clone_path, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", GIT_AUTHOR_EMAIL],
        cwd=clone_path, capture_output=True,
    )

    _run(["git", "commit", "-m", message])
    _run(["git", "push", "origin", branch])

    # Get the commit SHA
    sha_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=clone_path,
    )
    sha = sha_result.stdout.strip()
    owner_repo = "/".join(remote_url_to_owner_repo(clone_path))
    return sha, f"https://github.com/{owner_repo}/commit/{sha}"


def remote_url_to_owner_repo(clone_path):
    """Extract (owner, repo) from the clone's origin URL."""
    result = subprocess.run(
        ["git", "-C", clone_path, "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    url = result.stdout.strip()
    # Handle both HTTPS and proxy URLs
    # e.g., https://github.com/fairbay/idea-vault.git
    # e.g., http://local_proxy@127.0.0.1:PORT/git/fairbay/idea-vault
    for sep in ["/git/", "github.com/", "github.com:"]:
        if sep in url:
            tail = url.split(sep, 1)[1]
            tail = tail.rstrip("/").removesuffix(".git")
            parts = tail.split("/")
            if len(parts) >= 2:
                return parts[0], parts[1]
    # Fallback: return from the URL tail
    parts = url.rstrip("/").split("/")
    return parts[-2], parts[-1].removesuffix(".git")

# ---------------------------------------------------------------------------
# Token + API (chat / non-clone path)
# ---------------------------------------------------------------------------

# Placeholder sent when the session's agent proxy injects real GitHub
# credentials itself (claude.ai containers, attached repos). It is not a
# secret and authorizes nothing on its own. Same value as scripts/sync.py.
PROXY_TOKEN = "proxy-auth"


def _token():
    """Resolve GitHub auth: an explicit PAT if one is set, else the session proxy."""
    if os.environ.get("GITHUB_PAT"):
        return os.environ["GITHUB_PAT"].strip()
    if os.environ.get("HTTPS_PROXY"):
        return PROXY_TOKEN
    raise RuntimeError(
        "No GitHub auth: no agent proxy and no $GITHUB_PAT. In a claude.ai "
        "container, attach the repo with add_repo first; never read the Vault PAT."
    )

def api(method, path, body=None, _retries=8):
    """GitHub API call with retry-on-401 for egress proxy auth header drops.

    Known failure mode (2026-06-10): transparent egress proxy intermittently
    drops the Authorization header in bursts. Symptoms: valid PAT + bursty 401
    + GitHub request-ids present in response. NOT a token problem — safe to
    retry all methods including PATCH (ref update is idempotent for same SHA).
    """
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
    last_code, last_body = None, None
    for attempt in range(_retries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {_token()}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                raw = resp.read().decode()
                return resp.status, json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = {"raw": raw}
            last_code, last_body = e.code, parsed
            if e.code == 401 and attempt < _retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
            return e.code, parsed
    return last_code, last_body

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

PR_BRANCH_PREFIX = "claude/"


def _require_pr_branch(branch):
    """Refuse a push to anything but a claude/* branch (ruling 3fa9a61e).

    No exception exists today; one would be added here, by ruling, naming the
    repo it applies to.
    """
    if not branch.startswith(PR_BRANCH_PREFIX):
        raise RuntimeError(
            f"refused: push to '{branch}'. Every surface lands by pull request "
            f"(ruling 3fa9a61e): push a {PR_BRANCH_PREFIX}* branch with "
            f"push_to_pr() and land it through close-at-land."
        )


def push_files(owner_repo, branch, message, files):
    """Push files to a claude/* branch of a GitHub repo. Auto-detects environment.

    files = list of (remote_path, local_content_path_or_bytes)
    Atomic: single commit with all files, one parent. The branch must already
    exist (push_to_pr creates it); any branch outside claude/* refuses.

    In a Routine or cloud session where the repo is cloned, uses native
    git CLI (fast, 1 network call). Otherwise uses Git Data API (6 calls).
    On API 401 exhaustion (egress proxy auth flap), falls back to native
    git transport via shallow clone.
    """
    _require_pr_branch(branch)
    files = list(files)
    for remote_path, _ in files:
        check_remote_path(remote_path)
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        return _push_via_cli(clone_path, branch, message, files)
    try:
        return _push_via_api(owner_repo, branch, message, files)
    except RuntimeError as e:
        if "401" in str(e):
            print(f"[git-ops] API 401 after retries, falling back to native git: {e}",
                  file=sys.stderr)
            return _push_via_native_fallback(owner_repo, branch, message, files)
        raise


def _push_via_native_fallback(owner_repo, branch, message, files):
    """Shallow clone + commit + push when API path fails due to auth flap.

    Proven recovery path from 2026-06-10 (commit 690be66). Uses
    x-access-token:PAT@github.com for HTTPS auth through the egress proxy.
    """
    import tempfile
    token = _token()
    clone_url = f"https://x-access-token:{token}@github.com/{owner_repo}.git"
    tmpdir = tempfile.mkdtemp(prefix="git-fallback-")
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", f"--branch={branch}", clone_url, tmpdir],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", GIT_AUTHOR_NAME],
            cwd=tmpdir, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", GIT_AUTHOR_EMAIL],
            cwd=tmpdir, capture_output=True,
        )
        files = list(files)
        _write_files(tmpdir, files)
        subprocess.run(["git", "--literal-pathspecs", "add", "--"] + [rp for rp, _ in files],
                       cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=tmpdir, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=tmpdir, check=True, capture_output=True, text=True,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=tmpdir, capture_output=True, text=True,
        ).stdout.strip()
        return sha, f"https://github.com/{owner_repo}/commit/{sha}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _push_via_api(owner_repo, branch, message, files):
    """Original Git Data API push — 6 sequential API calls."""
    # 1. Get branch ref
    code, ref = api("GET", f"/repos/{owner_repo}/git/ref/heads/{branch}")
    if code >= 300:
        raise RuntimeError(f"get ref failed: {code} {ref}")
    parent_sha = ref["object"]["sha"]

    # 2. Get parent commit -> tree sha
    code, parent_commit = api("GET", f"/repos/{owner_repo}/git/commits/{parent_sha}")
    if code >= 300:
        raise RuntimeError(f"get parent commit failed: {code} {parent_commit}")
    base_tree_sha = parent_commit["tree"]["sha"]

    # 3. Create blobs
    tree_items = []
    for remote_path, local in files:
        if isinstance(local, bytes):
            content_bytes = local
        else:
            with open(local, "rb") as f:
                content_bytes = f.read()
        b64 = base64.b64encode(content_bytes).decode()
        code, blob = api("POST", f"/repos/{owner_repo}/git/blobs",
                         {"content": b64, "encoding": "base64"})
        if code >= 300:
            raise RuntimeError(f"create blob failed for {remote_path}: {code} {blob}")
        tree_items.append({
            "path": remote_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"]
        })

    # 4. Create tree (based on parent tree)
    code, tree = api("POST", f"/repos/{owner_repo}/git/trees",
                     {"base_tree": base_tree_sha, "tree": tree_items})
    if code >= 300:
        raise RuntimeError(f"create tree failed: {code} {tree}")

    # 5. Create commit
    code, commit = api("POST", f"/repos/{owner_repo}/git/commits",
                       {"message": message, "tree": tree["sha"], "parents": [parent_sha],
                        "author": {"name": GIT_AUTHOR_NAME, "email": GIT_AUTHOR_EMAIL},
                        "committer": {"name": GIT_AUTHOR_NAME, "email": GIT_AUTHOR_EMAIL}})
    if code >= 300:
        raise RuntimeError(f"create commit failed: {code} {commit}")

    # 6. Update ref
    code, upd = api("PATCH", f"/repos/{owner_repo}/git/refs/heads/{branch}",
                    {"sha": commit["sha"], "force": False})
    if code >= 300:
        raise RuntimeError(f"update ref failed: {code} {upd}")

    return commit["sha"], f"https://github.com/{owner_repo}/commit/{commit['sha']}"


def _ensure_branch_cli(clone_path, branch, base):
    """Check out branch in the clone: the local branch, else the remote one,
    else a new branch from origin/<base> (no upstream, so a bare `git push`
    can never reach <base>).

    Uncommitted edits ride along (git switch keeps them unless they conflict,
    in which case it refuses and nothing changes).
    """
    def _git(*args):
        return subprocess.run(["git", *args], cwd=clone_path,
                              capture_output=True, text=True, timeout=60)

    if _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == branch:
        return
    if _git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0:
        r = _git("switch", branch)
    elif _git("fetch", "origin", f"+refs/heads/{branch}:refs/remotes/origin/{branch}").returncode == 0:
        r = _git("switch", "-c", branch, "--track", f"origin/{branch}")
    else:
        _git("fetch", "origin", base)  # best effort; origin/<base> may be current already
        r = _git("switch", "--no-track", "-c", branch, f"origin/{base}")
    if r.returncode != 0:
        raise RuntimeError(f"git switch to '{branch}' failed: {r.stderr.strip()}")


def _ensure_branch_api(owner_repo, branch, base):
    """Create branch from base's head on GitHub if it does not exist yet."""
    code, got = api("GET", f"/repos/{owner_repo}/git/ref/heads/{branch}")
    if code < 300:
        return
    if code != 404:
        raise RuntimeError(f"get branch ref failed: {code} {got}")
    code, ref = api("GET", f"/repos/{owner_repo}/git/ref/heads/{base}")
    if code >= 300:
        raise RuntimeError(f"get base ref failed: {code} {ref}")
    code, new_ref = api("POST", f"/repos/{owner_repo}/git/refs", {
        "ref": f"refs/heads/{branch}", "sha": ref["object"]["sha"]})
    if code == 422 and "already exists" in json.dumps(new_ref):
        return  # created between the two calls
    if code >= 300:
        raise RuntimeError(f"create branch failed: {code} {new_ref}")


def _branch_prs(owner_repo, branch):
    """Every PR (open, closed, merged) whose head is branch, newest first."""
    owner = owner_repo.split("/", 1)[0]
    code, prs = api("GET", f"/repos/{owner_repo}/pulls?head={owner}:{branch}"
                           f"&state=all&sort=created&direction=desc")
    if code >= 300:
        raise RuntimeError(f"PR lookup for {branch} failed: {code} {prs}")
    return prs


def push_to_pr(owner_repo, branch, message, files, title=None, body="",
               base="main"):
    """Push files to a claude/* branch and make sure a PR is open for it.

    The default push for every surface (ruling 3fa9a61e). Creates the branch
    if it is new (from the remote branch if one exists, else from <base>),
    pushes one atomic commit, and opens a draft PR if the branch has no open
    one; a later call adds a commit to the same PR. A branch whose last PR
    merged or closed refuses: start a fresh claude/* name (push-protocol §11).
    Re-running after a failed PR open, with nothing new to commit, just opens
    the PR. Mark it ready only through close-at-land. With a local clone, the
    clone is left checked out on <branch> afterwards (read_file(branch=...)
    still reads the branch you name).

    Returns (commit_sha, commit_url, pr_url).
    """
    _require_pr_branch(branch)
    prs = _branch_prs(owner_repo, branch)
    open_prs = [p for p in prs if p.get("state") == "open"]
    if prs and not open_prs:
        raise RuntimeError(
            f"refused: {branch}'s PR #{prs[0]['number']} already landed or "
            f"closed. Use a fresh {PR_BRANCH_PREFIX}* name from origin/{base}.")
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        _ensure_branch_cli(clone_path, branch, base)
    else:
        _ensure_branch_api(owner_repo, branch, base)
    try:
        sha, commit_url = push_files(owner_repo, branch, message, files)
    except RuntimeError as e:
        if not (clone_path and "No changes to commit" in str(e)):
            raise
        # A re-run after the PR step failed: the commit is already there.
        subprocess.run(["git", "push", "origin", branch], cwd=clone_path,
                       capture_output=True, text=True, check=True)
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=clone_path,
                             capture_output=True, text=True).stdout.strip()
        commit_url = f"https://github.com/{owner_repo}/commit/{sha}"

    if open_prs:
        return sha, commit_url, open_prs[0]["html_url"]
    code, pr = api("POST", f"/repos/{owner_repo}/pulls", {
        "title": title or message.split("\n")[0][:72],
        "body": body or message,
        "head": branch,
        "base": base,
        "draft": True,
    })
    if code >= 300:
        raise RuntimeError(
            f"pushed {sha} to {branch}, but opening the PR failed: {code} {pr}. "
            f"Re-run push_to_pr with the same arguments to open it.")
    return sha, commit_url, pr["html_url"]


# push_and_merge lands at the push (no draft, no tap): only repos whose
# .claude/landing.yaml says merge_policy: self. Add a repo here only with that file.
SELF_LANDING_REPOS = {"fairbay/ops"}


def push_and_merge(owner_repo, message, files, base_branch="main"):
    """Push files via branch → PR → squash-merge → delete branch.

    The one-call landing for a merge_policy: self repo (SELF_LANDING_REPOS).
    Creates a temporary claude/auto-* branch, pushes files, creates a PR,
    squash-merges it, and deletes the branch — all in one call. Any other
    repo refuses: it lands through push_to_pr and close-at-land.

    Returns (commit_sha, diff_url) of the merge commit on the base branch.
    """
    import hashlib

    if owner_repo not in SELF_LANDING_REPOS:
        raise RuntimeError(
            f"refused: push_and_merge lands at the push, which only "
            f"{sorted(SELF_LANDING_REPOS)} allow (landing.yaml merge_policy: "
            f"self). Use push_to_pr and close-at-land.")

    slug = hashlib.md5(message.encode()).hexdigest()[:8]
    temp_branch = f"claude/auto-{slug}-{int(time.time()) % 10000}"

    # 1. Get base branch SHA
    code, ref = api("GET", f"/repos/{owner_repo}/git/ref/heads/{base_branch}")
    if code >= 300:
        raise RuntimeError(f"get base ref failed: {code} {ref}")
    base_sha = ref["object"]["sha"]

    # 2. Create temp branch
    code, new_ref = api("POST", f"/repos/{owner_repo}/git/refs", {
        "ref": f"refs/heads/{temp_branch}",
        "sha": base_sha,
    })
    if code >= 300:
        raise RuntimeError(f"create branch failed: {code} {new_ref}")

    # 3. Push files to temp branch (reuse existing API push logic)
    push_sha, _ = _push_via_api(owner_repo, temp_branch, message, files)

    # 4. Create PR
    code, pr = api("POST", f"/repos/{owner_repo}/pulls", {
        "title": message.split("\n")[0][:72],
        "body": message,
        "head": temp_branch,
        "base": base_branch,
    })
    if code >= 300:
        # Clean up branch on PR failure
        api("DELETE", f"/repos/{owner_repo}/git/refs/heads/{temp_branch}")
        raise RuntimeError(f"create PR failed: {code} {pr}")

    pr_number = pr["number"]

    # 5. Squash-merge
    code, merge = api("PUT", f"/repos/{owner_repo}/pulls/{pr_number}/merge", {
        "merge_method": "squash",
        "commit_title": message.split("\n")[0][:72],
    })
    if code >= 300:
        raise RuntimeError(
            f"merge failed: {code} {merge} — PR #{pr_number} is open at "
            f"https://github.com/{owner_repo}/pull/{pr_number}"
        )

    merge_sha = merge.get("sha", push_sha)

    # 6. Delete temp branch
    api("DELETE", f"/repos/{owner_repo}/git/refs/heads/{temp_branch}")

    return merge_sha, f"https://github.com/{owner_repo}/commit/{merge_sha}"


def read_file(owner_repo, remote_path, branch=None):
    """Read a file from a GitHub repo.

    branch=None (the default) reads the clone's working tree on whatever branch
    is checked out (an uncommitted edit is seen), or `main` through the API
    when there is no clone. A named branch is honored exactly: the working
    tree when it is checked out, else `origin/<branch>` after a quiet
    depth-1 fetch (content as of that fetch; a fetch that fails offline leaves
    the last fetched copy), else the contents API. A directory, a symlink or
    a missing path raises.
    """
    check_remote_path(remote_path)
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        check_remote_path(remote_path, clone_path)
        current = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=clone_path,
                                 capture_output=True, text=True).stdout.strip()
        if branch is None or current == branch:
            local_file = os.path.join(clone_path, remote_path)
            if os.path.isfile(local_file):
                with open(local_file, "r", errors="replace") as f:
                    return f.read()
            raise RuntimeError(f"File not found in clone: {remote_path}")
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        try:
            subprocess.run(["git", "fetch", "--quiet", "--depth=1", "origin",
                            f"+refs/heads/{branch}:refs/remotes/origin/{branch}"],
                           cwd=clone_path, capture_output=True, text=True, timeout=60, env=env)
            r = subprocess.run(["git", "cat-file", "blob", f"origin/{branch}:{remote_path}"],
                               cwd=clone_path, capture_output=True, timeout=60)
            if r.returncode == 0:
                return r.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            pass
    # API fallback
    code, resp = api("GET", f"/repos/{owner_repo}/contents/{remote_path}?ref={branch or 'main'}")
    if code >= 300:
        raise RuntimeError(f"read file failed: {code} {resp}")
    if resp.get("encoding") == "base64":
        return base64.b64decode(resp["content"]).decode("utf-8", errors="replace")
    return resp.get("content", "")

def list_files(owner_repo, path="", branch="main"):
    """List file paths under a directory. Uses local clone if available."""
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        local_dir = os.path.join(clone_path, path) if path else clone_path
        if os.path.isdir(local_dir):
            return [
                os.path.join(path, name) if path else name
                for name in sorted(os.listdir(local_dir))
                if not name.startswith(".")
            ]
        raise RuntimeError(f"Directory not found in clone: {path}")
    # API fallback
    code, resp = api("GET", f"/repos/{owner_repo}/contents/{path}?ref={branch}")
    if code >= 300:
        raise RuntimeError(f"list failed: {code} {resp}")
    if isinstance(resp, list):
        return [item["path"] for item in resp]
    # Single file result
    return [resp["path"]] if isinstance(resp, dict) and "path" in resp else []

def delete_repo(owner_repo):
    code, resp = api("DELETE", f"/repos/{owner_repo}")
    return code, resp


# ---------------------------------------------------------------------------
# push_and_verify — collapse push + deploy verification into one call
# ---------------------------------------------------------------------------

def _fetch_url(url, timeout=20):
    """GET a URL. Returns (status, body_text). HTTP errors return their code."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "fairbay-git-ops/1.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body


def push_and_verify(owner_repo, branch, message, files, verify_url=None,
                    expect=None, timeout=180, interval=15, initial_wait=25):
    """Push atomically to a claude/* branch, then verify_live() the URL.

    main is refused like any push (ruling 3fa9a61e), so for a production
    deploy, land the PR first and call verify_live() with the merge sha; this
    wrapper fits a branch whose push deploys (a preview).
    """
    sha, commit_url = push_files(owner_repo, branch, message, files)
    return verify_live(sha, commit_url, verify_url, expect=expect,
                       timeout=timeout, interval=interval,
                       initial_wait=initial_wait)


def verify_live(sha, commit_url, verify_url=None, expect=None, timeout=180,
                interval=15, initial_wait=25):
    """Verify a deploy by polling the live URL after sha landed.

    The strongest unauthenticated deploy signal is the version bump that
    push conventions already require: pass expect=<new version string>
    (e.g. "v2.4.1") and this polls verify_url until it appears in the body.

    Returns a verdict dict:
      state:
        PUSHED         -- no verify_url given; push succeeded, nothing polled
        VERIFIED_LIVE  -- 200 + expect found (expect=None -> weak reachability)
        TIMEOUT_STALE  -- 200s seen but expect never appeared (slow build, or
                          build failed and the old deploy is still serving)
        UNREACHABLE    -- no 200 within timeout (site down / first deploy broke)
      sha, commit_url  -- as passed in
      evidence         -- attempts, elapsed_s, last_status, weak flag,
                          last_body_snippet on failure

    On TIMEOUT_STALE / UNREACHABLE, escalate to the Vercel MCP diagnosis
    chain (references/vercel-mcp.md). The happy path needs no MCP calls.
    """
    verdict = {"sha": sha, "commit_url": commit_url,
               "state": "PUSHED", "evidence": {}}
    if not verify_url:
        return verdict

    sep = "&" if "?" in verify_url else "?"
    start = time.time()
    deadline = start + timeout
    attempts, last_status, last_body = 0, None, ""
    got_200 = False
    time.sleep(initial_wait)  # let Vercel pick up the commit
    while True:
        attempts += 1
        try:
            last_status, last_body = _fetch_url(
                f"{verify_url}{sep}pav={sha[:7]}-{attempts}")
        except Exception as e:  # DNS/timeout/TLS -> treat as not-yet-reachable
            last_status, last_body = None, f"fetch error: {e}"
        if last_status == 200:
            got_200 = True
            if expect is None or expect in last_body:
                verdict["state"] = "VERIFIED_LIVE"
                verdict["evidence"] = {
                    "attempts": attempts,
                    "elapsed_s": round(time.time() - start, 1),
                    "matched": expect,
                    "weak": expect is None,
                }
                return verdict
        if time.time() >= deadline:
            break
        time.sleep(interval)

    verdict["state"] = "TIMEOUT_STALE" if got_200 else "UNREACHABLE"
    verdict["evidence"] = {
        "attempts": attempts,
        "elapsed_s": round(time.time() - start, 1),
        "last_status": last_status,
        "expected": expect,
        "last_body_snippet": (last_body or "")[:400],
    }
    return verdict


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("usage: git_push.py <owner/repo> <branch> <msg> <remote:local> ...", file=sys.stderr)
        sys.exit(2)
    repo, branch, msg = sys.argv[1], sys.argv[2], sys.argv[3]
    files = []
    for arg in sys.argv[4:]:
        remote, local = arg.split(":", 1)
        files.append((remote, local))
    sha, url = push_files(repo, branch, msg, files)
    print(f"pushed: {sha}")
    print(f"diff:   {url}")

