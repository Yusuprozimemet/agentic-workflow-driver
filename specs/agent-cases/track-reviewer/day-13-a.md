# Brief: Day 13 Track A — `level` in the config, the own-repository refusal in `once.run`

Spec: `specs/day-13-the-merge.md`, criteria C13.1, C13.2 (both `new`); C13.20 (a `hold`, its tests
already in `tests/test_own_repository.py`, do not edit them). Work in this order: tests first, run
them red, stop if they are not red for the reason below, then the code.

## 1. Tests (write first)

### `tests/test_level_config.py` (new file; `tests/test_config.py` is frozen, do not touch it)

Class `LevelConfigTest`, one test `test_level_values`. It imports `problems` from `driver/config.py`
(`from driver.config import problems`, with the `ROOT`/`sys.path` preamble the other tests use). Base
config: `{"project": "p", "human_only": [], "budget_usd": 5, "steps_per_night": 1}`, path `"driver.json"`.
- the base with no `level`, with `"level": 1` and with `"level": 2`: `problems` returns `[]` for each;
- `"level"` set to `3`, `"2"`, `True` and `2.0`: `problems` returns exactly
  `["cannot start: driver.json's level must be 1 or 2"]` for each.
Collect the results of all seven into one dict keyed by `repr(value)` (absent as `"absent"`) and compare
it once with the expected dict, using `same` from `tests/test_review_loop.py` (fixed words in a failure).

Red today: the four bad values each give `[]`, so the comparison fails on those four keys.

### `tests/test_own_repository.py` (exists: add two tests to `OwnRepositoryTest`; leave `case`,
`test_other_origin` and `test_no_origin` as they are)

Both use `self.case(name)`, which returns `(folder, copy, flags)`; `flags` holds `--state <folder>/state`.
Add a helper method that asserts the refusal, given `(folder, copy, code, out, err, project_text)`:
- `same(self, (code, out.splitlines(), err.replace(project_text, "<project>").splitlines()), (2, [], ["cannot start: `<project>` is the driver's own repository"]))`;
- the fake `gh` was never called: `(folder / "gh" / "calls.jsonl")` does not exist or is empty;
- the fake `claude` was never called: `(folder / "claude" / "calls.jsonl")` does not exist (the fake
  writes that file on every call, `--version` included);
- no lock: `(folder / "state" / "lock")` does not exist — check the real name with `lock.path` in
  `driver/lock.py` and use `Path(lock.path(str(folder / "state")))`.
Assert the three file checks as one tuple of booleans with `same`, so a failure prints fixed words.

`test_same_folder`: `code, out, err = once(copy, *flags, "--project", str(copy))`; then the helper with
`project_text = str(copy)`.

`test_same_origin`: read the project's origin URL,
`url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=folder / "project", capture_output=True, check=True).stdout.decode().strip()`,
then `git(copy, "remote", "add", "origin", url)`, then `code, out, err = once(copy, *flags)` (the
project comes from the config `build` wrote, `folder/project`), then the helper with
`project_text` = the project path as the config holds it: `str(folder / "project")`. Check that the
config's `project` really is that string (read `tests/test_once.py`'s `write_config` and
`tests/test_dry_run.py`'s `make_project`) and adjust if not.

Red today: neither test sees the own-repository line; `test_same_folder` refuses on another line or
reads the copy, `test_same_origin` opens the step's pull request (exit 0). Run, from the repository root:

```
python scripts/seen-red.py --expect "is the driver's own repository|level must be 1 or 2" -- python -m unittest tests.test_level_config tests.test_own_repository
```

It must exit 0 and print `seen red:` lines for `test_level_values`, `test_same_folder` and
`test_same_origin`; `test_other_origin` and `test_no_origin` pass on `main` (holds). If it exits 1,
stop and report what it printed; do not write the code.

## 2. Code

### `driver/config.py`, `problems`
After the `review` check, add: `level` is optional; when present it must be the int `1` or `2`, not a
bool and not a float, else the line `f"cannot start: {path}'s level must be 1 or 2"`. (`True == 1`
and `2.0 == 2` in Python: test the type first, as `is_steps` does.) Add a short comment as the others
have ("Absent is 1: ..."), and one sentence to the module docstring about the optional `level`, 1 or 2,
1 when absent. Nothing reads `level` yet; do not add a reader.

### `driver/once.py`, `run`
After the config is loaded and `project` is set, and before `lock.take(args.state)`, add:

```python
    if own_repository(home, project):
        return refuse([f"cannot start: `{project}` is the driver's own repository"])
```

`project` is printed as given (as `--project` or the config gave it), not resolved. Add a module-level
function `own_repository(home, project)` near `run`, returning a bool:
- True when `os.path.normcase(str(Path(project).resolve()))` equals the same of `home` (`from pathlib
  import Path` if `once.py` does not import it yet; check);
- else the origin URL of each folder, read with
  `subprocess.run(["git", "ls-remote", "--get-url", "origin"], cwd=<folder>, capture_output=True, check=False)`;
  a URL is the stripped stdout decoded as UTF-8 when the exit code is 0 and the text is not empty and
  not the word `origin` (git echoes the remote's name when there is no such remote); an `OSError`
  (the folder missing) or any other exit is no URL. True only when both have a URL and the two are
  equal. No `gh` call, nothing else of the project read.
A comment of one or two lines on why `origin` counts as no URL. Update the module docstring's order
of checks: it lists "the config, the lock, the driver's own repository": put the own repository
before the lock and say in a few words that it is this check (the project is the driver's folder, or
both share an origin URL); the driver's folder check after the lock (`driver_home.check`) stays.

Do not touch `driver/home.py` (frozen), `tests/test_config.py`, or any other test file.

## 3. Run, then report

```
python scripts/test-parallel.py "test_level_config.py" "test_own_repository.py" "test_once*.py" "test_on.py" "test_config.py" "test_dry_run*.py"
ruff check . && ruff format --check .
```

(If `test-parallel.py` takes one glob only, run it once per glob.) Expected: `test_level_config` 1
test OK, `test_own_repository` 4 tests OK, the rest as on `main`. Report the files changed, the
seen-red output, the test counts, and anything you could not do as written.
