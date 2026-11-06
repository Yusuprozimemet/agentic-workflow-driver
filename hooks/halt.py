"""The halt hook: a session's PreToolUse check that refuses every call while the driver is halted.

`python hooks/halt.py <halt file>` exits 2 with one line on stderr while the halt file exists, and
exits 0 with nothing printed when it does not. It reads no environment variable and no stdin: the
session's folder does not matter, only the path it was given.
"""

import os
import sys


def main(argv):
    if len(argv) < 2 or not argv[1]:
        print("halted: the halt hook was given no halt file", file=sys.stderr)
        return 2
    if os.path.exists(argv[1]):
        print(f"halted: {argv[1]} exists; run-steps.py clear removes it", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
