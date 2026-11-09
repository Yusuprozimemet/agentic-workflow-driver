"""The token counts move with the replies and only then.

Each test writes a small transcript to a temporary folder and runs token-usage.py's count over it:
a reply is counted once, from its last streamed line, and the day comes from the branch.

    python scripts/test_token_usage.py
"""
import collections
import contextlib
import datetime
import importlib.util
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("token_usage", os.path.join(HERE, "token-usage.py"))
tu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tu)


def line(message_id="msg_1", request_id="req_1", output=3, branch="day-43/track-a2-x"):
    """One assistant line, as Claude Code writes it per streamed content block."""
    return json.dumps({
        "type": "assistant",
        "requestId": request_id,
        "timestamp": "2026-10-12T10:00:00Z",
        "gitBranch": branch,
        "message": {
            "id": message_id,
            "model": "claude-haiku-5-5-20260101",
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": 0,
                      "cache_read_input_tokens": 0, "output_tokens": output},
        },
    })


class CountTest(unittest.TestCase):
    def count(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return tu.count([path])

    def rows(self, totals):
        return [(key, dict(t)) for key, t in totals.items()]

    def test_a_reply_is_counted_from_its_last_line(self):
        totals = self.count([line(output=3), line(output=120)])
        rows = self.rows(totals)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["output"], 120)
        self.assertEqual(rows[0][1]["replies"], 1)

    def test_identical_repeats_count_once(self):
        totals = self.count([line(output=50), line(output=50), line(output=50)])
        rows = self.rows(totals)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["output"], 50)
        self.assertEqual(rows[0][1]["replies"], 1)

    def test_different_replies_add_up(self):
        totals = self.count([line(message_id="msg_1", output=10), line(message_id="msg_2", output=20)])
        rows = self.rows(totals)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["output"], 30)
        self.assertEqual(rows[0][1]["replies"], 2)

    def test_the_day_comes_from_the_branch(self):
        day43 = self.rows(self.count([line(branch="day-43/track-a2-x")]))
        self.assertEqual(day43[0][0][1], 43)
        main = self.rows(self.count([line(branch="main")]))
        self.assertIsNone(main[0][0][1])

    def test_a_cut_bash_result_and_a_whole_read_land_on_the_reply_row(self):
        cut = "a" * 3000 + "\n[cut 2000 chars; full output: x.txt; use Read with offset/limit or grep]\n"
        with tempfile.TemporaryDirectory() as folder:
            big = os.path.join(folder, "big.md")
            with open(big, "w", encoding="utf-8") as f:
                f.write("x" * 9_000)
            rows = self.rows(self.count([call("t1", "Bash"), result("t1", cut), call("t2", "Read", {"file_path": big}), result("t2", "x")]))
        self.assertEqual(len(rows), 1)
        self.assertEqual({k: rows[0][1][k] for k in tu.TOOL_FIELDS}, dict(bash=1, cut=1, reads=1, whole=1))

    def test_a_request_blob_repeating_a_bash_call_does_not_hide_it(self):
        cut = "a" * 3000 + "\n[cut 2000 chars; full output: x.txt; use Read with offset/limit or grep]\n"
        blob = json.dumps({"type": "api-request-blob", "hash": "h", "sessionId": "s",
                           "message": {"content": [{"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}]}})
        rows = self.rows(self.count([call("t1", "Bash"), result("t1", cut), blob]))
        self.assertEqual(len(rows), 1)
        self.assertEqual({k: rows[0][1][k] for k in tu.TOOL_FIELDS}, dict(bash=1, cut=1, reads=0, whole=0))

    def test_tool_calls_on_different_dates_go_to_two_rows(self):
        rows = self.rows(self.count([call("t1", "Bash", when="2026-11-05T10:00:00Z"), result("t1", "short"),
                                     call("t2", "Bash", when="2026-11-06T10:00:00Z"), result("t2", "short")]))
        self.assertEqual(sorted((key[0], t["bash"]) for key, t in rows), [("2026-11-05", 1), ("2026-11-06", 1)])


class TranscriptsTest(unittest.TestCase):
    """Only this repository's transcript folders are read: its own and its worktrees'."""

    def test_a_sibling_whose_name_starts_with_this_ones_is_not_read(self):
        root = tempfile.mkdtemp()
        name = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.join(HERE, os.pardir)))
        for folder in (name, name + "--claude-worktrees-a", name + "-pilot", name + "2", "other"):
            os.mkdir(os.path.join(root, folder))
            with open(os.path.join(root, folder, "s.jsonl"), "w", encoding="utf-8") as f:
                f.write(line())
        read = sorted(os.path.basename(os.path.dirname(p)) for p in tu.transcripts(root))
        self.assertEqual(read, [name, name + "--claude-worktrees-a"])


def native(path):
    # The test builds its files with its own \\?\ prefix, not the script's, so it runs on main's code too.
    return "\\\\?\\" + path if os.name == "nt" else path


class LongPathTest(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, native(self.root))
        name = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.join(HERE, os.pardir)))
        self.project = os.path.join(self.root, name)

    def write(self, path, text):
        os.makedirs(native(os.path.dirname(path)), exist_ok=True)
        with open(native(path), "w", encoding="utf-8") as f:
            f.write(text)

    def test_transcript_past_max_path_is_counted(self):
        # A subagent's transcript in a folder past 260 characters, beside a session at a short path.
        self.write(os.path.join(self.project, "short.jsonl"), line(output=3, branch="main") + "\n")
        folder = os.path.join(self.project, "s" * 200, "subagents")
        self.write(os.path.join(folder, "agent-" + "a" * 100 + ".jsonl"), line(message_id="msg_2", output=7, branch="main") + "\n")
        self.write(os.path.join(folder, "agent-" + "a" * 100 + ".meta.json"), '{"agentType": "implementer"}')
        self.assertGreater(len(folder), 260)
        totals = tu.count(tu.transcripts(self.root))
        self.assertEqual({who: t["output"] for (_, _, _, who), t in totals.items()},
                         {"main": 3, "implementer": 7})


class SessionsTest(unittest.TestCase):
    """sessions.json: a transcript's stretches of work, split where nothing was written for over five minutes."""

    @staticmethod
    def at(text, stamp, kind=None):
        entry = json.loads(text)
        entry["timestamp"] = stamp
        if kind:
            entry = {"type": kind, "timestamp": stamp, "gitBranch": entry["gitBranch"]}
        return json.dumps(entry)

    def sessions(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\nnot json\n")
            return tu.sessions([path])

    def test_a_stretch_ends_at_a_gap_longer_than_five_minutes_and_counts_each_reply_once(self):
        at, utc = self.at, datetime.timezone.utc
        rows = self.sessions([at(line(), "2026-10-12T10:00:00Z"), at(line(), "2026-10-12T10:00:30Z"),  # one reply, two streamed lines
                              at(line(), "2026-10-12T10:03:00Z", kind="user"),  # a tool result keeps the stretch going
                              at(line("msg_2", "req_2"), "2026-10-12T10:08:00Z"),
                              at(line("msg_3", "req_3"), "2026-10-12T10:13:01Z"),  # 5 min 1 s later: a new stretch
                              at(line(), "2026-10-12T10:14:00Z", kind="user")])
        self.assertEqual([(r["agent"], r["day"], r["replies"]) for r in rows], [("main", 43, 2), ("main", 43, 1)])
        instants = [(datetime.datetime.fromisoformat(r["from"]).astimezone(utc).isoformat(), datetime.datetime.fromisoformat(r["to"]).astimezone(utc).isoformat()) for r in rows]
        self.assertEqual(instants, [("2026-10-12T10:00:00+00:00", "2026-10-12T10:08:00+00:00"), ("2026-10-12T10:13:01+00:00", "2026-10-12T10:14:00+00:00")])
        # The stamps carry this machine's offset, and the date is the local one.
        local = datetime.datetime(2026, 10, 12, 10, 0, tzinfo=utc).astimezone()
        self.assertEqual((rows[0]["from"], rows[0]["date"]), (local.isoformat(timespec="seconds"), local.date().isoformat()))

    @staticmethod
    def call(tool_id, command, stamp, background=False):
        entry = json.loads(line(f"msg_{tool_id}", f"req_{tool_id}"))
        entry["timestamp"] = stamp
        entry["message"]["content"] = [{"type": "tool_use", "id": tool_id, "name": "Bash",
                                        "input": {"command": command, **({"run_in_background": True} if background else {})}}]
        return json.dumps(entry)

    @staticmethod
    def result(tool_id, stamp):
        return json.dumps({"type": "user", "timestamp": stamp, "gitBranch": "day-43/track-a2-x",
                           "message": {"content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}]}})

    def test_a_command_the_session_waits_on_for_over_five_minutes_keeps_the_stretch_whole(self):
        rows = self.sessions([self.call("t1", "python scripts/test-parallel.py", "2026-10-12T10:00:00Z"),
                              self.result("t1", "2026-10-12T10:06:00Z"),  # six minutes of tests: work, not a gap
                              self.at(line("msg_9", "req_9"), "2026-10-12T10:12:00Z")])  # six minutes of nothing: a gap
        utc = lambda s: datetime.datetime.fromisoformat(s).astimezone(datetime.timezone.utc).strftime("%H:%M")
        self.assertEqual([(utc(r["from"]), utc(r["to"]), r["replies"]) for r in rows], [("10:00", "10:06", 1), ("10:12", "10:12", 1)])
        self.assertEqual(rows[0]["ran"], {"tests": 360})
        self.assertEqual([(utc(a), utc(b), kind) for a, b, kind in rows[0]["runs"]], [("10:00", "10:06", "tests")])
        self.assertNotIn("ran", rows[1])

    def test_what_a_stretch_waited_on_is_counted_by_kind_and_a_shared_moment_once(self):
        call, result = self.call, self.result
        rows = self.sessions([call("t1", "gh pr checks 12 --watch", "2026-10-12T10:00:00Z"), result("t1", "2026-10-12T10:02:00Z"),
                              # two calls in one reply run side by side: the minute they share is tests, not both
                              call("t2", "python scripts/break.py --file a.py", "2026-10-12T10:03:00Z"), call("t3", "git status", "2026-10-12T10:03:00Z"),
                              result("t2", "2026-10-12T10:04:00Z"), result("t3", "2026-10-12T10:04:30Z"),
                              call("t4", "ruff check .", "2026-10-12T10:05:00Z", background=True), result("t4", "2026-10-12T10:07:00Z")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ran"], {"checks": 120, "other": 30, "tests": 60})
        # Only a wait of a minute or longer is drawn; the command sent to the background is no wait at all.
        self.assertEqual([kind for _, _, kind in rows[0]["runs"]], ["checks", "tests"])
        self.assertEqual([tu.run_kind(c) for c in ("python -m unittest discover -s tests", "python scripts/test_token_usage.py", "python scripts/seen-red.py -- x",
                                                   "python scripts/close-evidence.py --rehearse b", "gh run watch 5", "gh pr view 3", "ls")],
                         ["tests", "tests", "tests", "tests", "checks", "other", "other"])

    def test_a_subagents_stretch_carries_its_type(self):
        with tempfile.TemporaryDirectory() as folder:
            sub = os.path.join(folder, "subagents")
            os.makedirs(sub)
            with open(os.path.join(sub, "agent-1.jsonl"), "w", encoding="utf-8") as f:
                f.write(line(branch="main") + "\n")
            with open(os.path.join(sub, "agent-1.meta.json"), "w", encoding="utf-8") as f:
                f.write('{"agentType": "spec-auditor"}')
            rows = tu.sessions([os.path.join(sub, "agent-1.jsonl")])
        self.assertEqual([(r["agent"], r["day"], r["replies"]) for r in rows], [("spec-auditor", None, 1)])

    def test_stretches_are_kept_beside_the_written_ones_and_the_later_end_wins(self):
        row = lambda agent, start, end, n: {"date": start[:10], "day": 6, "agent": agent, "from": start, "to": end, "replies": n}
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, "sessions.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump([row("main", "2026-11-08T06:26:00+01:00", "2026-11-08T07:00:00+01:00", 20),  # the session went on after this was written
                           row("implementer", "2026-11-07T20:00:00+01:00", "2026-11-07T20:04:00+01:00", 3)], f)  # its transcript is gone
            tu.write_sessions(out, [row("main", "2026-11-08T06:26:00+01:00", "2026-11-08T07:30:00+01:00", 26),
                                    row("defect-rater", "2026-11-08T07:40:00+01:00", "2026-11-08T07:41:00+01:00", 1)])
            with open(out, encoding="utf-8") as f:
                rows = json.load(f)
        self.assertEqual([(r["agent"], r["to"], r["replies"]) for r in rows],
                         [("implementer", "2026-11-07T20:04:00+01:00", 3), ("main", "2026-11-08T07:30:00+01:00", 26), ("defect-rater", "2026-11-08T07:41:00+01:00", 1)])

    def test_a_written_stretch_inside_one_this_count_made_is_dropped_and_the_waits_are_this_counts(self):
        row = lambda agent, start, end, n, **more: {"date": start[:10], "day": 6, "agent": agent, "from": start, "to": end, "replies": n, **more}
        with tempfile.TemporaryDirectory() as folder:
            out = os.path.join(folder, "sessions.json")
            with open(out, "w", encoding="utf-8") as f:
                json.dump([row("main", "2026-11-08T06:00:00+01:00", "2026-11-08T06:10:00+01:00", 5),  # the two halves a six-minute
                           row("main", "2026-11-08T06:16:00+01:00", "2026-11-08T06:30:00+01:00", 7),  # test run used to leave
                           row("implementer", "2026-11-08T06:16:00+01:00", "2026-11-08T06:20:00+01:00", 2),  # another agent's: kept
                           row("main", "2026-11-08T09:00:00+01:00", "2026-11-08T09:05:00+01:00", 1)], f)  # outside: kept
            runs = [["2026-11-08T06:10:00+01:00", "2026-11-08T06:16:00+01:00", "tests"]]
            tu.write_sessions(out, [row("main", "2026-11-08T06:00:00+01:00", "2026-11-08T06:30:00+01:00", 12, ran={"tests": 360}, runs=runs)])
            with open(out, encoding="utf-8") as f:
                rows = json.load(f)
        self.assertEqual([(r["agent"], r["from"][11:16], r["to"][11:16], r["replies"]) for r in rows],
                         [("main", "06:00", "06:30", 12), ("implementer", "06:16", "06:20", 2), ("main", "09:00", "09:05", 1)])
        self.assertEqual((rows[0]["ran"], rows[0]["runs"]), ({"tests": 360}, runs))


class MergeTest(unittest.TestCase):
    """The rows already written are kept, those from before agents were counted among them."""

    def test_a_row_with_no_agent_keeps_its_count_as_unknown(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "token-usage.json")
            model = "claude-haiku-5-5"  # as rows store it, its date taken off
            legacy = dict(date="2026-10-12", day=43, model=model, input=10, cache_write=0, cache_read=0, output=100, replies=4)
            other = dict(legacy, date="2026-10-11", output=40, replies=2)
            with open(out, "w", encoding="utf-8") as f:
                json.dump([legacy, other], f)
            # Still on disk: one reply of the 2026-10-12 total, the main session's.
            project = os.path.join(root, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.join(HERE, os.pardir))))
            os.makedirs(project)
            with open(os.path.join(project, "s.jsonl"), "w", encoding="utf-8") as f:
                f.write(line(output=30) + "\n")
            run = subprocess.run([sys.executable, os.path.join(HERE, "token-usage.py"), "--transcripts",
                                  os.path.join(root, "projects"), "--out", out], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            with open(out, encoding="utf-8") as f:
                rows = {(r["date"], r["agent"]): (r["output"], r["replies"]) for r in json.load(f)}
        self.assertEqual(rows, {("2026-10-11", "unknown"): (40, 2),
                                ("2026-10-12", "main"): (30, 1), ("2026-10-12", "unknown"): (70, 3)})

    def test_a_kept_row_with_no_tool_fields_merges_and_takes_the_counted_ones(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "token-usage.json")
            kept = dict(date="2026-11-05", day=43, model="claude-haiku-5-5", agent="main", input=10, cache_write=0,
                        cache_read=0, output=100, replies=4)
            with open(out, "w", encoding="utf-8") as f:
                json.dump([kept], f)
            project = os.path.join(root, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.join(HERE, os.pardir))))
            os.makedirs(project)
            with open(os.path.join(project, "s.jsonl"), "w", encoding="utf-8") as f:
                f.write(call("t1", "Bash") + "\n" + result("t1", "short") + "\n")
            run = subprocess.run([sys.executable, os.path.join(HERE, "token-usage.py"), "--transcripts",
                                  os.path.join(root, "projects"), "--out", out], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            with open(out, encoding="utf-8") as f:
                rows = {(r["date"], r["agent"]): tuple(r[k] for k in ("bash", "cut", "reads", "whole", "output")) for r in json.load(f)}
        self.assertEqual(rows, {("2026-11-05", "main"): (1, 0, 0, 0, 100)})


def reply(message_id, context, sidechain=False, model=None, when=None):
    """One assistant line whose context (all input tokens, cached or not) is `context`."""
    entry = json.loads(line(message_id=message_id, request_id="req_" + message_id))
    entry["message"]["usage"] = {"input_tokens": 1, "cache_creation_input_tokens": 9,
                                 "cache_read_input_tokens": context - 10, "output_tokens": 5}
    entry["message"]["model"] = model or entry["message"]["model"]
    entry["timestamp"] = when or entry["timestamp"]
    entry["isSidechain"] = sidechain
    return json.dumps(entry)


def tool_result():
    return json.dumps({"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}})


class SimulateTest(unittest.TestCase):
    """What a fresh session past a size, or a cap on each tool result, would have saved."""

    def simulate(self, lines):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return tu.simulate([path])

    def test_a_fresh_session_restarts_from_the_first_replys_context(self):
        # 50k, 150k, 250k, the second streamed twice. Past 100k, the session restarts at 50k twice:
        # it reads 50k, 50k (saved 100k) and 50k + 100k = 150k, over 100k again, so 50k (saved 200k).
        s = self.simulate([reply("1", 50_000), reply("2", 150_000), reply("2", 150_000), reply("3", 250_000)])
        self.assertEqual((s["read"], s["replies"], s["sessions"]), (450_000, 3, 1))
        self.assertEqual(s["cut"], {100_000: 300_000, 200_000: 200_000, 300_000: 0})

    def test_a_tool_result_is_capped_for_every_reply_that_reads_it(self):
        # A tool result adds 10k and is read by two replies; a typed message adds 1k and is not capped.
        s = self.simulate([reply("1", 10_000), tool_result(), reply("2", 20_000), reply("3", 21_000)])
        self.assertEqual(s["cap"], {2_000: 16_000, 5_000: 10_000})

    def test_a_capped_result_saves_the_cache_read_price_of_each_reply_that_reads_it(self):
        # The tool result adds 10k, so the 2k cap removes 8k from each of the two replies that read it and
        # the 5k cap removes 5k from each. The first reply is Opus 5.5, cache read $0.20/M; the second is
        # Haiku 5.5, cache read $0.01/M. 2k: 8k x $0.20/M + 8k x $0.01/M = $0.00168. 5k: $0.00105.
        opus, haiku = "claude-opus-5-5", "claude-haiku-5-5"
        s = self.simulate([reply("1", 10_000, model=opus), tool_result(),
                           reply("2", 20_000, model=opus), reply("3", 21_000, model=haiku)])
        self.assertAlmostEqual(s["cap_cost"][2_000], 0.00168, places=9)
        self.assertAlmostEqual(s["cap_cost"][5_000], 0.00105, places=9)

    def test_a_compaction_starts_a_new_segment(self):
        # 250k, compacted to 40k, then 260k: the 260k restarts from 40k, not from 250k.
        s = self.simulate([reply("1", 250_000), reply("2", 40_000), reply("3", 260_000)])
        self.assertEqual(s["cut"][200_000], 220_000)

    def test_sidechain_lines_are_not_the_main_sessions(self):
        s = self.simulate([reply("1", 50_000), reply("2", 900_000, sidechain=True), reply("3", 60_000)])
        self.assertEqual((s["read"], s["replies"]), (110_000, 2))

    def test_a_fresh_session_saves_the_reads_and_pays_one_write_of_its_start(self):
        # Opus 5.5, as above: past 100k, 300k fewer tokens read at $0.20/M saves $0.06, and the two
        # restarts each write their 50k at $8/M instead of reading it: 2 x 50k x $7.80/M = $0.78.
        opus = "claude-opus-5-5"
        s = self.simulate([reply("1", 50_000, model=opus, when="2026-10-12T10:00:00Z"),
                           reply("2", 150_000, model=opus, when="2026-10-13T10:00:00Z"),
                           reply("3", 250_000, model=opus, when="2026-10-14T10:00:00Z")])
        # 449,970 read at $0.20, 3 input at $4, 27 written at $8, 15 output at $20, per million.
        self.assertAlmostEqual(s["cost"], 0.090522, places=9)
        self.assertAlmostEqual(s["cut_cost"][100_000], 0.06 - 0.78, places=9)
        self.assertAlmostEqual(s["cut_cost"][200_000], 0.04 - 0.39, places=9)
        self.assertAlmostEqual(s["cut_cost"][300_000], 0.0, places=9)
        self.assertEqual((s["first"][:10], s["last"][:10]), ("2026-10-12", "2026-10-14"))

    def test_the_report_prints_each_cuts_and_each_caps_dollar_saving_and_share(self):
        s = dict(read=1_000, replies=2, sessions=1, first="2026-10-12T10:00:00Z", last="2026-10-14T10:00:00Z",
                 cost=200.0, cut={100_000: 205}, cut_cost={100_000: 30.0}, cap={2_000: 250}, cap_cost={2_000: 20.0})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tu.report(s)
        self.assertIn("2026-10-12 to 2026-10-14", out.getvalue())
        self.assertIn("passes 100k: -20.5% tokens, -$30.00 (-15.0% of $200.00)", out.getvalue())
        self.assertIn("capped at 2k tokens: -25.0% tokens, -$20.00 (-10.0% of $200.00)", out.getvalue())


def call(tool_use_id, name, args=None, when="2026-11-05T10:00:00Z", branch="day-43/track-a2-x"):
    # A reply's line, as count() reads it: its usage and model, on a branch of a day.
    block = {"type": "tool_use", "id": tool_use_id, "name": name, "input": args or {}}
    return json.dumps({"type": "assistant", "timestamp": when, "gitBranch": branch, "requestId": "req_" + tool_use_id,
                       "message": {"id": "msg_" + tool_use_id, "model": "claude-haiku-5-5", "usage": {"output_tokens": 1},
                                   "content": [block]}})


def result(tool_use_id, text):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": text}
    return json.dumps({"type": "user", "timestamp": "2026-11-05T10:00:01Z", "message": {"content": [block]}})


class ToolsTest(unittest.TestCase):
    """Bash results cut by cap-output, and Reads of a file over 8,000 bytes, whole or ranged."""

    def tools(self, lines, since=None):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return tu.tools([path], since)

    def test_a_bash_result_with_the_cut_marker_at_3000_is_counted(self):
        cut = "a" * 3000 + "\n[cut 2000 chars; full output: x.txt; use Read with offset/limit or grep]\n" + "b" * 3000
        s = self.tools([call("t1", "Bash"), result("t1", cut), call("t2", "Bash"), result("t2", "short")])
        self.assertEqual((s["bash"], s["cut"]), (2, 1))

    def test_a_marker_elsewhere_in_a_result_is_not_a_cut(self):
        s = self.tools([call("t1", "Bash"), result("t1", "x" * 10 + "\n[cut 1 chars; full output: y]\n" + "z" * 3000)])
        self.assertEqual((s["bash"], s["cut"]), (1, 0))

    def test_a_read_of_a_file_over_8000_bytes_is_whole_or_ranged(self):
        with tempfile.TemporaryDirectory() as folder:
            big = os.path.join(folder, "big.md")
            small = os.path.join(folder, "small.md")
            with open(big, "w", encoding="utf-8") as f:
                f.write("x" * 9_000)
            with open(small, "w", encoding="utf-8") as f:
                f.write("x" * 100)
            path = os.path.join(folder, "session.jsonl")
            lines = [call("r1", "Read", {"file_path": big}), call("r2", "Read", {"file_path": big, "offset": 1, "limit": 5}),
                     call("r3", "Read", {"file_path": small})]
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            s = tu.tools([path])
        self.assertEqual((s["reads"], s["whole"]), (2, 1))

    def test_since_counts_only_the_sessions_started_after_it(self):
        with tempfile.TemporaryDirectory() as folder:
            before = os.path.join(folder, "before.jsonl")
            after = os.path.join(folder, "after.jsonl")
            with open(before, "w", encoding="utf-8") as f:
                f.write(json.dumps({"type": "user", "timestamp": "2026-10-20T10:00:00Z"}) + "\n" + call("b", "Bash") + "\n" + result("b", "short") + "\n")
            with open(after, "w", encoding="utf-8") as f:
                f.write(call("a", "Bash") + "\n" + result("a", "short") + "\n")
            s = tu.tools([before, after], since=tu.moment("2026-11-01"))
        self.assertEqual(s["bash"], 1)


REFUSAL = ("PreToolUse:Read hook error: [python -c \"import os,subprocess,sys;d=os.environ.get('CLAUDE_PROJECT_DIR');"
           "sys.exit(subprocess.call([sys.executable,os.path.join(d,'scripts','read-guard.py')]) if d else 0)\"]: refused")


class GatesTest(unittest.TestCase):
    """Each gate's runs, and the replies that ran it or read its result (gates.json)."""

    def gates(self, main, auditor=()):
        with tempfile.TemporaryDirectory() as folder:
            paths = [os.path.join(folder, "session.jsonl")]
            with open(paths[0], "w", encoding="utf-8") as f:
                f.write("\n".join(main) + "\n")
            if auditor:
                os.makedirs(os.path.join(folder, "subagents"))
                paths.append(os.path.join(folder, "subagents", "agent-1.jsonl"))
                with open(paths[1], "w", encoding="utf-8") as f:
                    f.write("\n".join(auditor) + "\n")
                with open(os.path.join(folder, "subagents", "agent-1.meta.json"), "w", encoding="utf-8") as f:
                    json.dump({"agentType": "spec-auditor"}, f)
            rows = tu.gates(paths)
        out = collections.defaultdict(lambda: [0, 0])
        for (_, day, gate), t in rows.items():
            self.assertEqual(day, 43)
            out[gate][0] += t["runs"]
            out[gate][1] += t["replies"]
        return {g: tuple(v) for g, v in out.items()}

    def test_a_gate_counts_the_reply_that_ran_it_and_the_one_that_read_its_result(self):
        self.assertEqual(self.gates([
            call("a", "Bash", {"command": "python scripts/break.py --file x"}), result("a", "broken: x"),
            call("b", "Read"), result("b", "text"),
            call("c", "Bash", {"command": "python scripts/test_break.py"}), result("c", "OK"),
            call("d", "Read"), result("d", REFUSAL),
            call("e", "Bash", {"command": "git status"}), result("e", "clean")]),
            {"break on purpose": (1, 2), "hooks": (1, 2)})

    def test_an_auditors_run_is_all_its_replies_and_its_calls_are_no_other_gate(self):
        self.assertEqual(self.gates([call("a", "Bash", {"command": "ls"})], [
            call("x", "Bash", {"command": "python scripts/seen-red.py -- pytest"}), result("x", "seen red"),
            call("y", "Read"), result("y", "text")]), {"auditors": (1, 2)})

    def test_each_script_names_its_gate(self):
        self.assertEqual([tu.gate_of_call("Bash", {"command": c}) for c in (
            "python scripts/seen-red.py -- x", "python scripts/close-evidence.py --rehearse b",
            "python scripts/evidence.py s.md", "python scripts/test_evidence.py", "python scripts/break.py")]
            + [tu.gate_of_call("Read", {"command": "break.py"})],
            ["seen red", "evidence replay", "evidence replay", None, "break on purpose", None])


class CostTest(unittest.TestCase):
    """Each kind of token at its model's list price."""

    def test_each_token_kind_is_priced_at_its_models_rate(self):
        # Opus 5.5: 1,000 input at $4, 1,000 5-minute writes at $5, 2,000 1-hour writes at $8,
        # 10,000 reads at $0.20 and 500 output at $20 per million: $0.037.
        entry = json.loads(line())
        entry["message"]["model"] = "claude-opus-5-5"
        entry["message"]["usage"] = {"input_tokens": 1_000, "cache_creation_input_tokens": 3_000,
                                     "cache_creation": {"ephemeral_5m_input_tokens": 1_000, "ephemeral_1h_input_tokens": 2_000},
                                     "cache_read_input_tokens": 10_000, "output_tokens": 500}
        totals = CountTest.count(self, [json.dumps(entry)])
        self.assertAlmostEqual(list(totals.values())[0]["cost"], 0.037, places=9)

    def test_a_write_with_no_split_is_a_one_hour_write(self):
        self.assertAlmostEqual(tu.cost("claude-opus-5-5", {"cache_creation_input_tokens": 1_000}), 0.008, places=9)

    def test_a_haiku_prompt_past_100k_costs_five_times(self):
        self.assertAlmostEqual(tu.cost("claude-haiku-5-5", {"cache_read_input_tokens": 100_000}), 0.001, places=9)
        self.assertAlmostEqual(tu.cost("claude-haiku-5-5", {"cache_read_input_tokens": 100_001}), 0.00500005, places=9)


def turn(message_id, context, calls=()):
    # A main-session Opus reply that read `context` from the cache, wrote 100 tokens and made these tool calls.
    blocks = [{"type": "tool_use", "id": message_id + str(i), "name": name, "input": args} for i, (name, args) in enumerate(calls)]
    return json.dumps({"type": "assistant", "requestId": "req_" + message_id, "timestamp": "2026-11-02T10:00:00Z",
                       "message": {"id": message_id, "model": "claude-opus-5-5", "content": blocks,
                                   "usage": {"cache_read_input_tokens": context, "output_tokens": 100}}})


class RouteTest(unittest.TestCase):
    """Which replies are mechanical, and what a Haiku operator subagent would take off the main sessions."""

    def test_only_our_scripts_and_gh_or_git_reads_are_mechanical(self):
        for command in ("python scripts/spec-drift.py --out spec-drift.json | tail -3",
                        "cd /c/repo && git checkout -q main && git pull -q && git log --oneline -1",
                        'gh pr checks 12 --watch > c.txt; gh pr checks 12 | grep -E "fail|pending"',
                        "PYTHONDONTWRITEBYTECODE=1 python scripts/break.py --file a.py --find x --replace y -- python t.py",
                        "git diff --stat main...HEAD", "gh api repos/o/r/pulls/3"):
            self.assertTrue(tu.mechanical([("Bash", {"command": command})]), command)
        for command in ("sed -n 1,40p specs/day-01.md", "grep -n def scripts/break.py", "git diff main -- a.py",
                        "git log -p -3", "gh pr diff 3", "gh pr create --body-file b.md", "git commit -F m.txt",
                        "gh api -X PATCH repos/o/r", "python scripts/test_break.py", "python -c 'print(1)'"):
            self.assertFalse(tu.mechanical([("Bash", {"command": command})]), command)
        self.assertFalse(tu.mechanical([]))
        self.assertFalse(tu.mechanical([("Bash", {"command": "git status"}), ("Edit", {})]))

    def test_mechanical_replies_move_to_haiku_with_the_context_they_added(self):
        # Edit at 50k ($0.012), spec-drift at 51k ($0.0122), a typed answer at 55k ($0.013). On Haiku the
        # mechanical reply writes the 20k brief and the 1k it took in ($0.0042) and its output ($0.00005);
        # the 4k it added is not read by the answer ($0.0008 at Opus's read price).
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "session.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join([turn("1", 50_000, [("Edit", {})]),
                                   turn("2", 51_000, [("Bash", {"command": "python scripts/spec-drift.py"})]),
                                   turn("3", 55_000)]) + "\n")
            s = tu.route([path])
        self.assertEqual(s["replies"], {"mechanical": 1, "judgment": 2})
        self.assertAlmostEqual(s["cost"]["mechanical"], 0.0122, places=9)
        self.assertAlmostEqual(s["cost"]["judgment"], 0.025, places=9)
        self.assertAlmostEqual(s["haiku"], 0.00425, places=9)
        self.assertAlmostEqual(s["unread"], 0.0008, places=9)


class CompareTest(unittest.TestCase):
    """The main sessions' replies before and after the day the hooks landed, each side at list prices."""

    def compare(self, *sessions, splits=None):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for i, lines in enumerate(sessions):
                paths.append(os.path.join(folder, f"session{i}.jsonl"))
                with open(paths[-1], "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            return tu.compare(paths, splits) if splits else tu.compare(paths)

    def test_replies_are_split_at_the_day_by_their_local_date(self):
        # Noon UTC keeps each reply on its date in every time zone from UTC-11 to UTC+11.
        s = self.compare([reply("1", 50_000, when="2026-11-01T12:00:00Z"), reply("2", 60_000, when="2026-11-02T12:00:00Z"),
                          reply("3", 70_000, when="2026-11-03T12:00:00Z")])
        self.assertEqual(s["before"]["contexts"], [50_000])
        self.assertEqual(s["after"]["contexts"], [60_000, 70_000])
        self.assertEqual(s["after"]["days"], {datetime.date(2026, 11, 2), datetime.date(2026, 11, 3)})

    def test_context_read_after_a_session_passed_300k_is_the_share_past_it(self):
        # One session: 150k, 350k, 400k. Only the 400k reply follows a reply over 300k, so 400k of its 900k
        # is past it. A second session reads 320k, which is the first reply of its session: nothing of it is past.
        before = "2026-11-01T12:00:00Z"
        s = self.compare([reply("1", 150_000, when=before), reply("2", 350_000, when=before), reply("3", 400_000, when=before)],
                         [reply("4", 320_000, when=before)])
        self.assertEqual(s["before"]["read"], 1_220_000)
        self.assertEqual(s["before"]["past"], 400_000)

    def test_each_reply_is_priced_at_its_models_list_price(self):
        # Opus 5.5 at 50k: 1 input at $4, 9 writes at $8 (no 5-minute split, so the 1-hour write), 49,990 reads at
        # $0.20 and 5 output at $20 per million: $0.010174.
        s = self.compare([reply("1", 50_000, model="claude-opus-5-5", when="2026-11-01T12:00:00Z")])
        self.assertAlmostEqual(s["before"]["cost"], 0.010174, places=9)

    def test_the_report_prints_each_side_and_says_when_a_side_is_empty(self):
        s = {"before": tu.side(), "after": tu.side()}
        s["before"].update(contexts=[100_000, 200_000, 600_000], days={datetime.date(2026, 11, 1)}, read=900_000, past=0, cost=1.5)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tu.report_compare(s)
        self.assertIn("before 2026-11-02: 3 replies on 1 days, median 200,000 and mean 300,000 context tokens per reply;"
                      " 0.0% of its context read after a session passed 300k; $1.50 at the list prices checked 2026-11-02"
                      " ($0.5000 per reply)", out.getvalue())
        self.assertIn("after 2026-11-02: no replies", out.getvalue())

    def test_a_second_split_puts_the_replies_between_the_two_dates_on_a_side_of_their_own(self):
        s = self.compare([reply("1", 50_000, when="2026-11-01T12:00:00Z"), reply("2", 60_000, when="2026-11-02T12:00:00Z"),
                          reply("3", 70_000, when="2026-11-03T12:00:00Z"), reply("4", 80_000, when="2026-11-04T12:00:00Z")],
                         splits=(datetime.date(2026, 11, 2), datetime.date(2026, 11, 3)))
        self.assertEqual({n: s[n]["contexts"] for n in s},
                         {"before": [50_000], "between": [60_000], "after": [70_000, 80_000]})

    def test_merged_pull_requests_are_merge_commits_and_squashes_github_says_merged(self):
        # #85 a merge commit; #86 a squash GitHub gives as merged; #87 a subject ending (#87) on a PR not merged;
        # #88 "(#88)" on a merge commit with two parents, not a squash; a commit with no PR.
        log = ["2026-11-03|a b|Merge pull request #85 from someone/specs/ladder",
               "2026-11-03|c|Count replies per PR (#86)",
               "2026-11-04|d|Revert a thing (#87)",
               "2026-11-04|e f|Merge branch main (#88)",
               "2026-11-04|g|Fix a typo"]
        self.assertEqual(tu.merges(log, {86, 88}), [(datetime.date(2026, 11, 3), 85), (datetime.date(2026, 11, 3), 86)])

    def test_each_side_counts_the_pull_requests_merged_from_its_first_reply_to_its_last(self):
        s = {"before": tu.side(), "after": tu.side()}
        s["before"]["days"] = {datetime.date(2026, 11, 1), datetime.date(2026, 11, 2)}
        merged = [(datetime.date(2026, 10, 31), 1), (datetime.date(2026, 11, 1), 2), (datetime.date(2026, 11, 2), 3),
                  (datetime.date(2026, 11, 3), 4)]
        tu.per_pr(s, merged)
        self.assertEqual(s["before"]["prs"], 2)
        self.assertIsNone(s["after"]["prs"])

    def test_the_report_prints_replies_per_merged_pull_request_and_the_split_dates(self):
        splits = (datetime.date(2026, 11, 2), datetime.date(2026, 11, 3))
        s = {"before": tu.side(), "between": tu.side(), "after": tu.side()}
        s["between"].update(contexts=[100_000] * 9, days={datetime.date(2026, 11, 2)}, read=900_000, cost=0.9, prs=2)
        s["after"].update(contexts=[100_000], days={datetime.date(2026, 11, 3)}, read=100_000, cost=0.1, prs=0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tu.report_compare(s, splits)
        self.assertIn("before 2026-11-02: no replies", out.getvalue())
        self.assertIn("from 2026-11-02, before 2026-11-03: 9 replies on 1 days,", out.getvalue())
        self.assertIn("($0.1000 per reply); 2 pull requests merged on main from 2026-11-02 to 2026-11-02,"
                      " 4.5 replies per merged pull request", out.getvalue())
        self.assertIn("after 2026-11-03: 1 replies on 1 days,", out.getvalue())
        self.assertIn("; no pull request merged on main from 2026-11-03 to 2026-11-03", out.getvalue())

    def test_each_side_counts_sessions_that_peaked_past_150k_and_the_cost_above_it(self):
        # Two sessions: one peaks at 200k, one at 120k. Only the 200k reply costs above 150k: Opus 5.5 at 200k is
        # 1 input at $4, 9 writes at $8, 199,990 reads at $0.20 and 5 output at $20 per million.
        opus, before = "claude-opus-5-5", "2026-11-01T12:00:00Z"
        s = self.compare([reply("1", 100_000, model=opus, when=before), reply("2", 200_000, model=opus, when=before)],
                         [reply("3", 120_000, model=opus, when=before)])["before"]
        self.assertEqual(sorted(s["peaks"].values()), [120_000, 200_000])
        self.assertAlmostEqual(s["above"], (4 + 9 * 8 + 199_990 * 0.20 + 5 * 20) / 1e6, places=9)

    def test_each_session_start_is_its_first_reply_and_every_reply_rereads_it_at_the_cache_read_price(self):
        # One session of three Opus 5.5 replies starting at 40k: re-reading only the start costs 3 x 40k at $0.20 per million.
        opus, before = "claude-opus-5-5", "2026-11-01T12:00:00Z"
        s = self.compare([reply("1", 40_000, model=opus, when=before), reply("2", 60_000, model=opus, when=before),
                          reply("3", 80_000, model=opus, when=before)], [reply("4", 30_000, model=opus, when=before)])["before"]
        self.assertEqual(sorted(s["starts"]), [30_000, 40_000])
        self.assertAlmostEqual(s["start_cost"], (3 * 40_000 + 30_000) * 0.20 / 1e6, places=9)

    def test_the_report_prints_the_peaks_the_cost_above_150k_and_the_session_start(self):
        s = {"before": tu.side(), "after": tu.side()}
        s["before"].update(contexts=[100_000, 200_000, 120_000], days={datetime.date(2026, 11, 1)}, read=420_000, cost=2.0,
                           peaks={"a": 200_000, "b": 120_000, "c": 90_000, "d": 151_000}, above=0.5,
                           starts=[40_000, 50_000, 60_000], start_cost=0.25)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tu.report_compare(s)
        self.assertIn("  50.0% of 4 sessions peaked past 150k; 25.0% of its cost in replies above 150k\n", out.getvalue())
        self.assertIn("  median first reply (the session start) 50,000 context tokens; re-read by every reply, the start"
                      " alone costs $0.25 (12.5% of its cost) at the cache-read price\n", out.getvalue())


class RepoTest(unittest.TestCase):
    """--repo reads another repository's transcript folder, and only with --compare or --tools."""

    def test_the_repo_given_names_the_folder_read(self):
        root = tempfile.mkdtemp()
        other = os.path.join(root, "elsewhere", "bearing")
        name = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(other))
        this = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(os.path.join(HERE, os.pardir)))
        for folder in (name, name + "--claude-worktrees-a", name + "-pilot", this):
            os.mkdir(os.path.join(root, folder))
            with open(os.path.join(root, folder, "s.jsonl"), "w", encoding="utf-8") as f:
                f.write(line())
        read = sorted(os.path.basename(os.path.dirname(p)) for p in tu.transcripts(root, other))
        self.assertEqual(read, [name, name + "--claude-worktrees-a"])

    def test_repo_without_compare_or_tools_is_refused_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "token-usage.json")
            run = subprocess.run([sys.executable, os.path.join(HERE, "token-usage.py"), "--transcripts", root,
                                  "--out", out, "--repo", root], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertIn("--repo needs --compare or --tools", run.stderr)
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
