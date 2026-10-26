#!/usr/bin/env python3
"""Clone-path tests for git_push._push_via_cli (temp clone + bare remote)."""
import os, subprocess, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(__file__))
import git_push


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class CloneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        self.remote = os.path.join(root, "remote.git")
        self.clone = os.path.join(root, "clone")
        git(root, "init", "--bare", "-b", "main", self.remote)
        git(root, "clone", self.remote, self.clone)
        git(self.clone, "config", "user.name", "t")
        git(self.clone, "config", "user.email", "t@example.com")
        git(self.clone, "checkout", "-b", "main")
        with open(os.path.join(self.clone, "a.txt"), "w") as f:
            f.write("one\n")
        git(self.clone, "add", "a.txt")
        git(self.clone, "commit", "-m", "init")
        git(self.clone, "push", "-u", "origin", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_already_in_clone_by_path(self):
        path = os.path.join(self.clone, "a.txt")
        with open(path, "w") as f:
            f.write("two\n")
        sha, _ = git_push._push_via_cli(self.clone, "main", "edit", [("a.txt", path)])
        self.assertEqual(git(self.remote, "rev-parse", "main"), sha)

    def test_branch_mismatch_refuses(self):
        git(self.clone, "checkout", "-b", "other")
        with self.assertRaises(RuntimeError) as cm:
            git_push._push_via_cli(self.clone, "main", "x", [("b.txt", b"b")])
        self.assertIn("not the target", str(cm.exception))


class LandByPrTests(unittest.TestCase):
    """Ruling 3fa9a61e (2026-10-21): every surface lands by PR; no push to main."""

    def test_push_files_refuses_outside_claude_branches(self):
        for branch in ("main", "master", "feature/x", "claud/x"):
            with self.assertRaises(RuntimeError) as cm:
                git_push.push_files("fairbay/x", branch, "m", [("a.txt", b"a")])
            self.assertIn("3fa9a61e", str(cm.exception))

    def test_push_and_verify_refuses_main(self):
        with self.assertRaises(RuntimeError):
            git_push.push_and_verify("fairbay/x", "main", "m", [("a.txt", b"a")])


class PushToPrTests(unittest.TestCase):
    """push_to_pr: new claude/* branch from origin/main in the clone, one draft PR."""

    def setUp(self):
        CloneTests.setUp(self)
        self.calls = []
        self.prs = []
        self.post_status = 201
        self._saved = (git_push.api, git_push._find_repo_clone)

        def fake_api(method, path, body=None):
            self.calls.append((method, path, body))
            if method == "GET" and "/pulls?" in path:
                return 200, self.prs
            if method == "POST" and path.endswith("/pulls"):
                return self.post_status, {"html_url": "https://github.com/fairbay/x/pull/7"}
            return 404, {}
        git_push.api = fake_api
        git_push._find_repo_clone = lambda _r: self.clone

    def tearDown(self):
        git_push.api, git_push._find_repo_clone = self._saved
        CloneTests.tearDown(self)

    def test_new_branch_and_draft_pr(self):
        path = os.path.join(self.clone, "a.txt")
        with open(path, "w") as f:
            f.write("two\n")  # uncommitted edit on main rides to the new branch
        sha, _, pr = git_push.push_to_pr("fairbay/x", "claude/t", "edit a", [("a.txt", path)])
        self.assertEqual(git(self.remote, "rev-parse", "claude/t"), sha)
        self.assertEqual(git(self.remote, "show", "main:a.txt"), "one")  # main untouched
        self.assertEqual(pr, "https://github.com/fairbay/x/pull/7")
        posts = [b for m, p, b in self.calls if m == "POST"]
        self.assertEqual(len(posts), 1)
        self.assertTrue(posts[0]["draft"])
        self.assertEqual((posts[0]["head"], posts[0]["base"]), ("claude/t", "main"))
        # no upstream on the new branch: a bare `git push` cannot reach main
        r = subprocess.run(["git", "config", "branch.claude/t.merge"], cwd=self.clone,
                           capture_output=True, text=True)
        self.assertNotEqual(r.stdout.strip(), "refs/heads/main")

    def test_existing_pr_gets_the_commit(self):
        self.prs = [{"number": 3, "state": "open", "html_url": "https://github.com/fairbay/x/pull/3"}]
        _, _, pr = git_push.push_to_pr("fairbay/x", "claude/t", "add b", [("b.txt", b"b")])
        self.assertEqual(pr, "https://github.com/fairbay/x/pull/3")
        self.assertFalse([c for c in self.calls if c[0] == "POST"])

    def test_landed_branch_refuses(self):
        self.prs = [{"number": 2, "state": "closed", "html_url": "u"}]
        with self.assertRaises(RuntimeError) as cm:
            git_push.push_to_pr("fairbay/x", "claude/t", "m", [("b.txt", b"b")])
        self.assertIn("already landed", str(cm.exception))
        self.assertEqual(git(self.remote, "branch", "--list", "claude/t"), "")

    def test_remote_only_branch_continues_its_history(self):
        # an earlier session pushed claude/t; main moved on; this is a fresh clone
        git(self.clone, "switch", "-c", "claude/t")
        with open(os.path.join(self.clone, "b.txt"), "w") as f:
            f.write("b\n")
        git(self.clone, "add", "b.txt"); git(self.clone, "commit", "-m", "b")
        git(self.clone, "push", "origin", "claude/t")
        git(self.clone, "switch", "main"); git(self.clone, "branch", "-D", "claude/t")
        with open(os.path.join(self.clone, "c.txt"), "w") as f:
            f.write("c\n")
        git(self.clone, "add", "c.txt"); git(self.clone, "commit", "-m", "c")
        git(self.clone, "push", "origin", "main")
        self.prs = [{"number": 3, "state": "open", "html_url": "https://github.com/fairbay/x/pull/3"}]
        sha, _, _ = git_push.push_to_pr("fairbay/x", "claude/t", "d", [("d.txt", b"d")])
        log = git(self.remote, "log", "--format=%s", "claude/t").split()
        self.assertEqual(log, ["d", "b", "init"])  # main's "c" not replayed in

    def test_rerun_after_failed_pr_open(self):
        self.post_status = 502
        with self.assertRaises(RuntimeError):
            git_push.push_to_pr("fairbay/x", "claude/t", "m", [("b.txt", b"b")])
        self.post_status = 201
        sha, _, pr = git_push.push_to_pr("fairbay/x", "claude/t", "m", [("b.txt", b"b")])
        self.assertEqual(pr, "https://github.com/fairbay/x/pull/7")
        self.assertEqual(git(self.remote, "rev-parse", "claude/t"), sha)

    def test_push_and_merge_only_on_self_landing_repos(self):
        with self.assertRaises(RuntimeError) as cm:
            git_push.push_and_merge("fairbay/medicaid-benefits-navigator", "m", [("b.txt", b"b")])
        self.assertIn("push_to_pr", str(cm.exception))
        self.assertEqual(self.calls, [])

    def test_refuses_main(self):
        with self.assertRaises(RuntimeError):
            git_push.push_to_pr("fairbay/x", "main", "m", [("b.txt", b"b")])
        self.assertEqual(self.calls, [])


class TokenTests(unittest.TestCase):
    """2026-10-19: chat sessions read a write-scoped PAT from Vault; the proxy makes that unnecessary."""
    KEYS = ("GITHUB_PAT", "GITHUB_PAT_PATH", "HTTPS_PROXY")  # GITHUB_PAT_PATH: proves it is ignored

    def _token(self, **env):
        saved = {k: os.environ.pop(k, None) for k in self.KEYS}
        os.environ.update(env)
        try:
            return git_push._token()
        finally:
            for k in self.KEYS:
                os.environ.pop(k, None)
                if saved[k] is not None:
                    os.environ[k] = saved[k]

    def test_explicit_pat_wins(self):
        self.assertEqual(self._token(GITHUB_PAT=" ghp_x\n", HTTPS_PROXY="http://p"), "ghp_x")

    def test_proxy_placeholder_without_pat(self):
        self.assertEqual(self._token(GITHUB_PAT_PATH="/nonexistent", HTTPS_PROXY="http://p"), git_push.PROXY_TOKEN)

    def test_no_auth_raises(self):
        with self.assertRaises(RuntimeError):
            self._token(GITHUB_PAT_PATH="/nonexistent")

    def test_no_key_file_is_read(self):
        """faca1b33: a token file never counts as auth, even when it exists."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt") as f:
            f.write("ghp_from_file\n")
            f.flush()
            self.assertEqual(self._token(GITHUB_PAT_PATH=f.name, HTTPS_PROXY="http://p"), git_push.PROXY_TOKEN)
            with self.assertRaises(RuntimeError):
                self._token(GITHUB_PAT_PATH=f.name)


class RemotePathTests(unittest.TestCase):
    """ba29ce5b: a remote_path never writes outside the clone's tree."""

    REFUSED = ["../x", "/etc/x", ".git/hooks/h", ".git", "a/.GIT/config", "a/.git./x", "a/../b", "a/./b", ".",
               "./a.txt", "a//b", "a/", "a\\b", "", "-A", "--all", ":(top)x", "*", "a?.txt", "a[1].txt", "a\0b"]

    def test_bad_paths_refused_by_push_files(self):
        for bad in self.REFUSED:
            with self.subTest(path=bad):
                with self.assertRaises(RuntimeError) as cm:
                    git_push.push_files("fairbay/x", "claude/t", "m", [(bad, b"x")])
                self.assertIn("refused", str(cm.exception))

    def test_bytes_path_refused_with_its_own_message(self):
        with self.assertRaises(RuntimeError) as cm:
            git_push.check_remote_path(b"a.txt")
        self.assertIn("must be a str", str(cm.exception))

    def test_generator_files_are_not_consumed_by_the_check(self):
        t = CloneTests(); t.setUp()
        try:
            git(t.clone, "checkout", "-b", "claude/t")
            saved = git_push._find_repo_clone
            git_push._find_repo_clone = lambda _r: t.clone
            try:
                sha, _ = git_push.push_files("fairbay/x", "claude/t", "m", ((p, b"g") for p in ["g.txt"]))
            finally:
                git_push._find_repo_clone = saved
            self.assertEqual(git(t.remote, "show", "claude/t:g.txt"), "g")
        finally:
            t.tearDown()

    def test_good_paths_pass(self):
        for good in ["a.txt", "docs/a.md", ".claude/skills/x/SKILL.md", ".github/workflows/ci.yml"]:
            self.assertEqual(git_push.check_remote_path(good), good)

    def test_symlinked_parent_refused_in_clone(self):
        t = CloneTests(); t.setUp()
        try:
            outside = os.path.join(t.tmp.name, "outside-target")
            os.makedirs(outside)
            os.symlink(outside, os.path.join(t.clone, "link"))
            with self.assertRaises(RuntimeError) as cm:
                git_push._push_via_cli(t.clone, "main", "m", [("link/evil.txt", b"x")])
            self.assertIn("symlink", str(cm.exception))
            self.assertFalse(os.path.exists(os.path.join(outside, "evil.txt")))
            # a symlink as the final component, through the writer every route shares
            os.symlink(os.path.join(outside, "target.txt"), os.path.join(t.clone, "leaf"))
            with self.assertRaises(RuntimeError):
                git_push._write_files(t.clone, [("leaf", b"x")])
            self.assertFalse(os.path.exists(os.path.join(outside, "target.txt")))
        finally:
            t.tearDown()


class ReadFileBranchTests(unittest.TestCase):
    """ba29ce5b: read_file(branch=) names the branch read, whatever the clone has checked out."""

    def setUp(self):
        CloneTests.setUp(self)
        self._saved = git_push._find_repo_clone
        git_push._find_repo_clone = lambda _r: self.clone

    def tearDown(self):
        git_push._find_repo_clone = self._saved
        CloneTests.tearDown(self)

    def test_main_read_while_clone_sits_on_a_pr_branch(self):
        git(self.clone, "checkout", "-b", "claude/t")
        with open(os.path.join(self.clone, "a.txt"), "w") as f:
            f.write("two\n")
        git(self.clone, "commit", "-am", "edit")
        git(self.clone, "push", "-u", "origin", "claude/t")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt", branch="main"), "one\n")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt", branch="claude/t"), "two\n")

    def test_checked_out_branch_sees_uncommitted_edit(self):
        with open(os.path.join(self.clone, "a.txt"), "w") as f:
            f.write("dirty\n")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt", branch="main"), "dirty\n")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt"), "dirty\n")  # default: the working tree

    def test_default_reads_working_tree_whatever_the_branch_name(self):  # review of #91, finding 3
        git(self.clone, "checkout", "-b", "master")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt"), "one\n")

    def test_stale_origin_ref_is_refreshed(self):  # finding 5
        git(self.clone, "checkout", "-b", "claude/t")
        other = os.path.join(self.tmp.name, "other")
        git(self.tmp.name, "clone", "-q", self.remote, other)
        git(other, "config", "user.name", "t"); git(other, "config", "user.email", "t@example.com")
        with open(os.path.join(other, "a.txt"), "w") as f:
            f.write("newer\n")
        git(other, "commit", "-am", "newer"); git(other, "push", "origin", "main")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt", branch="main"), "newer\n")

    def test_directory_and_symlink_raise(self):  # finding 4 and 8
        os.makedirs(os.path.join(self.clone, "d")); open(os.path.join(self.clone, "d/f"), "w").close()
        os.symlink("/etc/hostname", os.path.join(self.clone, "lnk"))
        git(self.clone, "add", "-A"); git(self.clone, "commit", "-m", "d"); git(self.clone, "push", "origin", "main")
        git(self.clone, "checkout", "-b", "claude/t")
        saved = git_push.api
        git_push.api = lambda *a, **k: (404, {})
        try:
            for p in ("d", "lnk"):
                with self.assertRaises(RuntimeError):
                    git_push.read_file("fairbay/x", p, branch="main")
            with self.assertRaises(RuntimeError):
                git_push.read_file("fairbay/x", "lnk")
        finally:
            git_push.api = saved

    def test_branch_the_clone_lacks_is_fetched(self):
        # a second clone pushes a branch this clone has never seen
        other = os.path.join(self.tmp.name, "other")
        git(self.tmp.name, "clone", "-q", self.remote, other)
        git(other, "config", "user.name", "t"); git(other, "config", "user.email", "t@example.com")
        git(other, "checkout", "-b", "claude/far")
        with open(os.path.join(other, "a.txt"), "w") as f:
            f.write("far\n")
        git(other, "commit", "-am", "far"); git(other, "push", "-u", "origin", "claude/far")
        self.assertEqual(git_push.read_file("fairbay/x", "a.txt", branch="claude/far"), "far\n")


if __name__ == "__main__":
    unittest.main()
