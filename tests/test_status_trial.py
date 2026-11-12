"""status prints the tools the driver refused and the Level 2 count, from the run log, and changes
nothing. Each test runs the CLI on a state folder of its own, with a fake gh beside it, and compares
the lines it prints."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh
from tests.test_status import T1, encode, end, start

LEVEL_2 = "level 2: {} of 15 pull requests in a row merged without a change asked"
UNSET = object()


def refused_end(session, refused, denials):
    record = end(session, "opened: #20", 0.1, denials)
    record["refused"] = refused
    return record


def merged(pr, changed=UNSET):
    # A merged line with no changed key when none is given, as the older driver wrote it.
    record = {"event": "merged", "at": T1, "pr": pr}
    if changed is not UNSET:
        record["changed"] = changed
    return record


def closed(pr):
    return {"event": "closed", "at": T1, "pr": pr}


def red_park():
    return {
        "event": "park",
        "at": T1,
        "step": "Step A",
        "line": "park: the checks on #20 are still red after two fixes: tests",
        "pr": 20,
    }


def one_off_park():
    return {"event": "park", "at": T1, "step": "Step A", "line": "park: a one-off"}


def after_cost(lines):
    # The lines after the cost line; None when there is no cost line.
    found = [number for number, line in enumerate(lines) if line.startswith("cost: ")]
    return lines[found[0] + 1 :] if found else None


def opened(pr):
    # A container session that opened pull request pr. A merge without a change counts only with one.
    begun = start(f"s{pr}", "Step A", T1)
    begun["container"] = f"driver-s{pr}"
    return [begun, end(f"s{pr}", f"opened: #{pr} from `b{pr}`", 0.1, 0)]


class StatusTrialTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def status(self, state=None):
        gh = fake_gh(self.folder, issues=[])
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "status",
                "--project",
                self.project,
                "--state",
                state or self.state,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def write_log(self, records, state=None):
        state = state or self.state
        os.makedirs(state, exist_ok=True)
        Path(state, "run.jsonl").write_bytes(b"".join(encode(record) for record in records))

    def test_refused_lines(self):
        self.write_log(
            [
                start("s1", "Step A", T1),
                refused_end(
                    "s1",
                    [
                        {"tool": "Bash", "input": '{"command": "git push --force"}'},
                        {"tool": "Edit", "input": "{}"},
                    ],
                    2,
                ),
                start("s2", "Step B", T1),
                refused_end(
                    "s2", [{"tool": "Bash", "input": '{"command": "git push --force"}'}], 1
                ),
            ]
        )
        done = self.status()
        lines = done.stdout.splitlines()
        self.assertIn("refusals: 3", lines)
        at = lines.index("refusals: 3")
        self.assertEqual(
            lines[at : at + 3],
            ["refusals: 3", '  2 Bash: {"command": "git push --force"}', "  1 Edit: {}"],
        )
        self.assertEqual([line[:6] for line in lines[at + 3 : at + 4]], ["cost: "])
        self.assertEqual(done.returncode, 0)

        # An end line with no refused key adds to the count and to no line.
        plain = os.path.join(self.root, "plain")
        self.write_log([start("s1", "Step A", T1), end("s1", "opened: #20", 0.1, 2)], state=plain)
        done = self.status(state=plain)
        lines = done.stdout.splitlines()
        self.assertIn("refusals: 2", lines)
        at = lines.index("refusals: 2")
        self.assertEqual([line[:6] for line in lines[at + 1 : at + 2]], ["cost: "])
        self.assertEqual(done.returncode, 0)

        # Equal counts are ordered by their text.
        order = os.path.join(self.root, "order")
        self.write_log(
            [
                start("s1", "Step A", T1),
                refused_end(
                    "s1", [{"tool": "Edit", "input": "{}"}, {"tool": "Bash", "input": "{}"}], 2
                ),
            ],
            state=order,
        )
        done = self.status(state=order)
        lines = done.stdout.splitlines()
        self.assertIn("refusals: 2", lines)
        at = lines.index("refusals: 2")
        self.assertEqual(lines[at + 1 : at + 3], ["  1 Bash: {}", "  1 Edit: {}"])
        self.assertEqual(done.returncode, 0)

    def test_level_2_count(self):
        self.write_log(
            opened(1)
            + opened(2)
            + opened(3)
            + [merged(1, False), red_park(), merged(2, False), merged(3, False)]
        )
        done = self.status()
        self.assertEqual(after_cost(done.stdout.splitlines()), [LEVEL_2.format(2)])
        self.assertEqual(done.returncode, 0)

        empty = os.path.join(self.root, "empty")
        done = self.status(state=empty)
        self.assertEqual(done.stdout.splitlines()[-1], LEVEL_2.format(0))
        self.assertEqual(done.returncode, 0)

        # Other parks do not end the count.
        ones = os.path.join(self.root, "ones")
        self.write_log(
            opened(1)
            + opened(2)
            + opened(3)
            + [
                merged(1, False),
                one_off_park(),
                merged(2, False),
                one_off_park(),
                merged(3, False),
            ],
            state=ones,
        )
        done = self.status(state=ones)
        self.assertEqual(done.stdout.splitlines()[-1], LEVEL_2.format(3))
        self.assertEqual(done.returncode, 0)

    def test_count_ends(self):
        enders = [
            ("closed", closed(9)),
            ("merged None", merged(9, None)),
            ("merged no key", merged(9)),
            ("merged True", merged(9, True)),
        ]
        for number, (name, ender) in enumerate(enders):
            with self.subTest(ender=name):
                state = os.path.join(self.root, f"ender-{number}")
                self.write_log(
                    opened(1)
                    + opened(2)
                    + opened(3)
                    + [merged(1, False), merged(2, False), ender, merged(3, False)],
                    state=state,
                )
                done = self.status(state=state)
                self.assertEqual(done.stdout.splitlines()[-1], LEVEL_2.format(1))
                self.assertEqual(done.returncode, 0)

        newest = os.path.join(self.root, "newest")
        self.write_log(
            opened(1) + opened(2) + [merged(1, False), merged(2, False), merged(9, None)],
            state=newest,
        )
        done = self.status(state=newest)
        self.assertEqual(done.stdout.splitlines()[-1], LEVEL_2.format(0))
        self.assertEqual(done.returncode, 0)
