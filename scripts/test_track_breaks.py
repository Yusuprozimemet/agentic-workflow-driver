"""scripts/track-breaks.py replays a track PR's recorded breaks before the close does.

Each test builds a scratch git repository with one file and a check, writes PR bodies holding
`manifest:` and `broken:` lines as break.py prints them, and runs the script there.

    python scripts/test_track_breaks.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track-breaks.py")
CHECK = [sys.executable, "-c", "import sys; t = open('guard.py').read(); "
         "sys.exit('AssertionError: the guard is off') if 'False' in t else None"]


def body(find="ok = True", report="AssertionError: the guard is off", what="the guard off"):
    entry = {"what": what, "file": "guard.py", "find": find, "replace": "ok = False", "command": CHECK}
    return f"## Breaks\n\nmanifest: {json.dumps(entry)}\nbroken: {what} → {report}\n"


class TrackBreaksTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.write("guard.py", "ok = True\n")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)

    def write(self, path, text):
        with open(os.path.join(self.dir, path), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def run_it(self, this, *earlier, branch="day-09/track-b-guard"):
        self.write("this.md", this)
        names = []
        for n, text in enumerate(earlier):
            self.write(f"earlier{n}.md", text)
            names.append(f"earlier{n}.md")
        return subprocess.run([sys.executable, SCRIPT, "--branch", branch, "--body", "this.md",
                               "--earlier", *names], cwd=self.dir, capture_output=True, text=True,
                              encoding="utf-8")

    def test_a_recorded_break_that_replays_passes(self):
        run = self.run_it(body())
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("replays: the guard off", run.stdout)
        self.assertIn("track-breaks: 1 of 1 breaks replay on this code", run.stdout)

    def test_a_report_recorded_on_another_machine_fails_here(self):
        # D08.83: a report recorded on Windows was 6 characters longer than Linux's.
        run = self.run_it(body(report="AssertionError: the guard is off (Windows)"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("differs: the guard off: recorded 'AssertionError: the guard is off (Windows)', "
                      "replayed 'AssertionError: the guard is off'", run.stdout)

    def test_an_earlier_track_s_find_this_code_changed_fails_until_recorded_again(self):
        # D08.82: Track C1 changed the line a break recorded on #111 replaced; the close found it.
        earlier = body(find="ok = True  # the guard", what="the guard off, by its comment")
        run = self.run_it("no breaks in this one\n", earlier)
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("failed: the guard off, by its comment: ", run.stdout)
        self.assertIn("--find occurs 0 times", run.stdout)
        run = self.run_it(body(what="the guard off, by its comment"), earlier)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_a_manifest_line_with_no_broken_line_fails(self):
        run = self.run_it(body().split("broken:")[0])
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("no broken: line: the guard off", run.stdout)

    def test_a_branch_that_is_not_a_track_has_nothing_to_replay(self):
        run = self.run_it(body(report="anything"), branch="tooling/catch-earlier")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("nothing to replay", run.stdout)


class WorkflowTest(unittest.TestCase):
    def test_a_pull_request_and_an_edit_of_its_body_replay_the_track_s_breaks(self):
        import yaml
        path = os.path.join(os.path.dirname(SCRIPT), "..", ".github", "workflows", "track-breaks.yml")
        with open(path, encoding="utf-8") as f:
            workflow = yaml.safe_load(f)
        triggers = workflow.get("on", workflow.get(True))  # YAML 1.1 reads the key `on` as true
        self.assertIn("edited", triggers["pull_request"]["types"])
        [step] = [s for s in workflow["jobs"]["track-breaks"]["steps"] if s.get("name") == "Replay the track's breaks"]
        self.assertEqual(step["run"], 'python scripts/track-breaks.py --branch "$BRANCH" --pr "$PR"')
        self.assertEqual(step["env"]["BRANCH"], "${{ github.head_ref }}")


if __name__ == "__main__":
    unittest.main()
