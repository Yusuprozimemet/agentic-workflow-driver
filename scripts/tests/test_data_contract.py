"""The data contract (scripts/pipeline/contract.json): each key of spec-drift.json, the function that makes it, the
views of scripts/pipeline/ that read it, and the functions of docs/dashboard/dashboard.js that draw it.

Each of the three is read here from the code itself, so a key added, dropped, read or drawn without the contract
saying so fails the test that names it. A key's `what` and `graph` are words for a reader and are not checked
against the drawing: only that they are there.
"""

import ast
import json
import os
import re
import sys
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import pipeline  # noqa: E402

ROOT = os.path.join(SCRIPTS, os.pardir)
CONTRACT = os.path.join(SCRIPTS, "pipeline", "contract.json")
DRIFT = os.path.join(SCRIPTS, "spec-drift.py")
PAGE_JS = os.path.join(ROOT, "docs", "dashboard", "dashboard.js")
# The folders whose modules read the data spec-drift.py has gathered: a view, the score, the page's build.
READERS = ("counts", "build")
# The name a view gives the data it is handed, as its first parameter.
DATA_NAMES = ("d", "real", "data")
FIELDS = ["what", "made_by", "read_by", "drawn_by", "graph"]


def contract():
    with open(CONTRACT, encoding="utf-8") as f:
        return json.load(f)


def parsed(path):
    with open(path, encoding="utf-8") as f:
        return ast.parse(f.read())


def written():
    """{key: the expression spec-drift.py's main() writes under it}, and main() itself: the keywords of the
    dict(...) it names `real`, and each real["key"] = ... after it."""
    main = next(n for n in parsed(DRIFT).body if isinstance(n, ast.FunctionDef) and n.name == "main")
    keys = {}
    for node in ast.walk(main):
        if isinstance(node, ast.Assign):
            for target, value in _pairs(node):
                if isinstance(target, ast.Name) and target.id == "real" and isinstance(value, ast.Call):
                    keys.update({k.arg: k.value for k in value.keywords})
                if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                        and target.value.id == "real"):
                    keys[target.slice.value] = value
    return keys, main


def _pairs(node):
    """(target, value) for an assignment, a tuple on both sides taken pair by pair."""
    for target in node.targets:
        if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple):
            yield from zip(target.elts, node.value.elts)
        else:
            yield target, node.value


def calls_behind(value, main):
    """The names of the functions called in `value`, and in the assignment of each name `value` reads but `real`."""
    made = {}
    for node in ast.walk(main):
        if isinstance(node, (ast.Assign, ast.With)):
            pairs = _pairs(node) if isinstance(node, ast.Assign) else []
            for target, val in pairs:
                names = [t.id for t in ast.walk(target) if isinstance(t, ast.Name)]
                for name in names:
                    made.setdefault(name, set()).update(_called(val))
    found = set(_called(value))
    # `real` is everything gathered so far: a view handed it is made by the view, not by what made the rest
    for name in {n.id for n in ast.walk(value) if isinstance(n, ast.Name)} - {"real"}:
        found |= made.get(name, set())
    return found


def _called(node):
    return {c.func.id for c in ast.walk(node) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}


def readers():
    """{key: the modules of scripts/pipeline/counts and build whose functions read it from the data they are
    handed}: d["key"] or d.get("key"), d being the function's first parameter."""
    found = {}
    for folder in READERS:
        here = os.path.join(SCRIPTS, "pipeline", folder)
        for name in sorted(os.listdir(here)):
            if not name.endswith(".py"):
                continue
            for fn in ast.walk(parsed(os.path.join(here, name))):
                if not isinstance(fn, ast.FunctionDef) or not fn.args.args:
                    continue
                first = fn.args.args[0].arg
                if first not in DATA_NAMES:
                    continue
                for key in _keys_read(fn, first):
                    found.setdefault(key, set()).add(name[:-3])
    return found


def _keys_read(fn, name):
    for node in ast.walk(fn):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == name
                and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)):
            yield node.slice.value
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == name and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            yield node.args[0].value


def drawers():
    """{key: the functions of dashboard.js that read DATA.key}: a line counts in the last function declared above
    it at the file's top level or one level in (model()'s graphs, as `  function prfGraph() {`)."""
    found, fn = {}, None
    with open(PAGE_JS, encoding="utf-8") as f:
        for line in f:
            top = re.match(r"(?:  )?(?:async\s+)?function\s+(\w+)", line)
            if top:
                fn = top.group(1)
            for a, b in re.findall(r"\bDATA\.(\w+)|\bDATA\[\"(\w+)\"\]", line):
                found.setdefault(a or b, set()).add(fn)
    return found


def defines(made_by):
    """Whether "module:function" names a function its module defines (spec-drift for the command itself)."""
    module, _, function = made_by.partition(":")
    path = DRIFT if module == "spec-drift" else pipeline.path(module + ".py")
    return any(isinstance(n, ast.FunctionDef) and n.name == function for n in parsed(path).body)


class DataContractTest(unittest.TestCase):
    def test_every_key_written_is_in_the_contract_and_no_other(self):
        keys, _ = written()
        # (in the data and not the contract, in the contract and not the data)
        self.assertEqual((sorted(set(keys) - set(contract())), sorted(set(contract()) - set(keys))), ([], []))

    def test_each_entry_has_its_fields(self):
        for key, entry in contract().items():
            self.assertEqual(list(entry), FIELDS, key)
            self.assertTrue(entry["what"].strip() and entry["graph"].strip(), key)

    def test_each_key_is_made_by_the_function_it_names(self):
        keys, main = written()
        for key, entry in contract().items():
            module, _, function = entry["made_by"].partition(":")
            self.assertTrue(defines(entry["made_by"]), f"{key}: {entry['made_by']} is not defined")
            # main() builds a dict of its own from what it has gathered (now, meta)
            called = "dict" if entry["made_by"] == "spec-drift:main" else function
            self.assertIn(called, calls_behind(keys[key], main), key)

    def test_each_key_is_read_by_the_views_it_names(self):
        read = readers()
        # the keys whose readers the contract names wrong
        self.assertEqual([k for k, e in contract().items() if e["read_by"] != sorted(read.get(k, ()))], [])

    def test_each_key_is_drawn_by_the_functions_it_names(self):
        drawn = drawers()
        # the keys whose drawers the contract names wrong
        self.assertEqual([k for k, e in contract().items() if e["drawn_by"] != sorted(drawn.get(k, ()))], [])

    def test_the_page_reads_no_key_the_data_does_not_have(self):
        # "demo" is what spec_drift_page.page_data adds when there are no day specs yet (demo-data.py's data)
        self.assertEqual(sorted(set(drawers()) - set(contract()) - {"demo"}), [])


if __name__ == "__main__":
    unittest.main()
