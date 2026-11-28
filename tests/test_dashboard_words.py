"""The dashboard's words for its biology: the plan is the gene, graph 1 is its reading, proofreading is graph 7's
second layer alone, graph 13 is read as immunity, two sets of merges no criterion cites have names of their own,
and the file map's small words say what each station is in the cell."""

import importlib.util
import os
import re
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
PAGE = os.path.join(ROOT, "docs", "dashboard")
sys.path.insert(0, SCRIPTS)
import pipeline  # noqa: F401  (the views import each other from scripts/pipeline/counts/)


def read(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as f:
        return f.read()


def views():
    spec = importlib.util.spec_from_file_location(
        "spec_drift_views", os.path.join(SCRIPTS, "pipeline", "counts", "spec_drift_views.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OneBiologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.js = read("index.html"), read("dashboard.js")

    def says(self, text, words):
        """Whether the text holds the words, kept short so a failure names the words and not the file."""
        return (words[:48], words in text)

    def test_graph_1_is_the_plan_being_read_not_a_gene_of_its_own(self):
        both = (self.html + self.js).lower()
        self.assertEqual(self.says(self.js, "GENE, AS READ"), ("GENE, AS READ", False))
        self.assertEqual(self.says(both, "read as a gene"), ("read as a gene", False))
        self.assertEqual(self.says(self.js, "THE READING, SO FAR"), ("THE READING, SO FAR", True))
        caption = "Graph 1 · the plan being read, merge by merge"
        self.assertEqual(self.says(self.html, caption), (caption, True))
        fold = "The plan is the gene, and each merge is one more step of reading it"
        self.assertEqual(self.says(self.html, fold), (fold[:48], True))

    def test_proofreading_names_graph_7s_second_layer_and_nothing_else(self):
        self.assertEqual(
            self.says(self.html, "drawn as proofreading"), ("drawn as proofreading", False)
        )
        named = '"spec-auditor", "proofreading"'
        self.assertEqual(self.says(self.js, named), (named, False))
        named = '"spec-auditor", "reading the template"'
        self.assertEqual(self.says(self.js, named), (named, True))
        stream = "The proofreading stream"
        self.assertEqual(self.says(self.js, stream), (stream, False))
        layers = [L["name"] for L in views().PRF_LAYERS if "proofreading" in L["bio"]]
        self.assertEqual(layers, ["While writing"])

    def test_the_ring_and_graph_13_say_what_they_are_read_as(self):
        for words in (
            "Where we are · the plan as one turn of the cell cycle, a checkpoint at each stop",
            "Graph 13 · read as immunity, after the checking",
            (
                "Read it as immunity: a fix is the memory of a problem met once, and a problem "
                "that comes back although its fix was in place is an escape."
            ),
        ):
            self.assertEqual(self.says(self.html, words), (words[:48], True))

    def test_graph_12_and_graph_6_name_what_they_count(self):
        for words, there in (
            ('"Criteria in force per Day"', True),
            ("drawn for a stop`", True),
            ("} uncited`", False),
            ("of product code no criterion cites", True),
        ):
            self.assertEqual(self.says(self.js, words), (words, there))

    def test_graph_1s_visible_key_has_a_swatch_for_every_cell_colour(self):
        section = self.html[self.html.index('<section class="graph" id="rdg">') :]
        line = re.search(r'<p class="mk-line"[^>]*>(.*?)</p>', section, re.DOTALL)
        self.assertIsNotNone(line)
        drawn = sorted(set(re.findall(r'class="cell (k-\w+)"', line.group(1))))
        self.assertEqual(drawn, ["k-close", "k-code", "k-spec"])

    def test_the_file_maps_small_words_put_the_folding_check_after_the_protein(self):
        for words in (
            '"negative control"',
            '"then a knock-out"',
            '"track-reviewer", "folding check"',
        ):
            self.assertEqual(self.says(self.js, words), (words, True))
        self.assertEqual(self.js.count('"folding check"'), 1)


if __name__ == "__main__":
    unittest.main()
