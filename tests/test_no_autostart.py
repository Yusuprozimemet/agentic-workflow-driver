"""Nothing installs the driver to start by itself (plan.md, "Recovery", 9: after a reboot the driver
stays off until the maintainer runs `on`). Nothing in the driver starts it at boot, so the test pins
that absence: no tracked file the driver runs or ships names a way to start a program at boot or
login, on Windows, Linux or macOS (#211, N5, P49)."""

import os
import re
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WHERE = ["driver", "docker", "hooks", "rules", "scripts", "run-steps.py"]
AUTOSTART = re.compile(
    r"schtasks|systemctl\s+(--user\s+)?enable|crontab|@reboot|RunOnce|CurrentVersion\\+Run"
    r"|launchctl|LaunchAgents|LaunchDaemons|shell:startup|Programs\\+Startup",
    re.IGNORECASE,
)


class NoAutostartTest(unittest.TestCase):
    def test_nothing_installs_an_autostart(self):
        listed = subprocess.run(
            ["git", "ls-files", "--", *WHERE], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        self.assertIn("run-steps.py", listed)
        found = []
        for name in listed:
            with open(os.path.join(ROOT, name), "rb") as f:
                text = f.read().decode("utf-8", "replace")
            found += [f"{name}: {m.group(0)}" for m in AUTOSTART.finditer(text)]
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
