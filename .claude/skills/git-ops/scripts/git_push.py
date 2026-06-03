#!/usr/bin/env python3
"""
Atomic multi-file GitHub push via Git Data API or native git CLI.
Shipped with the git-ops skill.

Usage (CLI):
  git_push.py <owner/repo> <branch> <commit_msg> <remote_path>:<local_path> [...]

Usage (Python):
  from git_push import push_files, read_file, list_files, delete_repo, api

Environment auto-detection:
  If the target repo is cloned locally (e.g., in a Routine), push_files()
  uses native git CLI through the authenticated git proxy — 1 network call.
  Otherwise, it falls back to the Git Data API — 6 network calls.

Token resolution order (API path only):
  1. $GITHUB_PAT env var — set from Claude memory edit in chat sessions
  2. $GITHUB_PAT_PATH env var (path to file holding token)
  3. /home/claude/github-pat.txt (dev fallback)
  In Routines, read_file/list_files/push_files auto-detect the local clone
  and read from disk — no token needed.
"""
import os
import sys
import json
import base64
import shutil
import subprocess
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Git identity — hardcoded to match GitHub account + Vercel team membership.
# Without this, Claude Code sessions invent plausible-looking emails that
# don't match any real account, causing Vercel seat-block on production.
# ---------------------------------------------------------------------------
GIT_AUTHOR_NAME = "Baylee Miller"
GIT_AUTHOR_EMAIL = "baylee.miller@gmail.com"

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

    # Pull latest to avoid conflicts with concurrent vault updates
    try:
        _run(["git", "pull", "--rebase", "origin", branch])
    except RuntimeError:
        pass  # May fail if no upstream tracking; safe to proceed

    # Copy files into the clone at their remote paths
    for remote_path, local in files:
        dest = os.path.join(clone_path, remote_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if isinstance(local, bytes):
            with open(dest, "wb") as f:
                f.write(local)
        else:
            shutil.copy2(local, dest)

    # Stage, commit, push
    remote_paths = [rp for rp, _ in files]
    _run(["git", "add"] + remote_paths)

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

def _token():
    """Resolve GitHub PAT. In chat: set from memory edit via $GITHUB_PAT."""
    if os.environ.get("GITHUB_PAT"):
        return os.environ["GITHUB_PAT"].strip()
    path = os.environ.get("GITHUB_PAT_PATH")
    if not path:
        path = "/home/claude/github-pat.txt"
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    raise RuntimeError(
        "No GitHub PAT found. Set $GITHUB_PAT env var (from memory edit) "
        "or $GITHUB_PAT_PATH. In Routines, use clone-aware functions instead."
    )

def api(method, path, body=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(body).encode() if body is not None else None
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
        return e.code, parsed

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def push_files(owner_repo, branch, message, files):
    """Push files to a GitHub repo. Auto-detects environment.

    files = list of (remote_path, local_content_path_or_bytes)
    Atomic: single commit with all files, one parent.

    In a Routine or cloud session where the repo is cloned, uses native
    git CLI (fast, 1 network call). Otherwise uses Git Data API (6 calls).
    """
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        return _push_via_cli(clone_path, branch, message, files)
    return _push_via_api(owner_repo, branch, message, files)


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


def read_file(owner_repo, remote_path, branch="main"):
    """Read a file from a GitHub repo. Uses local clone if available."""
    clone_path = _find_repo_clone(owner_repo)
    if clone_path:
        local_file = os.path.join(clone_path, remote_path)
        if os.path.isfile(local_file):
            with open(local_file, "r", errors="replace") as f:
                return f.read()
        raise RuntimeError(f"File not found in clone: {remote_path}")
    # API fallback
    code, resp = api("GET", f"/repos/{owner_repo}/contents/{remote_path}?ref={branch}")
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

