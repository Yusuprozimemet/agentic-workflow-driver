"""The optional container keys in driver.json: container_image and container_secrets come as a pair,
and each present key is checked for its type. config.load() is called on a driver.json written into
a temporary folder, and the lines it returns are compared with the path replaced by <path>, so a
failure message holds no absolute path."""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def good(project):
    return {"project": str(project), "human_only": [], "budget_usd": 5, "steps_per_night": 3}


class ContainerConfigTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, so a missing module fails each test alone.
        self.config = importlib.import_module("driver.config")

    def folder(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return Path(os.path.realpath(tmp.name))

    def load(self, tmp, **keys):
        # Written as bytes: on Windows, text mode would add a carriage return to the file.
        path = tmp / "driver.json"
        path.write_bytes(json.dumps({**good(tmp), **keys}).encode("utf-8"))
        config, lines = self.config.load(path)
        return config, [line.replace(str(path), "<path>") for line in lines]

    def test_container_keys_checked(self):
        tmp = self.folder()
        secrets = str(tmp / "secrets.env")
        image_only = "cannot start: <path> has container_image but no container_secrets"
        secrets_only = "cannot start: <path> has container_secrets but no container_image"
        bad_image = "cannot start: <path>'s container_image must be an image name"
        bad_secrets = "cannot start: <path>'s container_secrets must be an absolute path"
        cases = [
            ({"container_image": "img:1"}, [image_only]),
            ({"container_secrets": secrets}, [secrets_only]),
            ({"container_image": "", "container_secrets": secrets}, [bad_image]),
            ({"container_image": 5, "container_secrets": secrets}, [bad_image]),
            ({"container_image": "img:1", "container_secrets": "secrets.env"}, [bad_secrets]),
            ({"container_image": "img:1", "container_secrets": 5}, [bad_secrets]),
        ]
        for number, (keys, expected) in enumerate(cases):
            with self.subTest(case=number):
                config, lines = self.load(tmp, **keys)
                self.assertEqual(lines, expected)
                self.assertIsNone(config)
        config, lines = self.load(tmp, container_image="img:1", container_secrets=secrets)
        self.assertIsNotNone(config)
        self.assertEqual(config.get("container_image"), "img:1")
        # Compared as a bool: a failing string comparison would print the absolute path.
        self.assertTrue(config.get("container_secrets") == secrets)
        self.assertEqual(lines, [])


if __name__ == "__main__":
    unittest.main()
