"""The page's data builder, kept apart from the commands: a folder for each concern.

    sources/   what is read: git and GitHub, plan.md and the day specs, hand-offs, the
               dashboard-data branch, the tracked files, the plan's commitments
    counts/    what is counted from what the sources read: the measures, the quality score, and
               one view for each section of the page
    build/     the data the dashboard draws, and the one-file page

scripts/spec-drift.py is the command that runs them. The modules keep the names they had beside it
(spec_drift_<part>.py) and import each other by those bare names, so importing this package puts the
three folders on the path:

    sys.path.insert(0, "<scripts/>")
    import pipeline  # noqa: F401
    import spec_drift_views

A source imports only sources, a count sources and counts, the build any of them
(scripts/tests/test_scripts_layout.py holds it). scripts/README.md says what each module does.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDERS = ("sources", "counts", "build")


def path(name):
    """The full path of a module by its file's name ("spec_drift_views.py"), whichever folder holds it."""
    for folder in FOLDERS:
        full = os.path.join(HERE, folder, name)
        if os.path.isfile(full):
            return full
    raise FileNotFoundError(f"scripts/pipeline/ holds no {name}")


for _folder in FOLDERS:
    if os.path.join(HERE, _folder) not in sys.path:
        sys.path.append(os.path.join(HERE, _folder))
