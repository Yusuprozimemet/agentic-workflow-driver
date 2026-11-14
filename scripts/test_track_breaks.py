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


class Scratch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.write("guard.py", "ok = True\n")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)

    def write(self, path, text):
        with open(os.path.join(self.dir, path), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


class TrackBreaksTest(Scratch):
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

    def record(self, report="AssertionError: the guard is off", find="ok = True"):
        os.makedirs(os.path.join(self.dir, "specs", "breaks"), exist_ok=True)
        entry = {"what": "the guard off", "file": "guard.py", "find": find, "replace": "ok = False",
                 "command": CHECK, "report": report, "blob": "0" * 40}
        self.write("specs/breaks/day-09.json", json.dumps([entry]))

    def test_a_break_recorded_in_the_day_s_manifest_replays_with_no_body_line(self):
        self.record()
        run = self.run_it("no breaks in this one\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("replays: the guard off", run.stdout)
        self.assertIn("track-breaks: 1 of 1 breaks replay on this code", run.stdout)

    def test_the_record_replaces_a_body_line_of_the_same_name(self):
        self.record(report="AssertionError: the guard is off (Windows)")
        run = self.run_it(body())
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("differs: the guard off: recorded 'AssertionError: the guard is off (Windows)'", run.stdout)
        self.record()
        run = self.run_it(body(report="AssertionError: the guard is off (Windows)"))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_a_recorded_report_linux_words_otherwise_is_saved_for_the_record(self):
        self.record(report="AssertionError: the guard is off (Windows)")
        self.write("this.md", "no breaks in this one\n")
        run = subprocess.run([sys.executable, SCRIPT, "--branch", "day-09/track-b-guard", "--body", "this.md",
                              "--reports", "linux-reports.json"], cwd=self.dir, capture_output=True, text=True,
                             encoding="utf-8", env=dict(os.environ, GITHUB_RUN_ID="77"))
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "linux-reports.json")), "no reports file written")
        self.assertIn("; saved for break.py --take-reports", run.stdout)
        self.assertIn("gh run download 77 -n linux-reports, then python scripts/break.py --take-reports "
                      "linux-reports.json", run.stdout)
        with open(os.path.join(self.dir, "linux-reports.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), [{"manifest": "specs/breaks/day-09.json", "what": "the guard off",
                                             "report": "AssertionError: the guard is off"}])

    def test_a_body_line_that_differs_is_not_saved(self):
        # only the record can take a report; a body line is fixed in the body
        self.write("this.md", body(report="AssertionError: the guard is off (Windows)"))
        run = subprocess.run([sys.executable, SCRIPT, "--branch", "day-09/track-b-guard", "--body", "this.md",
                              "--reports", "linux-reports.json"], cwd=self.dir, capture_output=True, text=True,
                             encoding="utf-8")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "linux-reports.json")))

    def test_a_branch_that_is_not_a_track_has_nothing_to_replay(self):
        run = self.run_it(body(report="anything"), branch="tooling/catch-earlier")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("no PR body to replay", run.stdout)


def spec(cid, what, report, replaced=None):
    later = f"- [x] C02.1 **new** — the guard again.\n      Replaces: {replaced} — was: the guard.\n" if replaced else ""
    return (f"# Day\n\n## Acceptance criteria\n- [x] {cid} **hold** — the guard holds.\n"
            f"      broken: {what} → {report}\n{later}")


class EarlierDaysTest(Scratch):
    """An earlier Day's in-force break is checked on every branch: its find statically, its run when
    the change touches it. #184 re-recorded ten whose finds had gone stale unseen."""

    def setUp(self):
        super().setUp()
        os.makedirs(os.path.join(self.dir, "specs", "breaks"))
        self.day(find="ok = True")
        subprocess.run(["git", "add", "-A"], cwd=self.dir, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"],
                       cwd=self.dir, check=True)

    def day(self, find, report="AssertionError: the guard is off", replaced=None):
        entry = {"what": "the guard off", "file": "guard.py", "find": find, "replace": "ok = False", "command": CHECK}
        self.write("specs/breaks/day-01.json", json.dumps([entry]))
        self.write("specs/day-01-guard.md", spec("C01.1", "the guard off", report))
        if replaced:
            self.write("specs/day-02-again.md", spec("C02.2", "none", "a reader", replaced=replaced))

    def run_branch(self, branch="tooling/catch-earlier"):
        return subprocess.run([sys.executable, SCRIPT, "--branch", branch, "--base", "HEAD"], cwd=self.dir,
                              capture_output=True, text=True, encoding="utf-8")

    def test_a_stale_find_fails_and_names_what_to_re_record(self):
        self.write("guard.py", "ok = True  # the guard\nok = True\n")
        run = self.run_branch()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("no longer applies: the guard off (C01.1): the find occurs 2 times in guard.py: re-record it "
                      "with a find that occurs once at Day 01's close and here, python scripts/break.py --record "
                      "specs/breaks/day-01.json --what 'the guard off' --file guard.py --find <text> --replace <text> -- ",
                      run.stdout)
        self.assertIn(", or pin it where it last applied, python scripts/break.py --retire specs/breaks/day-01.json "
                      "--what 'the guard off'; then python scripts/break-lines.py --spec specs/day-01-guard.md",
                      run.stdout)
        self.assertIn("0 of 1 earlier Days' breaks still apply", run.stdout)

    def test_a_replaced_criterion_s_break_is_not_checked(self):
        self.day(find="gone", replaced="C01.1")
        run = self.run_branch()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("0 of 0 earlier Days' breaks still apply", run.stdout)

    def test_the_break_runs_only_when_the_change_touches_its_file(self):
        self.day(find="ok = True", report="something else")
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "report"],
                       cwd=self.dir, check=True)
        run = self.run_branch()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("applies: the guard off (C01.1)", run.stdout)
        self.assertIn("1 of 1 earlier Days' breaks still apply, 0 run", run.stdout)
        self.write("guard.py", "ok = True\n\n")
        run = self.run_branch()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("differs: the guard off (C01.1): recorded 'something else', "
                      "replayed 'AssertionError: the guard is off'", run.stdout)

    def test_the_branch_s_own_day_is_left_to_its_close(self):
        self.write("guard.py", "ok = True  # the guard\nok = True\n")
        run = self.run_branch(branch="day-01/close-the-day")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("0 of 0 earlier Days' breaks", run.stdout)


class WorkflowTest(unittest.TestCase):
    def test_a_pull_request_and_an_edit_of_its_body_replay_the_track_s_breaks(self):
        import yaml
        path = os.path.join(os.path.dirname(SCRIPT), "..", ".github", "workflows", "track-breaks.yml")
        with open(path, encoding="utf-8") as f:
            workflow = yaml.safe_load(f)
        triggers = workflow.get("on", workflow.get(True))  # YAML 1.1 reads the key `on` as true
        self.assertIn("edited", triggers["pull_request"]["types"])
        [step] = [s for s in workflow["jobs"]["track-breaks"]["steps"] if s.get("name") == "Replay the track's breaks"]
        self.assertEqual(step["run"], 'python scripts/track-breaks.py --branch "$BRANCH" --pr "$PR" --base HEAD^1 '
                                      "--reports linux-reports.json")
        # the saved reports survive the failed step, for break.py --take-reports
        [keep] = [s for s in workflow["jobs"]["track-breaks"]["steps"] if s.get("uses", "").startswith("actions/upload")]
        self.assertEqual((keep["with"]["path"], keep["with"]["name"]), ("linux-reports.json", "linux-reports"))
        self.assertIn("failure()", keep["if"])
        self.assertEqual(step["env"]["BRANCH"], "${{ github.head_ref }}")
        # HEAD^1, main's side of the merge commit, is there only when the checkout fetches two commits.
        [checkout] = [s for s in workflow["jobs"]["track-breaks"]["steps"] if s.get("uses", "").startswith("actions/checkout")]
        self.assertEqual(checkout["with"]["fetch-depth"], 2)


if __name__ == "__main__":
    unittest.main()
