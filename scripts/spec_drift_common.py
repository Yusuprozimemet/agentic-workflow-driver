"""What every part of spec-drift.py reads: the patterns, the project file's values, and where the page and its data live."""

import json
import os
import re


TICK = re.compile(r"`([^`\n]+)`")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
WORDS = re.compile(r"[A-Za-z0-9_]+")
# A flag has a hyphen, which IDENT never takes: flags are counted apart, and stay out of the gap angle.
FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*(?![\w-])")
# A test's own name: test_ functions, Test classes and helpers named Test or Tests at the end.
TEST_NAME = re.compile(r"^test_|^Test|Tests?$")
COMMENT_LINE = re.compile(r"^\s*(//|/\*|\*|--|<!--|#(\s|!|$))")
COMMENT_TAIL = re.compile(r"/\*.*?\*/|\s(//|--|#)\s.*$")
CRITERION = re.compile(r"^- \[( |x)\]", re.M)
# A criterion's evidence: the PRs it cites and the tests it names (a class, or Class.member).
CITED_PR = re.compile(r"(?<![\w&])#(\d+)\b")
EVIDENCE_TEST = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:Test|IT|Tests))(?:\.([a-z][A-Za-z0-9_]*))?\b")
# A break on purpose, in one fixed line (specs/README.md): `broken: <what> → <what it reported>`,
# on its own line in a PR description or under a ticked criterion; `broken: none → <why>` says
# there was none. In the project the kit was copied from, it replaced three regexes over free text (#310), which
# read a break described in other words as none. Nothing earlier was asked for the line, so there
# it is read from PR #310 on (310 below): a PR before it, or a day none of whose PRs reaches it, is
# not measured. A day number would not do: Days 39-41 ran before Day 28. A project whose rules ask
# for the line from its first PR leaves it at 0, and the page names no PR.
BREAK_LINE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?broken:[ \t]*(\S[^\n]*?)[ \t]*(?:→|->)[ \t]*\S", re.M)
BREAK_NONE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?broken:[ \t]*(\S[^\n]*?)[ \t]*(?:→|->)[ \t]*(\S[^\n]*)", re.M)
# A command a criterion's evidence names, in backticks.
COMMAND = re.compile(r"`(?:git|python|diff|grep|bash) [^`]+`")
BREAK_LINE_FROM_PR = 0  # PROJECT: the first PR asked for the broken: line; 0 for all of them
# A test CI can skip: switched off, or run only on a condition. A condition on a system property
# is met when a workflow passes it as true (GatewayHarnessIT, -Dharness.gateway=true), so that
# test runs. A bare @Disabled stays skippable. In Python, a skip decorator or a skipTest() call.
SKIPPABLE = re.compile(r"@Disabled\b|@(?:Enabled|Disabled)If|@(?:unittest\.|pytest\.mark\.)skip|\.skipTest\(|(?<![\w.])(?:(?:it|test|describe)\.(?:skip|todo)|xit|xdescribe)\(")
PY_CLASS = re.compile(r"^[ \t]*class[ \t]+(\w+)", re.M)
ON_PROPERTY = re.compile(r'@EnabledIfSystemProperty\(\s*named\s*=\s*"([^"]+)"\s*,\s*matches\s*=\s*"true"\s*\)')
CI_PROPERTY = re.compile(r"-D([\w.-]+)=true\b")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "spec-drift.config.json")


def project_config(path=CONFIG_FILE):
    """The project file's values by the names this script reads them under; with no file, or no
    field, nothing is renamed, moved or a service's, Verify reads from the root, and no infra."""
    try:
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
    except FileNotFoundError:
        c = {}
    root = c.get("package_root", "")
    return dict(RENAMED={n: (old, new) for n, old, new in c.get("renamed", [])},
                MOVED=[tuple(m) for m in c.get("moved", [])],
                VERIFY_BASES=(*c.get("verify_bases", []), ""),
                SERVICE=c.get("services", {}),
                OWN_PACKAGE=re.compile(rf"(?:^|/)src/main/java/{re.escape(root.replace('.', '/'))}/([a-z]+)/"),
                IMPORT=re.compile(rf"^import\s+(?:static\s+)?{re.escape(root)}\.([a-z]+)\.", re.M),
                INFRA_WORKFLOW=c.get("infra_workflow", ""))


CONFIG = project_config()
# Tests that moved to a class of another stem, which moves() cannot tell by name: the PR that
# completed the move, and (old, new). Both kept every test method's name.
RENAMED = CONFIG["RENAMED"]
# A removal check: a grep a criterion says prints nothing ("`grep ...` returns nothing", "gives 0"),
# or a Verify line that echoes when it does (`grep ... || echo "clean"`).
GREP_SAYS_NOTHING = re.compile(r"`(grep [^`]+)`[^.]{0,40}?\b(?:returns|prints|finds|gives) (?:nothing|0)\b")
GREP_OR_ECHO = re.compile(r"^(grep\s.+?)\s*\|\|\s*echo\b", re.M)
# Directories that moved, by the merge that moved them, in order. A removal check's paths follow
# them: a grep of core/stock/src/ reads stock-service's code once the PR that moved it has merged.
MOVED = CONFIG["MOVED"]
# Where a Verify block's paths are read from, the root last: the one under which they find most.
VERIFY_BASES = CONFIG["VERIFY_BASES"]
# The most lines of one check's finds on main that the page lists.
FOUND_SHOWN = 10
# "Day 17", "Days 18-19", "Days 19, 21 and 24": the days a sentence names.
DAY_REF = re.compile(r"\bDays? (\d+)((?:\s*(?:[–-]|,|and|or)\s*\d+)*)")
# IDs (specs/README.md): criterion 3 of Day 28 is C28.3, and the
# first hand-off Day 28's Notes leave is H28.1. A spec picks a hand-off up by citing its ID.
CRITERION_ID = re.compile(r"^C(\d+)\.(\d+)\s+")
# A spec may cite a range of them, H34.1–H34.3 or H35.2-4: the second end may leave its day out.
HAND_OFF_LINE = re.compile(r"\s*- \**Hand-off\b")  # a Notes item that is one, not one citing it
HAND_OFF_RANGE = re.compile(r"\bH(\d+)\.(\d+)(?:\s*[–-]\s*(?:H\1\.)?(\d+)\b)?")
# A track a PR names ("**E1c** (next, ...)"), not a grep's -A3 or Day 14's A1. A criterion ID
# (C32.5) is not a track either, so a match followed by ".<digit>" is rejected.
# A track number is one digit, as in a day's track table, so neither C32.5 nor a day-numbered C32 is one.
TRACK_NAMED = re.compile(r"(?<![-\w])(?<!Day \d\d's )(?<!Day \d\d )([A-Z]\d[a-z]?|0[a-z])\b(?!\.\d)")
PHASE_READ = re.compile(r"^\*\*Read [^*\n]*end of Phase (\d+)\.\*\*.*?(?=^\*\*Read |^## |\Z)", re.M | re.S)
# Days plan.md's list names before their specs exist: an item "numbered from N", one "numbered after
# the last", and one numbered after the last that says "close-out".
PLATFORM = "platform"
CLEANUP = "cleanup"
CLOSEOUT = "close-out"
PLACEHOLDERS = (PLATFORM, CLEANUP, CLOSEOUT)
# The target services, by the monolith packages each one takes under the package root. A package
# no service takes is no service's, so depending on it crosses nothing.
SERVICE = CONFIG["SERVICE"]
OWN_PACKAGE = CONFIG["OWN_PACKAGE"]
IMPORT = CONFIG["IMPORT"]
INFRA_WORKFLOW = CONFIG["INFRA_WORKFLOW"]
FINISHED = ("done", "closed")
CHANCE_DRAWS = 1000
PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "docs", "dashboard")
# What the page cannot compute from git and GitHub: the sessions' counts and the driver's, from the
# maintainer's machine (scripts/publish-counts.py), and the re-check rows (recheck.yml). Machines push
# them to a branch of their own and nothing commits them to main: the page reads them there, and says
# so when the branch or a file on it is missing, rather than draw what an older copy held.
DATA_BRANCH = "dashboard-data"
DATA_FOLDER = "docs/dashboard"
DATA_FILES = ("token-usage.json", "refusals.json", "gates.json", "sessions.json", "counted.json",
              "driver-runs.json", "replay-history.json")
DATA = dict(commit=None, at=None, held=())  # data_branch() fills it; until then every file reads as absent
# What git said about each merge, kept between runs: every call cached here names commits only by
# SHA, so its output never changes. Keyed on this script's text too, so a change here starts over.
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, ".spec-drift-cache.json")
CACHE = {}
