"""driver/box.py's docker run command, and the container's settings file from settings.write(inside=
True), and the --docker argument of run-steps.py. Every folder is a temporary one, resolved with
os.path.realpath, and each path in a comparison is replaced by a placeholder first, so a failure
message holds no absolute path."""

import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BANNED = ["--privileged", "-v", "--volume"]
HALT = 'python "/driver/hooks/halt.py" "/state/halt" "/state/refusals"'
GUARD = 'python "/driver/hooks/guard.py" "/driver" "/state/refusals"'


class BoxCommandTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, so a missing module fails each test alone; driver.box
        # only in the test that uses it, so the others show their own red.
        self.settings = importlib.import_module("driver.settings")

    def folder(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return os.path.realpath(tmp.name)

    def substitute(self, argv, places):
        # Each folder's path becomes its placeholder, in every element that holds it, and the
        # separator becomes /, so a failure reads the same on Windows and on CI's Linux.
        out = []
        for item in argv:
            for value, place in places:
                item = item.replace(value, place)
            out.append(item.replace(os.sep, "/"))
        return out

    def test_the_mounts(self):
        self.box = importlib.import_module("driver.box")
        home = self.folder()
        state = self.folder()
        project = self.folder()
        secrets = os.path.join(self.folder(), "secrets.env")
        places = [
            (secrets, "<secrets>"),
            (home, "<home>"),
            (state, "<state>"),
            (project, "<project>"),
        ]
        argv = self.box.command(
            "docker", "img:1", secrets, home, state, project, "driver-s1", ["claude", "-p"]
        )
        mounts = [
            "type=bind,source=<project>,target=/work",
            "type=bind,source=<home>/hooks,target=/driver/hooks,readonly",
            "type=bind,source=<home>/rules,target=/driver/rules,readonly",
            "type=bind,source=<state>,target=/state,readonly",
            "type=bind,source=<state>/refusals,target=/state/refusals",
            "type=bind,source=<state>/claude,target=/claude",
        ]
        head = ["docker", "run", "-i", "--rm", "--name", "driver-s1"]
        head += ["--env-file", "<secrets>", "-e", "CLAUDE_CONFIG_DIR=/claude", "-w", "/work"]
        expected = head
        for mount in mounts:
            expected += ["--mount", mount]
        expected += ["img:1", "claude", "-p"]
        got = self.substitute(argv, places)
        self.assertEqual(got, expected)

        banned = [item for item in argv if item in BANNED]
        self.assertEqual(banned, [])
        sources = [
            part[len("source=") :] for item in got for part in item.split(",") if "source=" in part
        ]
        self.assertEqual(sources, [mount.split(",")[1][len("source=") :] for mount in mounts])
        self.assertEqual(len(sources), 6)
        self.assertNotIn("<home>", sources)
        quiet = self.box.command(
            "docker",
            "img:1",
            secrets,
            home,
            state,
            project,
            "driver-s1",
            ["claude", "-p"],
            stdin=False,
        )
        self.assertEqual(
            self.substitute(quiet, places), [item for item in expected if item != "-i"]
        )

    def test_container_settings(self):
        state = self.folder()
        other = self.folder()
        home = self.folder()
        path = self.settings.write(state, home, inside=True)
        self.assertEqual(os.path.dirname(path), state)
        self.assertEqual(os.path.basename(path), "container-settings.json")
        with open(path, "rb") as f:
            body = json.loads(f.read().decode("utf-8"))
        pre = body["hooks"]["PreToolUse"]
        self.assertEqual([entry["hooks"][0]["command"] for entry in pre], [HALT, GUARD])
        matchers = [entry["matcher"] for entry in pre]
        self.assertEqual(matchers, ["*", self.settings.GUARDED])

        other_path = self.settings.write(other, home)
        with open(other_path, "rb") as f:
            other_pre = json.loads(f.read().decode("utf-8"))["hooks"]["PreToolUse"]
        self.assertEqual(matchers, [entry["matcher"] for entry in other_pre])
        self.assertFalse(os.path.exists(os.path.join(state, "settings.json")))

    def test_docker_flag(self):
        done = subprocess.run(
            [sys.executable, "run-steps.py", "--help"], check=False, cwd=ROOT, capture_output=True
        )
        named = "--docker" in done.stdout.decode("utf-8")
        self.assertTrue(named, "run-steps.py --help names no --docker")


if __name__ == "__main__":
    unittest.main()
