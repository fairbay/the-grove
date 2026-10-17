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


if __name__ == "__main__":
    unittest.main()
