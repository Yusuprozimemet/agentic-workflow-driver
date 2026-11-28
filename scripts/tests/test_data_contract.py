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


def maker(value, main):
    """The function that makes `value`: the call it is, or for a name, the call main() assigned the name from;
    "main" for a dict(...) main() builds itself. Any other expression (a list) is made by the names it reads
    that main() assigned. More than one function is ambiguous, and the test fails on it."""
    if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
        return {"main"} if value.func.id == "dict" else {value.func.id}
    assigned = {}
    for node in ast.walk(main):
        if isinstance(node, ast.Assign):
            for target, val in _pairs(node):
                for t in target.elts if isinstance(target, ast.Tuple) else [target]:
                    if isinstance(t, ast.Name):
                        assigned.setdefault(t.id, []).append(val)
    if isinstance(value, ast.Name):
        names = [value.id]
    else:
        names = sorted({n.id for n in ast.walk(value) if isinstance(n, ast.Name)} & set(assigned))
    return {f for name in names for val in assigned.get(name, []) for f in maker(val, main)}


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


def _code(text):
    """dashboard.js with its comments and the text of its strings blanked, lengths and lines kept: what is left
    is code. A ${...} inside a template string is code too."""
    out, i, n, stack = list(text), 0, len(text), []  # "`" for a template string, "{" for a ${ inside one

    def blank(a, b):
        for j in range(a, min(b, n)):
            if out[j] != "\n":
                out[j] = " "

    while i < n:
        c, nxt = text[i], text[i + 1 : i + 2]
        if stack and stack[-1] == "`":
            if c == "\\":
                blank(i, i + 2)
                i += 2
            elif c == "`":
                stack.pop()
                i += 1
            elif c == "$" and nxt == "{":
                stack.append("{")
                i += 2
            else:
                blank(i, i + 1)
                i += 1
        elif c == "/" and nxt == "/":
            end = text.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif c == "/" and nxt == "*":
            end = text.find("*/", i + 2) + 2
            blank(i, end)
            i = end
        elif c == "/" and re.search(r"(^|[(,=:\[!&|?{};+\-*%<>~^]|\breturn)\s*$", text[max(0, i - 40) : i]):
            # a regex literal, where an operand is expected: /`/g is no template string
            j, klass = i + 1, False
            while j < n and text[j] != "\n" and (klass or text[j] != "/"):
                klass = (klass or text[j] == "[") and text[j] != "]"
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            blank(i + 1, j)
            i = j + 1
        elif c == "`":
            stack.append("`")
            i += 1
        else:
            if c == "{" and stack:
                stack.append("{")
            elif c == "}" and stack:
                stack.pop()
            i += 1
    return "".join(out)


def drawers():
    """{key: the functions of dashboard.js that read DATA.key}: the innermost function declared at the file's
    top level or one level in (model()'s graphs, as `  function prfGraph() {`) whose braces hold the read.
    Comments and the text of strings are not read."""
    with open(PAGE_JS, encoding="utf-8") as f:
        code = _code(f.read())
    spans = []
    for m in re.finditer(r"^(?:  )?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{", code, re.M):
        depth, j = 1, m.end()
        while depth and j < len(code):
            depth += {"{": 1, "}": -1}.get(code[j], 0)
            j += 1
        spans.append((m.start(), j, m.group(1)))
    found = {}
    for m in re.finditer(r"\bDATA\.(\w+)|\bDATA\[\"(\w+)\"\]", code):
        inside = [s for s in spans if s[0] <= m.start() < s[1]]
        found.setdefault(m.group(1) or m.group(2), set()).add(max(inside)[2] if inside else "(top level)")
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
            self.assertIn(key, keys)
            self.assertEqual(sorted(maker(keys[key], main)), [function], key)

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
