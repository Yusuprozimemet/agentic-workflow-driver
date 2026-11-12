"""The write probe: run in the session's container before each session, it tries to create and
remove a file in each folder given, and prints `written <folder>` or `refused <folder>` for each, in
order, and exits 0. `python hooks/probe.py <folder>...`, standard library only: the driver's reach()
in driver/box.py reads these lines before a session starts."""

import os
import sys
import tempfile


def main(folders):
    for folder in folders:
        try:
            fd, path = tempfile.mkstemp(dir=folder)
            os.close(fd)
            os.remove(path)
        except OSError:
            print(f"refused {folder}")
        else:
            print(f"written {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
