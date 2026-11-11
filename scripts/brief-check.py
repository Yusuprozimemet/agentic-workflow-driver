"""Check the paths and names a brief gives the implementer against the tree, before it is sent.

    python scripts/brief-check.py <brief.md>

A brief is written from memory, and three of them put a helper in the wrong file: D07.24 named
`tests/test_tree.py` for `commit_file`, which lives in `tests/test_dry_run.py`; D08.77 named
`tests/test_github.py` for helpers in `tests/test_status.py`. The implementer found each and
worked round it, after the fact. On each line of the brief, every backticked name that the
tracked Python files define (`def`, `class`, or a top-level assignment) must be defined in one
of the backticked files on that line, when the line names one that exists. Paths that do not
exist are listed, not refused: a brief names the files it creates.

Exits 1 when a name sits in the wrong file, with one line each; 0 otherwise, with the count.
"""
import os
import re
import subprocess
import sys

TICK = re.compile(r"`([^`\n]+)`")
PATH = re.compile(r"[\w./-]+\.(?:py|md|json|ya?ml|txt|toml|cfg|ini|sh)$|[\w.-]+/[\w./-]*$")
NAME = re.compile(r"([A-Za-z_]\w*)(?:\.\w+)*(?:\(\))?$")


def tracked():
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, encoding="utf-8", check=True)
    return set(out.stdout.split())


def sources(paths):
    found = {}
    for path in sorted(p for p in paths if p.endswith(".py")):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                found[path] = f.read()
        except OSError:
            pass
    return found


def defined(name, texts):
    pattern = re.compile(rf"^\s*(?:async\s+)?(?:def|class)\s+{name}\b|^{name}\s*[:=]", re.MULTILINE)
    return sorted(path for path, text in texts.items() if pattern.search(text))


def check(text, files, texts):
    """(problems, missing paths, names checked) for a brief's text."""
    problems, missing, checked = [], [], 0
    for n, line in enumerate(text.splitlines(), 1):
        ticks = [t.strip() for t in TICK.findall(line)]
        paths = [t.rstrip("/") for t in ticks if PATH.fullmatch(t)]
        missing += [f"line {n}: `{p}`" for p in paths if p not in files and not os.path.exists(p)]
        here = [p for p in paths if p in texts]
        if not here:
            continue
        for tick in ticks:
            match = NAME.fullmatch(tick)
            if tick in paths or not match:
                continue
            where = defined(match.group(1), texts)
            if not where:
                continue  # a name the brief asks for, not one it points at
            checked += 1
            if not set(where) & set(here):
                problems.append(f"line {n}: `{match.group(1)}` is defined in {', '.join(where)}, "
                                f"not in {', '.join(here)}")
    return problems, missing, checked


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__.split("\n\n")[1].strip(), file=sys.stderr)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    with open(argv[0], encoding="utf-8") as f:
        text = f.read()
    files = tracked()
    problems, missing, checked = check(text, files, sources(files))
    for line in missing:
        print(f"not in the tree (a file the brief creates?): {line}")
    for line in problems:
        print(line)
    if problems:
        print(f"brief-check: {len(problems)} of {checked} names point at the wrong file")
        return 1
    print(f"brief-check: {checked} names found where the brief says")
    return 0


if __name__ == "__main__":
    sys.exit(main())
