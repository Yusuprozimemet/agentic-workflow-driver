"""scripts/step-guard.py: after the maintainer's "merged", new work in the same session is refused
until a new session, /clear or /compact. The settings tests run the three hook commands through the
shell, in order, as Claude Code would: the prompt, the tool calls, the next session's start.

    python scripts/test_step_guard.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "step-guard.py")
SETTINGS = os.path.join(HERE, os.pardir, ".claude", "settings.json")
_spec = importlib.util.spec_from_file_location("step_guard", SCRIPT)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)


def tool(name, session="s1", **args):
    return {"session_id": session, "hook_event_name": "PreToolUse", "tool_name": name,
            "tool_use_id": "t1", "tool_input": args}


class MergedTests(unittest.TestCase):
    def test_short_merged_prompts_count(self):
        for prompt in ("merged", "Merged.", "merged #8", "#8 merged", "  MERGED!  ", "ok, merged it"):
            self.assertTrue(guard.is_merged(prompt), prompt)

    def test_messages_about_a_merge_do_not(self):
        for prompt in ("", "merge", "is it merged?", "not merged yet", "unmerged",
                       "again i said merged. you keep working in the same session, why?",
                       "after i said merged you kept working on another thing in the same session"):
            self.assertFalse(guard.is_merged(prompt), prompt)


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.marker = os.path.join(self.root, ".claude", "state", "step-guard.json")
        guard.set_marker("s1", self.marker)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def refused(self, data):
        return guard.refusal(data, self.marker, self.root)

    def test_subagents_are_refused(self):
        for name in ("Agent", "Task"):
            reason = self.refused(tool(name, subagent_type="plan-auditor"))
            self.assertIn("a subagent (plan-auditor)", reason or "", name)
            self.assertIn("new session", reason)

    def test_new_work_commands_are_refused(self):
        for command in ("git switch -c tooling/x", "git checkout -b day-02/spec", "git switch -q -c x",
                        "git branch day-02/x", 'git commit -F msg.txt', "git -c core.x=y commit -m x",
                        "git push -u origin x", "git merge main", "git stash push -- src",
                        "gh pr create --title t --body-file b", "gh pr merge 9", "gh issue create",
                        "cd repo && git commit -m x"):
            for name in ("Bash", "PowerShell"):
                self.assertIsNotNone(self.refused(tool(name, command=command)), f"{name}: {command}")

    def test_step_five_commands_pass(self):
        for command in ("git switch -q main && git pull -q --ff-only", "git log --oneline -1",
                        "gh run list --workflow evidence.yml --commit abc", "gh run view 1 --exit-status",
                        "gh run download 1 -D out", "python scripts/spec-drift.py --out spec-drift.json",
                        "python scripts/evidence.py specs/day-01-skeleton.md --ref main --json e.json",
                        "git status --short", "git branch --show-current", "gh pr view 8", "gh pr checks 8"):
            self.assertIsNone(self.refused(tool("Bash", command=command)), command)

    def test_edits_inside_the_repository_are_refused_and_outside_pass(self):
        inside = os.path.join(self.root, "specs", "day-02.md")
        outside = os.path.join(tempfile.gettempdir(), "scratch-note.md")
        for name in ("Edit", "Write"):
            self.assertIsNotNone(self.refused(tool(name, file_path=inside)), name)
            self.assertIsNone(self.refused(tool(name, file_path=outside)), name)

    def test_reads_pass(self):
        for name, args in (("Read", {"file_path": os.path.join(self.root, "plan.md")}),
                           ("Grep", {"pattern": "x"}), ("Glob", {"pattern": "*"})):
            self.assertIsNone(self.refused(tool(name, **args)), name)

    def test_another_session_and_no_marker_pass(self):
        self.assertIsNone(self.refused(tool("Agent", session="s2", subagent_type="plan-auditor")))
        guard.clear_marker(self.marker)
        self.assertIsNone(self.refused(tool("Agent", subagent_type="plan-auditor")))
        self.assertIsNone(self.refused(tool("Bash", command="git commit -m x")))


class SettingsTests(unittest.TestCase):
    """The hooks as configured, in the order a session meets them."""

    def setUp(self):
        self.project = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.project, "scripts"))
        shutil.copy(SCRIPT, os.path.join(self.project, "scripts", "step-guard.py"))
        with open(SETTINGS, encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]

        def command(event, mode):
            return next(h["command"] for e in hooks[event] for h in e["hooks"]
                        if "step-guard.py" in h["command"] and h["command"].endswith(" " + mode))

        self.prompt, self.pre, self.start = (command("UserPromptSubmit", "prompt"),
                                             command("PreToolUse", "pre"), command("SessionStart", "start"))
        self.matcher = next(e["matcher"] for e in hooks["PreToolUse"]
                            if any("step-guard.py" in h["command"] for h in e["hooks"]))

    def tearDown(self):
        shutil.rmtree(self.project, ignore_errors=True)

    def run_hook(self, command, data, project_dir=True):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        if project_dir:
            env["CLAUDE_PROJECT_DIR"] = self.project
        return subprocess.run(command, shell=True, cwd=self.project, env=env,
                              input=json.dumps(data), capture_output=True, text=True)

    def test_matcher_covers_every_guarded_tool(self):
        for name in ("Agent", "Task", "Edit", "Write", "NotebookEdit", "Bash", "PowerShell"):
            self.assertIn(name, self.matcher.split("|"))

    def test_merged_then_new_work_is_refused_until_a_new_session(self):
        auditor = tool("Agent", subagent_type="plan-auditor")
        self.assertEqual(self.run_hook(self.pre, auditor).returncode, 0, "refused before any merged")

        said = self.run_hook(self.prompt, {"session_id": "s1", "prompt": "merged"})
        self.assertEqual(said.returncode, 0)
        self.assertIn("new session", said.stdout)

        run = self.run_hook(self.pre, auditor)
        self.assertEqual(run.returncode, 2, run.stdout)
        self.assertIn("step-guard: refused a subagent (plan-auditor)", run.stderr)
        self.assertEqual(self.run_hook(self.pre, tool("Bash", command="gh run view 1 --exit-status")).returncode, 0)

        self.run_hook(self.start, {"session_id": "s1", "source": "resume"})
        self.assertEqual(self.run_hook(self.pre, auditor).returncode, 2, "resume cleared the marker")

        self.run_hook(self.start, {"session_id": "s1", "source": "compact"})
        self.assertEqual(self.run_hook(self.pre, auditor).returncode, 0, "/compact left the marker")

    def test_a_new_session_is_not_bound_by_the_old_marker(self):
        self.run_hook(self.prompt, {"session_id": "s1", "prompt": "merged #8"})
        self.assertEqual(self.run_hook(self.pre, tool("Agent", session="s2")).returncode, 0)

    def test_passes_without_project_dir(self):
        self.run_hook(self.prompt, {"session_id": "s1", "prompt": "merged"})
        run = self.run_hook(self.pre, tool("Agent"), project_dir=False)
        self.assertEqual((run.returncode, run.stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()
