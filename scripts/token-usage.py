"""Count the Claude Code tokens spent on this repository, per date, migration day, model and agent.

Reads the session transcripts Claude Code keeps on this machine (~/.claude/projects/<this
repository's path>, subagents included) and writes totals only, no prompt or reply text, to
docs/dashboard/token-usage.json (tokens, their cost at list prices, the part of it spent in replies that read
over 150k tokens, and the --tools counts per row), which scripts/spec-drift.py puts on the dashboard. The
transcripts live on the maintainer's machine, not in CI, so this runs locally and its output is
committed; the closing PR of each day refreshes it. Beside it, gates.json holds each gate's runs and the
tokens of the replies that ran it or read its result (gates()), refusals.json the guards' refusals,
sessions.json each transcript's stretches of work on this machine's clock (sessions()), for the
dashboard's tenth graph, one date on the clock, and counted.json the moment of this count, which
the page gives as what the other four are counted up to.

    python scripts/token-usage.py
    python scripts/token-usage.py --simulate   # what shorter sessions, capped tool output or a Haiku operator would save
    python scripts/token-usage.py --tools      # Bash results cap-output cut; Reads of files over 8,000 bytes
    python scripts/token-usage.py --tools --since 2026-11-01   # only the sessions that started since then
    python scripts/token-usage.py --compare    # main sessions' context per reply before and after the hooks landed
    python scripts/token-usage.py --compare --split 2026-11-03   # a second split; each side's replies per merged PR
    python scripts/token-usage.py --compare --repo ../bearing   # another repository's transcripts and merged PRs

A reply is counted once, from its last line: a transcript repeats a reply's usage on every content
block it streamed, and the usage is complete only on the last of those lines, so replies are keyed
by message and request id and the last line per key wins. The day is the branch the session was on
(day-17/track-d-... is Day 17); anything else (main, tooling/, docs/) has no day. Claude Code
deletes transcripts after cleanupPeriodDays (30 by default), so an entry already in the file is
never lowered: each count keeps the larger of the file's and the transcripts'.
"""
import argparse
import collections
import datetime
import glob
import json
import os
import re
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, os.pardir, "docs", "dashboard", "token-usage.json"))
FIELDS = ("input", "cache_write", "cache_read", "output", "replies")
TOOL_FIELDS = ("bash", "cut", "reads", "whole")
DAY_BRANCH = re.compile(r"^day-(\d+)/")
DATED = re.compile(r"-\d{8}$")
GAP = datetime.timedelta(minutes=5)  # sessions(): a stretch of work ends when nothing is written for longer
CUTS = (100_000, 200_000, 300_000)
PEAK = 150_000  # --compare: the share of sessions whose peak passed it, and of cost in replies above it
# A row's dollars spent in replies that read a context over PEAK, the part one session per step is meant to
# save (graph 8). A row counted before this field, whose transcripts are gone, has none: unknown, not zero.
PAST = f"cost_past_{PEAK // 1000}k"
CAPS = (2_000, 5_000)
RUN_MIN = datetime.timedelta(minutes=1)  # sessions(): a wait on a shell command this long or longer is drawn on the page
SHELLS = ("Bash", "PowerShell")
RUN_KINDS = (("tests", re.compile(r"unittest|test-parallel\.py|pytest|\btest_\w+\.py|seen-red\.py|break\.py|evidence\.py")),
             ("checks", re.compile(r"\bgh\s+(?:pr\s+checks|run\s+watch)\b")))
HOOKS_DAY =datetime.date(2026, 11, 2)  # read-guard.py and cap-output.py landed this day: --compare splits the replies at it
TOOL_LIMIT = 8_000  # read-guard.py's LIMIT: a whole Read of a file over it is refused
CUT_AT = 3_000  # cap-output.py's KEEP: its cut marker follows the head, this many characters in
# List prices in dollars per million tokens: input, cache write for 5 minutes (1.25x input) and for
# 1 hour (2x), cache read, output. From the claude-api skill's model table (cached 2026-10-06) and its
# prompt-caching notes; a cache read the skill gives no figure for is 0.1x input. A model not here costs 0.
PRICES_CHECKED = "2026-11-02"
PRICES = {
    "claude-fable-5-2": (8, 10, 16, 0.20, 40),  # this row checked 2026-11-10
    "claude-fable-5-1": (10, 12.5, 20, 0.25, 50),
    "claude-opus-5-5": (4, 5, 8, 0.20, 20),
    "claude-opus-5": (5, 6.25, 10, 0.50, 25),
    "claude-sonnet-5-5": (2, 2.5, 4, 0.20, 10),
    "claude-sonnet-5": (2, 2.5, 4, 0.20, 10),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    "claude-haiku-4-5": (1, 1.25, 2, 0.10, 5),
}
HAIKU_LONG = 100_000  # a Haiku 5.5 prompt past this many tokens costs five times as much ($0.50 / $2.50)
HAIKU_BRIEF = 20_000  # assumed: an operator subagent's system prompt, tools and brief
# A mechanical reply's Bash calls only run these scripts, read with gh or git, or filter what they print.
SCRIPTS = ("break.py", "seen-red.py", "pr-names.py", "check-links.py", "evidence.py", "spec-drift.py", "relabel.py", "token-usage.py")
GIT_READS = {"status", "log", "diff", "show", "fetch", "pull", "checkout", "switch", "branch", "rev-parse", "ls-files", "remote"}
GIT_DIFFS = {"diff", "show"}  # reviewing a diff is judgment: these, and log -p, are mechanical only with a stat flag
STATS = {"--stat", "--numstat", "--shortstat", "--name-only", "--name-status"}
GH_READS = {"pr view", "pr list", "pr checks", "run list", "run view", "run watch", "issue view", "issue list", "api"}
GH_WRITES = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"}
FILTERS = {"grep", "tail", "head", "wc", "sort", "uniq", "select-object", "select-string"}  # only after a |


def long_path(path):
    # Windows refuses a path past MAX_PATH (260 characters) unless it is absolute and starts with
    # \\?\: open() raises, and glob skips a folder past the limit without a word. glob keeps the
    # prefix on every path it yields, so prefixing the root reaches every open. UNC paths are left as they are.
    if os.name != "nt" or path.startswith("\\\\"):
        return path
    return "\\\\?\\" + os.path.abspath(path)


def transcripts(root, repo=None):
    # Claude Code names a project's folder after its path, every character but letters and digits
    # turned into "-"; a worktree of the repository, under its .claude/worktrees/, gets the same name
    # and "--". A sibling folder whose name only starts with this one's is another project.
    # repo is the repository's path (--repo); without it, this one.
    name = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(repo or os.path.join(HERE, os.pardir))).lower()
    for folder in glob.glob(os.path.join(long_path(root), "*")):
        base = os.path.basename(folder).lower()
        if base == name or base.startswith(name + "--"):
            yield from glob.glob(os.path.join(folder, "**", "*.jsonl"), recursive=True)


def agent(path):
    # A subagent's transcript, subagents/agent-<id>.jsonl, has its type in agent-<id>.meta.json beside it.
    meta = path[:-len(".jsonl")] + ".meta.json"
    if os.path.basename(os.path.dirname(path)) != "subagents":
        return "main"
    try:
        with open(meta, encoding="utf-8") as f:
            return json.load(f).get("agentType") or "unknown"
    except (OSError, ValueError):
        return "unknown"


def reply(entry):
    # The assistant message a line counts as a reply: it has usage and comes from a Claude model.
    msg = entry.get("message") or {}
    if entry.get("type") != "assistant" or not msg.get("usage") or not DATED.sub("", msg.get("model") or "").startswith("claude"):
        return None
    return msg


def row_key(entry, who):
    # The row a reply or a tool call counts toward: its local date, the day of its branch, its model and its agent.
    when = datetime.datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
    day = DAY_BRANCH.match(entry.get("gitBranch") or "")
    return (when.astimezone().date().isoformat(), int(day.group(1)) if day else None, DATED.sub("", entry["message"].get("model") or ""), who)


def tool_blocks(entry, calls, cut):
    # A line's tool calls by tool_use id, and each Bash result's cut test. A message spread over several
    # lines repeats its blocks: the last line wins, so a call counts once. A Bash result is cut by
    # cap-output.py when its text has the marker at CUT_AT. A request blob repeats earlier calls, so only a reply records one.
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return
    for b in content:
        if not isinstance(b, dict):
            continue
        if b.get("type") == "tool_use" and entry.get("type") == "assistant":
            calls[b.get("id")] = (b.get("name"), b.get("input") or {}, entry)
        elif b.get("type") == "tool_result" and calls.get(b.get("tool_use_id"), (None,))[0] == "Bash":
            cut[b.get("tool_use_id")] = tool_text(b.get("content")).find("\n[cut ") == CUT_AT


def read_size(name, args):
    # What a tool call adds to reads and whole: (1, whole) for a Read of a file over TOOL_LIMIT, else (0, 0).
    # A transcript keeps no size, so the file's size on disk now is read.
    if name != "Read" or size(args.get("file_path") or "") <= TOOL_LIMIT:
        return 0, 0
    return 1, int(not any(args.get(k) is not None for k in ("offset", "limit", "pages")))


def cost(model, usage):
    # A reply's list price in dollars. The usage splits its cache writes by lifetime; one with no split
    # is Claude Code's 1-hour write. Haiku 5.5's long-prompt price is per reply, so it is applied here.
    p = PRICES.get(DATED.sub("", model or ""))
    if p is None:
        return 0.0
    write, read = usage.get("cache_creation_input_tokens", 0), usage.get("cache_read_input_tokens", 0)
    hour = (usage.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", write)
    prompt = usage.get("input_tokens", 0) + write + read
    scale = 5 if p is PRICES["claude-haiku-5-5"] and prompt > HAIKU_LONG else 1
    return scale * (usage.get("input_tokens", 0) * p[0] + (write - hour) * p[1] + hour * p[2]
                    + read * p[3] + usage.get("output_tokens", 0) * p[4]) / 1e6


def count(files):
    # The usage is complete only on a reply's last line, so the last line per key overwrites the others.
    replies, totals = {}, collections.defaultdict(lambda: dict.fromkeys(FIELDS + TOOL_FIELDS + ("cost",), 0))
    for path in files:
        who = agent(path)
        calls, cut = {}, {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                tool_blocks(entry, calls, cut)
                msg = reply(entry)
                if msg is not None:
                    replies[(msg.get("id"), entry.get("requestId"))] = (who, entry)
        for tid, (name, args, entry) in calls.items():
            if reply(entry) is None:
                continue
            t = totals[row_key(entry, who)]
            if tid in cut:
                t["bash"] += 1
                t["cut"] += int(cut[tid])
            reads, whole = read_size(name, args)
            t["reads"] += reads
            t["whole"] += whole
    for who, entry in replies.values():
        usage = entry["message"]["usage"]
        t = totals[row_key(entry, who)]
        t["input"] += usage.get("input_tokens", 0)
        t["cache_write"] += usage.get("cache_creation_input_tokens", 0)
        t["cache_read"] += usage.get("cache_read_input_tokens", 0)
        t["output"] += usage.get("output_tokens", 0)
        t["replies"] += 1
        spent = cost(entry["message"].get("model"), usage)
        context = usage.get("input_tokens", 0) + usage.get("cache_creation_input_tokens", 0) + usage.get("cache_read_input_tokens", 0)
        t["cost"] += spent
        t[PAST] = t.get(PAST, 0) + (spent if context > PEAK else 0)
    return totals


# The gates (docs/dashboard/gates.json): an auditor's whole run, and in any session the scripts that run
# seen red, a break on purpose and the evidence replay, and a call a guard refused. A refusal's result
# starts with the hook's command, which names the guard's script.
GATE_SCRIPT = (("seen red", re.compile(r"\bseen-red\.py\b")), ("break on purpose", re.compile(r"\bbreak\.py\b")),
               ("evidence replay", re.compile(r"\b(?:close-)?evidence\.py\b")))
REFUSED = re.compile(r"PreToolUse:\w+ hook error: \[[^\n]*?\b(step-guard|read-guard|auditor-guard)\.py")
GATE_FIELDS = ("runs", "replies", "context", "output", "cost")


def gate_of_call(name, args):
    if name not in ("Bash", "PowerShell"):
        return None
    command = str(args.get("command") or "")
    return next((g for g, rx in GATE_SCRIPT if rx.search(command)), None)


def gates(files):
    """Per (date, day, gate): its runs, and the replies that made its call or read what the call
    returned, with their context, output and cost. Every reply of an auditor's run is the auditors'.
    A reply counts toward one gate: the first its own calls name, else the one whose result it reads."""
    rows = collections.defaultdict(lambda: dict.fromkeys(GATE_FIELDS, 0))
    for path in files:
        auditor = agent(path).endswith("-auditor")
        last, own, of_call, calls = {}, {}, {}, {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                content = (entry.get("message") or {}).get("content")
                blocks = [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []
                msg = reply(entry)
                if msg is not None:
                    key = (msg.get("id"), entry.get("requestId"))
                    last[key] = entry  # a key keeps the place of its first line, and its last line's usage
                    for b in (b for b in blocks if b.get("type") == "tool_use"):
                        of_call[b.get("id")] = key
                        g = gate_of_call(b.get("name"), b.get("input") or {})
                        if g:
                            calls[b.get("id")] = g
                            own.setdefault(key, g)
                elif entry.get("type") == "user":
                    for b in (b for b in blocks if b.get("type") == "tool_result" and b.get("tool_use_id") in of_call):
                        if REFUSED.match(tool_text(b.get("content"))):
                            calls[b["tool_use_id"]] = own[of_call[b["tool_use_id"]]] = "hooks"
        order = list(last)
        where = lambda key, g: row_key(last[key], None)[:2] + (g,)
        for i, key in enumerate(order):
            g = "auditors" if auditor else own.get(key) or (own.get(order[i - 1]) if i else None)
            if g:
                usage, t = last[key]["message"]["usage"], rows[where(key, g)]
                t["replies"] += 1
                t["context"] += sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
                t["output"] += usage.get("output_tokens", 0)
                t["cost"] += cost(last[key]["message"].get("model"), usage)
        for tid, g in ([] if auditor else calls.items()):
            rows[where(of_call[tid], g)]["runs"] += 1
        if auditor and order:
            rows[where(order[0], "auditors")]["runs"] += 1
    return rows


def run_kind(command):
    # What a shell command the session waited on was: its tests (a break, a seen-red run and a replay
    # run tests too), GitHub's checks on a pull request, or anything else.
    return next((kind for kind, pattern in RUN_KINDS if pattern.search(command)), "other")


def waited(runs):
    """The time a stretch spent waiting on shell commands, as [start, end, kind] pieces in order that
    never overlap: calls made in one reply run side by side, and a moment two of them share counts
    once, as the first kind in RUN_KINDS that was running."""
    order = [kind for kind, _ in RUN_KINDS] + ["other"]
    edges, pieces = sorted({t for start, end, _ in runs for t in (start, end)}), []
    for a, b in zip(edges, edges[1:]):
        on = [kind for start, end, kind in runs if start <= a and b <= end]
        if not on:
            continue
        kind = min(on, key=order.index)
        if pieces and pieces[-1][1] == a and pieces[-1][2] == kind:
            pieces[-1][1] = b
        else:
            pieces.append([a, b, kind])
    return pieces


def sessions(files):
    """Each transcript's stretches of work, for docs/dashboard/sessions.json: a stretch runs from one
    line's timestamp to the next while no gap is longer than GAP, and carries its agent, the day of
    its branch and its replies, counted once each. A tool's result is a line too, so a test suite that
    runs for four minutes keeps the stretch whole; one that runs for six does as well, since a shell
    command the session is waiting on is work and not a gap. `ran` is the seconds of the stretch spent
    waiting on such commands, by kind, and `runs` the waits of RUN_MIN or longer, which the page draws.
    A command sent to the background returns at once and is not counted. The stamps are written on this
    machine's clock, with its offset, so the page can show the maintainer's day and not the reader's."""
    rows = []
    for path in files:
        who, stamps, calls, runs = agent(path), [], {}, []
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    when = datetime.datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue
                msg = reply(entry)
                stamps.append((when, entry.get("gitBranch") or "", (msg.get("id"), entry.get("requestId")) if msg else None))
                content = (entry.get("message") or {}).get("content")
                for b in content if isinstance(content, list) else ():
                    if not isinstance(b, dict):
                        continue
                    args = b.get("input") or {}
                    if b.get("type") == "tool_use" and entry.get("type") == "assistant" and b.get("name") in SHELLS and not args.get("run_in_background"):
                        calls[b.get("id")] = (when, run_kind(str(args.get("command") or "")))
                    elif b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                        asked, kind = calls.pop(b.get("tool_use_id"))
                        if when > asked:
                            runs.append((asked, when, kind))
        long_runs = [(a, b) for a, b, _ in runs if b - a > GAP]
        stretches = []
        for when, branch, key in sorted(stamps, key=lambda s: s[0]):
            end = stretches[-1]["end"] if stretches else None
            if stretches and (when - end <= GAP or any(a <= end and when <= b for a, b in long_runs)):
                stretches[-1]["end"] = max(end, when)
            else:
                stretches.append(dict(start=when, end=when, branch=branch, replies=set()))
            if key:
                stretches[-1]["replies"].add(key)
        stamp = lambda t: t.astimezone().isoformat(timespec="seconds")
        for s in stretches:
            start, day = s["start"].astimezone(), DAY_BRANCH.match(s["branch"])
            row = {"date": start.date().isoformat(), "day": int(day.group(1)) if day else None, "agent": who,
                   "from": stamp(start), "to": stamp(s["end"]), "replies": len(s["replies"])}
            pieces = waited([r for r in runs if s["start"] <= r[0] and r[1] <= s["end"]])
            if pieces:
                ran = collections.Counter()
                for a, b, kind in pieces:
                    ran[kind] += (b - a).total_seconds()
                row["ran"] = {kind: round(seconds) for kind, seconds in sorted(ran.items()) if round(seconds)}
                row["runs"] = [[stamp(a), stamp(b), kind] for a, b, kind in pieces if b - a >= RUN_MIN]
            rows.append(row)
    return rows


def write_sessions(out, rows):
    """The stretches beside those already in out, as token-usage.json keeps its rows: a stretch is its
    agent and start, and the later end and the larger count win, since a session can go on after it
    was counted and Claude Code deletes old transcripts. What a stretch waited on is this count's. A
    stretch in out that this count did not make, and that lies inside one it did make for the same
    agent, is dropped: it was written before a long command joined its two halves."""
    kept = {}
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            kept = {(r["agent"], r["from"]): r for r in json.load(f)}
    made, at = {(r["agent"], r["from"]) for r in rows}, datetime.datetime.fromisoformat
    for r in rows:
        k = kept.setdefault((r["agent"], r["from"]), r)
        k["to"], k["replies"] = max(k["to"], r["to"]), max(k["replies"], r["replies"])
        k.update({f: r[f] for f in ("ran", "runs") if f in r})
    spans = [(agent, at(kept[agent, start]["from"]), at(kept[agent, start]["to"])) for agent, start in made]
    for key in [k for k in kept if k not in made]:
        a, b = at(kept[key]["from"]), at(kept[key]["to"])
        if any(agent == key[0] and start <= a and b <= end for agent, start, end in spans):
            del kept[key]
    if not kept:
        return
    out_rows = sorted(kept.values(), key=lambda r: (r["from"], r["agent"]))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, separators=(",", ":")) for r in out_rows) + "\n]\n")
    print(f"{out}: {len(out_rows)} stretches of work over {len({r['date'] for r in out_rows})} dates")


def contexts(path):
    # A session's replies in order: the context each read (every input token, cached or not),
    # whether a tool result came in since the reply before, its model, usage and timestamp. A sidechain line is a subagent's.
    replies, tool = {}, False
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            msg = entry.get("message") or {}
            if entry.get("isSidechain"):
                continue
            if entry.get("type") == "user" and isinstance(msg.get("content"), list):
                tool = tool or any(isinstance(b, dict) and b.get("type") == "tool_result" for b in msg["content"])
            elif entry.get("type") == "assistant" and msg.get("usage"):
                u = msg["usage"]
                key = (msg.get("id"), entry.get("requestId"))
                context = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
                tool = replies[key][1] if key in replies else tool
                replies[key] = (context, tool, msg.get("model"), u, entry.get("timestamp") or "")
                tool = False
    return list(replies.values())


def side():
    # prs stays None until per_pr() counts the side's merged pull requests. peaks: each session's largest
    # context on the side; above: the cost of its replies over PEAK; starts: each session's first context,
    # on the side of its first reply; start_cost: what re-reading only that start would cost every reply.
    return dict(contexts=[], days=set(), read=0, past=0, cost=0.0, prs=None, peaks={}, above=0.0, starts=[], start_cost=0.0)


def cache_read(model):
    # A model's cache-read list price per token; a model not in PRICES costs 0.
    return PRICES.get(DATED.sub("", model or ""), (0,) * 5)[3] / 1e6


def compare(files, splits=(HOOKS_DAY,)):
    # The main sessions' replies split by their local date at one or two sorted dates (HOOKS_DAY, and --split):
    # before the first, between them, from the last on. Per side: each reply's context, the
    # days it covers, its cost at list prices, and the context read after a session had passed the largest
    # CUTS size: a reply whose session had an earlier reply over it. A reply's cost is cost(), as in count().
    names = ("before", "between", "after") if len(splits) == 2 else ("before", "after")
    sides = {name: side() for name in names}
    # Per side also: each session's peak, the cost of replies over PEAK, each session's first context
    # (its start), and the start's cost if every reply had re-read only it, at the cache-read price.
    for path in files:
        passed, start = False, None
        for context, _, model, usage, when in contexts(path):
            if not when:
                continue
            day = datetime.datetime.fromisoformat(when.replace("Z", "+00:00")).astimezone().date()
            s = sides[names[sum(day >= d for d in splits)]]
            if start is None:
                start = context
                s["starts"].append(start)
            s["peaks"][path] = max(s["peaks"].get(path, 0), context)
            s["above"] += cost(model, usage) if context > PEAK else 0
            s["start_cost"] += start * cache_read(model)
            s["contexts"].append(context)
            s["days"].add(day)
            s["read"] += context
            s["past"] += context if passed else 0
            s["cost"] += cost(model, usage)
            passed = passed or context > CUTS[-1]
    return sides


def merges(log, merged):
    # The pull requests merged on main, read as spec-drift.py's snapshots() reads them. log is main's
    # first-parent history, one "date|parents|subject" line per commit: a merge commit names its pull
    # request; a single-parent commit whose subject ends "(#N)" is a squash only when N is in merged, the
    # numbers GitHub gives as MERGED. Returns (date, number) pairs.
    out = []
    for line in log:
        date, parents, subject = line.split("|", 2)
        m = re.match(r"Merge pull request #(\d+)", subject)
        if not m and len(parents.split()) == 1:
            m = re.search(r" \(#(\d+)\)$", subject)
            m = m if m and int(m.group(1)) in merged else None
        if m:
            out.append((datetime.date.fromisoformat(date), int(m.group(1))))
    return out


def merged_prs(repo=None):
    # merges() on the repository (--repo; without it, this one): main's history from git, with each commit's
    # local date as the replies have theirs, and the merged numbers from gh. Without gh, squashes are not counted, and it says so.
    root = repo or os.path.join(HERE, os.pardir)
    log = subprocess.run(["git", "-C", root, "log", "--first-parent", "main", "--format=%ad|%P|%s",
                          "--date=format-local:%Y-%m-%d"], capture_output=True, text=True, encoding="utf-8",
                         check=True).stdout.splitlines()
    try:
        gh = subprocess.run(["gh", "pr", "list", "--state", "merged", "--json", "number", "--limit", "1000"],
                            cwd=root, capture_output=True, text=True, encoding="utf-8", check=True)
        merged = {p["number"] for p in json.loads(gh.stdout)}
    except (OSError, subprocess.CalledProcessError, ValueError) as e:
        print(f"gh pr list failed, so squash merges are not counted: {e}", file=sys.stderr)
        merged = set()
    if len(merged) >= 1000:
        sys.exit("gh pr list returned its limit of 1000 merged pull requests: some are missing, raise it")
    return merges(log, merged)


def per_pr(sides, merged):
    # Each side's merged pull requests: those merged on main from the date of its first reply to its last's.
    for s in sides.values():
        if s["days"]:
            s["prs"] = sum(min(s["days"]) <= day <= max(s["days"]) for day, _ in merged)


def simulate(files):
    # Every reply re-reads the whole context, so what a block adds is read once by each later reply.
    # A context that falls by more than 30% was compacted: the session goes on as a new segment.
    # Cut: whenever the context passes the size, start again from the segment's first context.
    # Cap: a tool result that added more than the cap adds only the cap, to that reply and every later one.
    # Both are upper bounds: a fresh session re-reads what it needs, and a capped result may be read again.
    # Cut in dollars: each token no longer read saves the model's cache-read price, and each restart
    # costs one reply at the new session's starting context (the segment's first): written to the
    # 1-hour cache instead of read. No summary or hand-over is counted, and the Haiku long-prompt price is not applied.
    # Cap in dollars: each token the cap removes is a cache read in every reply that reads it, so it saves that
    # reply's cache-read price. A cap has no restart, so it adds no cost.
    s = dict(read=0, replies=0, sessions=0, cost=0.0, first="", last="",
             cut=dict.fromkeys(CUTS, 0), cut_cost=dict.fromkeys(CUTS, 0.0), cap=dict.fromkeys(CAPS, 0),
             cap_cost=dict.fromkeys(CAPS, 0.0))
    for path in files:
        segments = []
        for context, tool, model, usage, when in contexts(path):
            if not segments or context < 0.7 * segments[-1][-1][0]:
                segments.append([])
            segments[-1].append((context, tool, PRICES.get(DATED.sub("", model or ""), (0,) * 5)))
            s["cost"] += cost(model, usage)
            s["first"] = min(s["first"] or when, when)
            s["last"] = max(s["last"], when)
        s["sessions"] += bool(segments)
        for seg in segments:
            for i, (context, tool, _) in enumerate(seg):
                s["read"] += context
                s["replies"] += 1
                if tool and i:
                    for cap in CAPS:
                        excess = max(0, context - seg[i - 1][0] - cap)
                        s["cap"][cap] += excess * (len(seg) - i)
                        s["cap_cost"][cap] += excess * sum(p[3] for _, _, p in seg[i:]) / 1e6
            for cut in CUTS:
                saved = 0
                for context, _, p in seg:
                    if context - saved > cut:
                        saved = context - seg[0][0]
                        s["cut_cost"][cut] -= seg[0][0] * (p[2] - p[3]) / 1e6
                    s["cut"][cut] += saved
                    s["cut_cost"][cut] += saved * p[3] / 1e6
    return s


def turns(path):
    # A session's replies in order, as (model, usage, tool calls): the usage from a reply's last line,
    # its tool calls from every line it streamed. A sidechain line is a subagent's.
    replies = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            msg = entry.get("message") or {}
            if entry.get("isSidechain") or entry.get("type") != "assistant" or not msg.get("usage"):
                continue
            key = (msg.get("id"), entry.get("requestId"))
            calls = replies[key][2] if key in replies else []
            calls += [(b.get("name"), b.get("input") or {}) for b in msg.get("content") or []
                      if isinstance(b, dict) and b.get("type") == "tool_use"]
            replies[key] = (msg.get("model"), msg["usage"], calls)
    return list(replies.values())


def mechanical_command(command):
    # Every part of the command, split at && || ; | and newlines, with its redirection dropped, is cd or
    # echo, a script of ours, a gh or git read, or, after a |, a filter of what the part before printed.
    # A quoted string is one word, so a | in a grep pattern does not split it.
    masked = re.sub(r"'[^']*'|\"[^\"]*\"", "Q", command)
    for sep, part in zip([""] + re.findall(r"&&|\|\||[;|\n]", masked), re.split(r"&&|\|\||[;|\n]", masked)):
        words = [w for w in re.split(r"\d?>", part)[0].split() if not re.match(r"^\w+=", w)]
        if not words:
            continue
        head, flags = words[0].lower(), set(words)
        if head in ("cd", "echo") or head in FILTERS and sep == "|":
            continue
        if re.match(r"^py(thon3?)?(\.exe)?$", head):
            path = next((w for w in words[1:] if not w.startswith("-")), "")
            if os.path.basename(path.replace("\\", "/")) not in SCRIPTS:
                return False
        elif head == "git":
            rest = [w for i, w in enumerate(words[1:], 1) if not w.startswith("-") and words[i - 1] not in ("-C", "-c")]
            if not rest or rest[0] not in GIT_READS or (rest[0] == "branch" and {"-d", "-D", "-m", "-M"} & flags):
                return False
            if (rest[0] in GIT_DIFFS or rest[0] == "log" and "-p" in flags) and not STATS & flags:
                return False
        elif head == "gh":
            if " ".join(words[1:3]) not in GH_READS and words[1:2] != ["api"] or GH_WRITES & flags:
                return False
        else:
            return False
    return True


def mechanical(calls):
    # A reply is mechanical when it calls a tool and every call is a shell command mechanical_command passes.
    return bool(calls) and all(name in ("Bash", "PowerShell") and mechanical_command(args.get("command") or "")
                               for name, args in calls)


def route(files):
    # The main sessions' replies and their cost by class, and what moving the mechanical ones to a Haiku
    # operator subagent would change. Haiku: each run of them writes the brief once and reads it after,
    # writes what each reply took in since the reply before (its tool results), and the same output.
    # Opus: what a mechanical reply added to the context (its output and tool results, seen at the next
    # reply) is no longer read by the judgment replies after it, until a compaction (as in simulate).
    s = dict(replies=dict(mechanical=0, judgment=0), cost=dict(mechanical=0.0, judgment=0.0), haiku=0.0, unread=0.0)
    for path in files:
        before, run, seg = 0, False, []
        for model, usage, calls in turns(path):
            context = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            kind = "mechanical" if mechanical(calls) else "judgment"
            s["replies"][kind] += 1
            s["cost"][kind] += cost(model, usage)
            if seg and context < 0.7 * seg[-1][1]:
                seg = []
            if seg and seg[-1][0] == "mechanical":
                seg[-1][2] = max(0, context - seg[-1][1])
            if kind == "judgment":
                s["unread"] += sum(added for k, _, added in seg if k == "mechanical") * PRICES.get(DATED.sub("", model or ""), (0,) * 5)[3] / 1e6
            else:
                s["haiku"] += cost("claude-haiku-5-5", {
                    "cache_read_input_tokens": HAIKU_BRIEF if run else 0,
                    "cache_creation_input_tokens": (0 if run else HAIKU_BRIEF) + max(0, context - before),
                    "output_tokens": usage.get("output_tokens", 0)})
            seg.append([kind, context, 0])
            run, before = kind == "mechanical", context
    return s


def moment(text):
    # A date or a time for --since, read as local time when it has no zone.
    return datetime.datetime.fromisoformat(text).astimezone()


def started(path):
    # A transcript's first timestamp: when its session started, or a subagent's run began.
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                stamp = json.loads(line).get("timestamp")
            except (ValueError, AttributeError):
                continue
            if stamp:
                return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return None


def after(path, since):
    # Whether the transcript started at or after --since; without --since, every transcript counts.
    if since is None:
        return True
    start = started(path)
    return start is not None and start >= since


def size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def tool_text(content):
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def tools(files, since=None):
    s = dict(bash=0, cut=0, reads=0, whole=0)
    for path in files:
        if not after(path, since):
            continue
        calls, cut = {}, {}
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                tool_blocks(entry, calls, cut)
        s["bash"] += len(cut)
        s["cut"] += sum(cut.values())
        for name, args, _ in calls.values():
            reads, whole = read_size(name, args)
            s["reads"] += reads
            s["whole"] += whole
    return s


def report_tools(s):
    print(f"Bash results: {s['bash']:,}, cut by cap-output: {s['cut']:,} ({s['cut'] / max(s['bash'], 1):.1%})")
    print(f"Reads of files over {TOOL_LIMIT:,} bytes: {s['reads']:,}, whole {s['whole']:,}, ranged {s['reads'] - s['whole']:,}")


def report(s):
    print(f"main sessions:{s['sessions']}, {s['first'][:10]} to {s['last'][:10]}, {s['replies']:,} replies,"
          f" {s['read'] / 1e6:,.1f}M context tokens read, ${s['cost']:,.2f}")
    for cut, saved in s["cut"].items():
        d = s["cut_cost"][cut]
        sign = "-" if d >= 0 else "+"
        print(f"  fresh session whenever the context passes {cut // 1000}k: -{saved / max(s['read'], 1):.1%} tokens,"
              f" {sign}${abs(d):,.2f} ({sign}{abs(d) / max(s['cost'], 1e-9):.1%} of ${s['cost']:,.2f})")
    for cap, saved in s["cap"].items():
        d = s["cap_cost"][cap]
        print(f"  each tool result capped at {cap // 1000}k tokens: -{saved / max(s['read'], 1):.1%} tokens,"
              f" -${d:,.2f} (-{d / max(s['cost'], 1e-9):.1%} of ${s['cost']:,.2f})")
    print(f"  upper bounds, at the list prices checked {PRICES_CHECKED}: a fresh session re-reads what it needs, and"
          " each restart costs one reply writing its starting context; a capped result may be read again")


def report_compare(sides, splits=(HOOKS_DAY,)):
    labels = {"before": f"before {splits[0]}", "between": f"from {splits[0]}, before {splits[-1]}", "after": f"after {splits[-1]}"}
    for name, s in sides.items():
        n = len(s["contexts"])
        if not n:
            print(f"{labels[name]}: no replies")
            continue
        prs = ""
        if s["prs"] is not None:
            window = f"merged on main from {min(s['days'])} to {max(s['days'])}"
            prs = (f"; {s['prs']} pull requests {window}, {n / s['prs']:,.1f} replies per merged pull request" if s["prs"]
                   else f"; no pull request {window}")
        print(f"{labels[name]}: {n:,} replies on {len(s['days'])} days, median {statistics.median(s['contexts']):,.0f}"
              f" and mean {statistics.mean(s['contexts']):,.0f} context tokens per reply;"
              f" {s['past'] / max(s['read'], 1):.1%} of its context read after a session passed {CUTS[-1] // 1000}k;"
              f" ${s['cost']:,.2f} at the list prices checked {PRICES_CHECKED} (${s['cost'] / n:,.4f} per reply){prs}")
        peaks = list(s["peaks"].values())
        print(f"  {sum(p > PEAK for p in peaks) / max(len(peaks), 1):.1%} of {len(peaks)} sessions peaked past {PEAK // 1000}k;"
              f" {s['above'] / max(s['cost'], 1e-9):.1%} of its cost in replies above {PEAK // 1000}k")
        if s["starts"]:
            print(f"  median first reply (the session start) {statistics.median(s['starts']):,.0f} context tokens;"
                  f" re-read by every reply, the start alone costs ${s['start_cost']:,.2f}"
                  f" ({s['start_cost'] / max(s['cost'], 1e-9):.1%} of its cost) at the cache-read price")


def report_route(s):
    n, c = sum(s["replies"].values()), sum(s["cost"].values())
    for kind in ("mechanical", "judgment"):
        print(f"  {kind} replies: {s['replies'][kind]:,} ({s['replies'][kind] / max(n, 1):.1%}),"
              f" ${s['cost'][kind]:,.2f} ({s['cost'][kind] / max(c, 1e-9):.1%} of ${c:,.2f})")
    saved = s["cost"]["mechanical"] + s["unread"] - s["haiku"]
    print(f"  mechanical replies run in a Haiku subagent: -${saved:,.2f} (-{saved / max(c, 1e-9):.1%});"
          f" their own cost ${s['cost']['mechanical']:,.2f} and their output re-read later ${s['unread']:,.2f}, less Haiku ${s['haiku']:,.2f}")
    print(f"  upper bound, at the list prices checked {PRICES_CHECKED}: a {HAIKU_BRIEF // 1000}k Haiku brief per run of"
          " mechanical replies, each with the tool results it took in and the same output; no Opus reply hands the"
          " work over or reads a summary back, and the reply after a mechanical one keeps the same output")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--transcripts", default=os.path.join(os.path.expanduser("~"), ".claude", "projects"))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--simulate", action="store_true",
                    help="print what fresh sessions or capped tool results would have saved; write nothing")
    ap.add_argument("--tools", action="store_true",
                    help="print the Bash results cap-output cut and the Reads of a file over 8,000 bytes; write nothing")
    ap.add_argument("--compare", action="store_true",
                    help=f"print the main sessions' context per reply before and after {HOOKS_DAY}"
                         " and replies per merged pull request; write nothing")
    ap.add_argument("--split", type=datetime.date.fromisoformat, metavar="DATE",
                    help="with --compare: a second date to split the replies at, such as the day a change landed")
    ap.add_argument("--repo", metavar="PATH",
                    help="with --compare or --tools: read that repository's transcripts and merged pull requests, not this one's")
    ap.add_argument("--since", type=moment, metavar="DATE",
                    help="with --simulate or --tools: count only the sessions started at or after this date or time")
    args = ap.parse_args()
    if args.since and not (args.simulate or args.tools):
        ap.error("--since needs --simulate or --tools: token-usage.json is never written for part of the transcripts")
    if args.split and not args.compare:
        ap.error("--split needs --compare")
    if args.repo and not (args.compare or args.tools):
        ap.error("--repo needs --compare or --tools: token-usage.json counts this repository only")
    if args.compare:
        splits = tuple(sorted({HOOKS_DAY, args.split or HOOKS_DAY}))
        sides = compare([p for p in transcripts(args.transcripts, args.repo) if agent(p) == "main"], splits)
        per_pr(sides, merged_prs(args.repo))
        report_compare(sides, splits)
        return
    if args.tools:
        report_tools(tools(transcripts(args.transcripts, args.repo), args.since))
        return
    if args.simulate:
        paths = [p for p in transcripts(args.transcripts) if agent(p) == "main" and after(p, args.since)]
        report(simulate(paths))
        report_route(route(paths))
        return
    files = list(transcripts(args.transcripts))
    totals = count(files)
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            kept = json.load(f)
        for r in (r for r in kept if "agent" in r):
            t = totals[(r["date"], r["day"], r["model"], r["agent"])]
            for k in FIELDS:
                t[k] = max(t[k], r[k])
            for k in TOOL_FIELDS + ("cost",):
                t[k] = max(t[k], r.get(k, 0))
            if PAST in t or PAST in r:
                t[PAST] = max(t.get(PAST, 0), r.get(PAST, 0))
        # A row written before agents were counted holds every agent's tokens: what it has beyond
        # the agents counted for its date, day and model is kept as unknown, not given to one of them.
        for r in (r for r in kept if "agent" not in r):
            counted = [t for key, t in totals.items() if key[:3] == (r["date"], r["day"], r["model"])]
            t = totals[(r["date"], r["day"], r["model"], "unknown")]
            for k in FIELDS:
                t[k] += max(0, r[k] - sum(c[k] for c in counted))
    rows = [dict(date=d, day=n, model=m, agent=a, **{k: round(v, 4) if k in ("cost", PAST) else v for k, v in t.items()})
            for (d, n, m, a), t in totals.items()]
    rows.sort(key=lambda r: (r["date"], r["day"] or 0, r["model"], r["agent"]))
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n]\n")
    out = sum(r["output"] for r in rows)
    print(f"{args.out}: {len(rows)} rows, {rows[0]['date']} to {rows[-1]['date']}, {out:,} output tokens, "
          f"${sum(r['cost'] for r in rows):,.2f} at the list prices checked {PRICES_CHECKED}")
    write_refusals(os.path.join(os.path.dirname(args.out), "refusals.json"))
    write_gates(os.path.join(os.path.dirname(args.out), "gates.json"), gates(files))
    write_sessions(os.path.join(os.path.dirname(args.out), "sessions.json"), sessions(files))
    write_counted(os.path.join(os.path.dirname(args.out), "counted.json"))


def write_counted(out, now=None):
    """When this count was made, on this machine's clock with its offset: the four files beside it
    hold nothing later, and the page says so where it sets them against GitHub's pull requests."""
    at = (now or datetime.datetime.now()).astimezone().isoformat(timespec="seconds")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"at": at}) + "\n")
    print(f"{out}: counted up to {at}")


def write_gates(out, rows):
    """Each gate's runs and tokens per date and day, beside those already in out: the larger of each
    count is kept, as in token-usage.json, since Claude Code deletes old transcripts."""
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            for r in json.load(f):
                t = rows[(r["date"], r["day"], r["gate"])]
                for k in GATE_FIELDS:
                    t[k] = max(t[k], r.get(k, 0))
    if not rows:
        return
    out_rows = sorted((dict(date=d, day=n, gate=g, **dict(t, cost=round(t["cost"], 4))) for (d, n, g), t in rows.items()),
                      key=lambda r: (r["date"], r["day"] or 0, r["gate"]))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, separators=(",", ":")) for r in out_rows) + "\n]\n")
    print(f"{out}: {sum(r['runs'] for r in out_rows)} gate runs, ${sum(r['cost'] for r in out_rows):,.2f}")


def write_refusals(out, log=None):
    """The guards' refusals per date, from this machine's log, beside those already in out."""
    import refusal_log
    kept = []
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            kept = json.load(f)
    rows = refusal_log.merge(kept, refusal_log.counts(log))
    if not rows:
        return
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(json.dumps(r, separators=(",", ":")) for r in rows) + "\n]\n")
    print(f"{out}: {sum(r['refused'] for r in rows)} refusals over {len({r['date'] for r in rows})} dates")


if __name__ == "__main__":
    main()
