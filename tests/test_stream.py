"""The stream-json result event (Day 11, Track A): --once reads the session's cost, session and refusals
from the last result line of its stdout, and skips every line that is not one. The outcome cases run
from test_once_outcome's harness; it is imported as a module, so its own tests do not run again here."""

import json
import unittest

from tests import test_once_outcome as outcome

SYSTEM = {"type": "system", "subtype": "init"}
ASSISTANT = {
    "type": "assistant",
    "message": {
        "id": "m1",
        "content": [{"type": "text", "text": "hi"}],
        "usage": {"output_tokens": 900},
    },
}
RESULT = {
    "type": "result",
    "is_error": False,
    "result": "done",
    "total_cost_usd": 0.42,
    "permission_denials": [{}, {}],
}


class StreamResultTest(unittest.TestCase):
    setUp = outcome.OutcomeTest.setUp
    copy_of = outcome.OutcomeTest.copy_of
    run_case = outcome.OutcomeTest.run_case

    def test_result_is_the_last_result_line(self):
        # Imported here, not at the top: on the code before Track A there is no driver.stream.
        from driver import stream

        text = "\n".join(
            [json.dumps(SYSTEM), json.dumps(ASSISTANT), "not json", json.dumps(RESULT)]
        )
        self.assertEqual(stream.result(text), RESULT)
        self.assertEqual(stream.result(text.encode("utf-8")), RESULT)
        second = {**RESULT, "total_cost_usd": 0.10}
        text = "\n".join(
            [
                json.dumps(SYSTEM),
                json.dumps(second),
                json.dumps(ASSISTANT),
                "not json",
                json.dumps(RESULT),
            ]
        )
        self.assertEqual(stream.result(text).get("total_cost_usd"), 0.42)

    def test_once_reads_the_result_event(self):
        lines = [json.dumps(SYSTEM), json.dumps(ASSISTANT), "not json"]
        do = f"for line in {lines!r}: print(line)"
        result = self.run_case(copy=self.copy_of(), do=do, result=RESULT)
        records = result["records"]
        end = records[-1] if records else {}
        self.assertEqual((result["code"], result["out"].strip()), (0, outcome.OPENED))
        self.assertEqual(
            (end.get("event"), end.get("cost_usd"), end.get("denials")), ("end", 0.42, 2)
        )

    def test_unparsed_line_skipped(self):
        parked = {
            "type": "result",
            "is_error": False,
            "result": "Worked.\nPARK: needs a decision",
        }
        result = self.run_case(copy=self.copy_of(), do='print("not json")', result=parked)
        expected = "park: the session parked: needs a decision (session `<uuid>`)"
        self.assertEqual((result["code"], result["out"].strip()), (1, expected))

    def test_no_result_line(self):
        lines = [json.dumps(SYSTEM), json.dumps(ASSISTANT)]
        do = f"for line in {lines!r}: print(line)\nsys.exit(0)"
        result = self.run_case(copy=self.copy_of(), do=do)
        # The park's record comes after the end record, so take the last end, not the last record.
        ends = [record for record in result["records"] if record.get("event") == "end"]
        end = ends[-1] if ends else {}
        expected = "park: the session ended without a result (exit 0; session `<uuid>`)"
        self.assertEqual((result["code"], result["out"].strip()), (1, expected))
        self.assertEqual(
            (end.get("event"), end.get("cost_usd"), end.get("denials")), ("end", None, 0)
        )
