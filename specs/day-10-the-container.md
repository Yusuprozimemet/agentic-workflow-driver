# Day 10 — The session's container: the image, sessions started and killed in it, its reach checked before each session, the count from it, the bypass line

**Phase:** 2 · **Depends on:** Day 9 · **Expected PRs:** 11 (the spec change, Tracks A, B, C1, C2, D1, D2, E, F, G, the close)

## Goal
With `container_image` and `container_secrets` in `driver.json`, every session the driver starts
(a step's, a fix's resume, the usage limit's resume) runs in a Docker container of that image with
only the mounts `plan.md` ("Where the driver lives") lists: the driver's hooks and rules, never the
rest of its folder; the driver kills it with `docker kill` past `--session-minutes`, on a STOP issue
and on `run-steps.py halt`, and Recovery waits on it while it runs; before each session the driver
checks that Docker runs, the image exists, its Claude Code is live-checked, and, from inside the
container, that the driver's hooks, rules and state cannot be written and the project,
`<state>/refusals` and `<state>/claude` can; the usage limit is read from `<state>/claude`;
`status`'s level 2 count counts only pull requests a container session opened;
`scripts/setup-check.py` says whether anyone may bypass `main`'s protection; and one real step of
the trial's project ran in the container and opened its pull request.

## In scope

- **The config and the command (Track A).** `driver.json` takes two optional keys, given together
  or not at all: `container_image`, an image name (`agentic-workflow-driver-session:2.1.322`), and
  `container_secrets`, the absolute path of the maintainer's env file (`GH_TOKEN` and
  `CLAUDE_CODE_OAUTH_TOKEN`), outside both repositories. `driver.config.load` reports a problem
  with them as it reports the others, one line each; a config with neither loads as today, and the
  driver then runs every session on the PC as it does now (level 1 only, `plan.md`).
  `driver/box.py` builds the container's command, `driver.box.command(docker, image, secrets,
  home, state, project, name, inner, stdin=True)`, the list:
  `[docker, "run", "-i", "--rm", "--name", <name>, "--env-file", <secrets>, "-e",
  "CLAUDE_CONFIG_DIR=/claude", "-w", "/work"]` (`"-i"` left out when `stdin` is false), then one
  `--mount` pair per mount, in this order:
  `type=bind,source=<project>,target=/work`;
  `type=bind,source=<home>/hooks,target=/driver/hooks,readonly`;
  `type=bind,source=<home>/rules,target=/driver/rules,readonly`;
  `type=bind,source=<state>,target=/state,readonly`;
  `type=bind,source=<state>/refusals,target=/state/refusals`;
  `type=bind,source=<state>/claude,target=/claude`; then the image, then `inner`. Each source is
  the folder's real path. The driver's folder itself, its `.env`, `driver.json` and `.git`, is
  never mounted, and no `--privileged`, `-v` or `--volume` is ever in the list.
  `driver.settings.write(state, home, inside=True)` writes `<state>/container-settings.json`, the
  same two hooks as `settings.json` with the commands
  `python "/driver/hooks/halt.py" "/state/halt" "/state/refusals"` and
  `python "/driver/hooks/guard.py" "/driver" "/state/refusals"`; `settings.json` is written as
  today. `run-steps.py` takes `--docker` (default `docker`), as it takes `--gh`.
- **The image (Track B).** `docker/Dockerfile`, from `node:22-trixie-slim` as the spike's was
  (`plan.md`, "Shown on 2026-11-11"): Claude Code at the version of a build argument
  `CLAUDE_VERSION`; Python 3 in a virtual environment at `/opt/venv`, first on `PATH`, so that
  `python` and `pip` run and the session can install the project as CI does; `git`; `gh`;
  `/etc/gitconfig` with `safe.directory = /work`, `core.autocrlf = true`, `core.filemode = false`,
  the commit identity from build arguments `GIT_NAME` and `GIT_EMAIL`, and
  `credential.helper = !gh auth git-credential`; and `USER node`. `docs/container.md`: the build
  (`docker build --build-arg CLAUDE_VERSION=<v> --build-arg GIT_NAME=<n> --build-arg GIT_EMAIL=<e>
  -t agentic-workflow-driver-session:<v> docker`, with a `GIT_NAME` other than the PC's, so a
  commit made in the container can be told from one made on the PC), the secrets file
  (`claude setup-token`, the fine-grained token as "The token" in `plan.md` scopes it, kept outside
  both repositories, never mounted), the two `driver.json` keys, the project's test tools installed
  by the session with `pip install` as CI installs them, and on GitHub the project's `main` with
  "Do not allow bypassing the above settings" turned on.
- **The image checked before a session (Track C1; `plan.md`, Day 10).** With the container keys,
  `--once` and `on` check, in `driver.once.preflight` before the project's issues are read, in
  this order, and print only the first that fails:
  `<docker> version --format {{.Server.Version}}` exits 0, else
  "cannot start: Docker does not run: <its last stderr line, or "exit <n>">";
  `<docker> image inspect <image>` exits 0, else
  "cannot start: the image `<image>` is not built; docs/container.md says how";
  `container_secrets` is a file, else "cannot start: the secrets file `<path>` does not exist".
  When all three pass, Day 2's version and `--help` checks run on the image's Claude Code
  (`<docker> run --rm <image> claude --version` and `... claude --help`) in place of the PC's,
  through `driver.preflight.cli_lines`, which takes the command to run in place of a program on
  `PATH`; their lines name it "the image's claude" where Day 2's name the program (for example
  "cannot run a session: the image's claude --help lists no --settings"), and the "older than"
  line is Day 2's. The kit's lines are checked as today. `on`'s live check reads the image's
  version line in place of the PC's.
- **The reach checked before each session (Track C2; `plan.md`, Day 10, and H09.1).** Before each
  session `--once` or `on` starts (each step's, not only the first: after `ready()` returns a start
  and before `begin()` opens the run's issue), the driver makes the session's uuid (then given to
  `begin()`), makes `<state>/refusals` and `<state>/claude` if missing, and calls
  `driver.box.reach(docker, image, secrets, home, state, project, session)`, which runs
  `hooks/probe.py` in a container of the image with the session's mounts:
  `driver.box.command(..., "driver-probe-<session>", ["python", "/driver/hooks/probe.py",
  "/driver/hooks", "/driver/rules", "/state", "/work", "/state/refusals", "/claude"],
  stdin=False)`, and returns `None` or the line below.
  `hooks/probe.py <folder>...`, standard library only and importing nothing from `driver/`: for
  each folder, creates a new file in it and removes it, and prints `written <folder>` or
  `refused <folder>` (a missing folder is refused), one line each, in order, then exits 0. The
  first three must print `refused`, the last three `written`; otherwise the driver prints one line
  on stderr and exits 2, with no issue opened or commented, no run log line and no session:

  | The probe | The driver prints |
  |---|---|
  | exits non-zero, or prints other than six such lines | "cannot start: the session's container cannot run the probe: <its last stderr line, or "exit <n>">" |
  | `written` for `/driver/hooks`, `/driver/rules` or `/state` | "cannot start: the session's container can write `<folder>`" |
  | `refused` for `/work`, `/state/refusals` or `/claude` | "cannot start: the session's container cannot write `<folder>`" |

  The first row that applies wins, and within it the first folder in the probe's order.
- **Sessions start in it (Track D1).** With the container keys, `driver.once.begin` builds the
  session's command as `driver.box.command(..., "driver-<session>", ["claude", "-p", ...])`: today's
  flags, with `--settings /state/container-settings.json` and `--append-system-prompt-file
  /driver/rules/session.md`. A fix's resume (`driver.loop.resume`) and the usage limit's resume
  replace `--session-id` with `--resume` inside it, as today, and keep the container's name. The
  run log's `start` and `pid` lines carry `"container": "driver-<session>"` (last, as `issue`
  goes last), and `start`'s `claude` is the image's version line. The usage limit's transcript
  (`driver.once.limit_reset`) is read from `<state>/claude/projects/*/<session>.jsonl` only, at
  the session's end and at the resumed session's end. Without the container keys no `docker` is
  run and nothing of this changes.
- **Sessions are killed in it (Track D2).** With a `container` on the session's `pid` line:
  `driver.once.kill_session` (past `--session-minutes`) and `driver.once.stop_session` (a STOP
  issue) run `<docker> kill driver-<session>` before their kill of the process tree, since
  killing the `docker` client leaves the container running. `runlog.live_container(state)` returns
  `(session, name)` for the newest `pid` line with a `container` and no later `end`, whether or not
  its pid lives, else `(None, None)`; `runlog.live_session` keeps its three-value answer and its
  pid rule. `driver.switches.halt(state, docker="docker")`, after its kills of today, runs
  `<docker> kill <name>` for `live_container`'s name; when that exits 0 it prints
  "halt: set; killed container `<name>` of session `<session>`" and not "halt: set; no driver is
  running"; when its stderr holds "No such container", nothing more than today; else
  "halt: set; could not kill container `<name>`: <its last stderr line>". `halt` asks no
  `inspect`. In `ready()`, with the container keys, when `live_session` finds no live pid and
  `live_container` names a session whose `<docker> inspect --format {{.State.Running}} <name>`
  prints `true`, it waits with "wait: session `<session>` is still running (container `<name>`)";
  a live pid keeps today's line. `status` reads `live_session` as today and runs no `docker`.
- **The count (Track E; `plan.md`, Levels).** `driver.status.level_2_run` counts a `merged` line
  only when the log shows a container session opened its pull request: the newest `end` line whose
  outcome starts "opened: #<pr> " belongs to a session whose `start` line has a `container`. A
  `merged` line for any other pull request (opened on the PC, or opened by no session the log
  names) ends the count there, as a change asked does. The line `status` prints keeps its words.
  On the Day 8 trial's log, whose sessions ran on the PC, the count is 0.
- **The bypass line (Track F; `plan.md`, "Course correction after Phase 1").**
  `scripts/setup-check.py`'s `protection_lines` adds one line after the pull request line:
  `("ok", "main: no one may bypass the rules")` when a rule that requires a pull request on `main`
  admits no bypass, that is classic protection with `enforce_admins.enabled` true, or a ruleset
  (the `ruleset_id` of a `pull_request` rule from `repos/<repo>/rules/branches/main`) whose
  `repos/<repo>/rulesets/<id>` gives `bypass_actors` as an empty list; else
  `("FAIL", 'main: administrators may bypass the rules; turn on "Do not allow bypassing the above settings"')`.
  A ruleset that cannot be read is a FAIL as `unreadable` words it, and one whose answer has no
  `bypass_actors` key (GitHub leaves it out for a caller without admin rights) is
  `("FAIL", "main's ruleset <id>: cannot read: bypass_actors not shown (needs admin)")`.
- **The first step in the container (Track G).** After D2 and E merge and the image is built, the
  maintainer's `run-steps.py --once` on the trial's project runs one real step in the container,
  which pushes its branch with `GH_TOKEN` and opens its pull request. `docs/trial/day-10.md`
  records the run log's lines, the pull request, its commit's author and the cost.

## Out of scope

- The level 2 merge refusing unless the three conditions hold (the count, the container, `main`'s
  protection with no bypass) — Day 12, which reads this day's count and `setup-check.py`'s line.
- `live-check` running in the image: it runs `tests/test_live_cli.py` on the PC's Claude Code, and
  the image must be built at a version it listed (C10.9) (H10.1).
- Sessions on the PC: without the container keys they run as today, at level 1; nothing here
  refuses that.
- The reviewer — Day 11. The usage limit met by a headless session — Day 13 (H09.2).
- Counting the container's transcripts with `scripts/token-usage.py`: it keeps only folders named
  after this repository's path, and the container's are `projects/-work/`; Track G reads the cost
  from the run log's `end` line, and the count goes to Day 13's record (H10.2).
- Removing a probe container left behind: `--rm` removes it, and C07.1 keeps the string "rm" out
  of `driver/*.py`, so the driver runs no `docker rm`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | The config keys, `driver/box.py`'s command, the container's settings file, `--docker`: C10.1–C10.4 |
| B | | `docker/Dockerfile`, `docs/container.md`, the image's live test: C10.5–C10.7 |
| C1 | | Docker, the image, the secrets file and the image's Claude Code checked before a session; `tests/fake_docker.py`: C10.8–C10.9 |
| C2 | | `hooks/probe.py`, `driver.box.reach`, the reach check before each session: C10.10–C10.14 |
| D1 | | Sessions start in the container; the run log's `container`; the transcripts' folder: C10.15–C10.19 |
| D2 | | `docker kill` past the bound, on STOP and on `halt`; Recovery waits on a running container: C10.20–C10.23, C10.32 |
| E | | `status`'s level 2 count from container sessions only: C10.24–C10.26 |
| F | | `setup-check.py`'s bypass line: C10.27–C10.29 |
| G | | The first step in the container, on the trial's project: C10.30 |

In order: A, B, C1, C2, D1, D2, E, G; F at any time. B follows A (its live test imports
`driver.box`); C1 owns `tests/fake_docker.py`, which C2, D1 and D2 use; C2 and D1 both edit
`driver/once.py` and `driver/loop.py`, C2 first. G last, with the image built by the maintainer as
`docs/container.md` says. C10.31 is checked on each track and at the close.

Breaks recorded on earlier days whose finds a track rewrites are recorded again in that track's PR
under the same `<what>`, with a `manifest:` line, as #128 did: A — Day 9's `entry(GUARDED, ...)`
and `f'"{argument}"' for argument` in `driver/settings.py`, and C03.5's (its find in the settings
file's command line); C1 — Day 6's `lines += cli_lines(args.claude)`; C2 and D1 — Day 4's
`settings_path = driver_settings.write(args.state, home)`, Days 7 and 8's `record["issue"] = issue`,
and Day 9's `limit_reset` and `record.get("type") == "assistant"`; D2 — Day 7's
`print("halt: set; no driver is running")`; E — C08.2's (`status.py`'s `_refusals(records, late)`).
A track checks the day manifests in `specs/breaks/` for its files before it opens its PR.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

The tests below replace, before they compare a printed line or a command list, the temporary
folders with `<home>`, `<state>` and `<project>`, the secrets file's path with `<secrets>`, and a
session's uuid with `<uuid>`, so that a break's report holds no absolute path and no uuid. They
build every absolute path from a temporary folder, never a Windows literal, so they run on CI's
Linux. They run Docker through `tests/fake_docker.py`, a fake `--docker` program, which records
its arguments and answers `version`, `image inspect`, `inspect`, `kill` and `run` as the test sets
it; no test but C10.7, C10.14 and C10.30 needs Docker.

- [x] C10.1 **new** — `driver.config.load` on a config with every Day 2 key and
      `"container_image": "img:1"` but no `container_secrets` returns `None` and the line
      "cannot start: <path> has container_image but no container_secrets"; with
      `container_secrets` and no `container_image`, "cannot start: <path> has container_secrets
      but no container_image"; with `container_image` `""` or not a string, "cannot start:
      <path>'s container_image must be an image name"; with `container_secrets` a relative path or
      not a string, "cannot start: <path>'s container_secrets must be an absolute path". With both
      valid it returns the config with both keys as given and no lines.
      Red today: `load` ignores keys it does not know, so each case returns the config and no lines.
      Test: `ContainerConfigTest.test_container_keys_checked`.
      Evidence: `ContainerConfigTest.test_container_keys_checked` (#149).
      seen red: python -m unittest tests.test_box_config on main → AssertionError: Lists differ: [] != ["cannot start: <path>'s container_secrets must be an absolute path"] (#149)
      broken: a relative container_secrets accepted → AssertionError: Lists differ: [] != ["cannot start: <path>'s container_secrets must be an absolute path"] (#149)
- [x] C10.2 **new** — `driver.box.command("docker", "img:1", <secrets>, <home>, <state>,
      <project>, "driver-s1", ["claude", "-p"])` returns exactly the list In scope gives, ending
      `"img:1", "claude", "-p"`; with `stdin=False`, the same without `"-i"`. It holds no
      `--privileged`, `-v` or `--volume`, no source but the six, and no source that is `<home>`
      itself.
      Red today: `driver/box.py` does not exist (ModuleNotFoundError).
      Test: `BoxCommandTest.test_the_mounts`.
      Evidence: `BoxCommandTest.test_the_mounts`; `--docker` in `BoxCommandTest.test_docker_flag` (#149).
      seen red: python -m unittest tests.test_box_command.BoxCommandTest.test_the_mounts on main → FAILED (errors=1) (#149)
      seen red: python -m unittest tests.test_box_command.BoxCommandTest.test_docker_flag on main → AssertionError: False is not true : run-steps.py --help names no --docker (#149)
      broken: the state folder mounted writable → AssertionError: Lists differ: ['doc[374 chars]state', '--mount', 'type=bind,source=<state>/r[113 chars]'-p'] != ['doc[374 chars]state,readonly', '--mount', 'type=bind,source=[122 chars]'-p'] (#149)
- [x] C10.3 **new** — `driver.settings.write(<state>, <home>, inside=True)` writes
      `<state>/container-settings.json` whose two hook commands are, as printed,
      `python "/driver/hooks/halt.py" "/state/halt" "/state/refusals"` and
      `python "/driver/hooks/guard.py" "/driver" "/state/refusals"`, with the matchers of
      `settings.json`, and returns its path; `<state>/settings.json` is not written by that call.
      Red today: `write` takes no `inside` (TypeError).
      Test: `BoxCommandTest.test_container_settings`.
      Evidence: `BoxCommandTest.test_container_settings` (#149).
      seen red: python -m unittest tests.test_box_command.BoxCommandTest.test_container_settings on main → FAILED (errors=1) (#149)
      broken: the container settings written to settings.json → AssertionError: 'settings.json' != 'container-settings.json' (#149)
- [x] C10.4 **hold** — A config with neither key loads, and sessions start, as before:
      `python -m unittest tests.test_config tests.test_hooks tests.test_once_run` passes with the
      files unedited.
      Evidence: the command above passes, the three files unedited since `495bf69` (#149).
      broken: a config with neither container key refused → AssertionError: Tuples differ: (1, '') != (0, 'start: Day 01: read the spec against the code, then the spec-change PR\n') (#149)
- [x] C10.5 **new** — `docker/Dockerfile` holds `FROM node:22-trixie-slim`, `ARG CLAUDE_VERSION`,
      `ARG GIT_NAME`, `ARG GIT_EMAIL`, an install of `@anthropic-ai/claude-code@${CLAUDE_VERSION}`,
      `/opt/venv`, `USER node`, and each of "safe.directory", "/work", "autocrlf", "filemode" and
      "gh auth git-credential"; and `docs/container.md` holds each of "docker build",
      "CLAUDE_VERSION", "GIT_NAME", "claude setup-token", "GH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN",
      "container_image", "container_secrets", "pip install" and "Do not allow bypassing the above
      settings"; `python scripts/check-links.py docs/container.md` exits 0.
      Red today: neither file exists.
      Test: `ImageFilesTest.test_dockerfile_and_doc`.
      Evidence: `ImageFilesTest.test_dockerfile_and_doc`; `python scripts/check-links.py docs/container.md` exits 0 (#150).
      seen red: python -m unittest tests.test_image_files.ImageFilesTest.test_dockerfile_and_doc on main → AssertionError: False is not true : docker/Dockerfile does not exist (#150)
      broken: the image left running as root → AssertionError: False is not true : docker/Dockerfile does not hold 'USER node' (#150)
- [x] C10.6 **new** — Every mount `docs/container.md` shows is one of the six: each `source=` in
      it is followed by one of `<project>`, `<home>/hooks`, `<home>/rules`, `<state>`,
      `<state>/refusals` and `<state>/claude`, and it holds no `-v ` and no `--volume`. Words that
      warn against a mount (the Docker socket, `--privileged`) are not checked.
      Red today: the file does not exist.
      Test: `ImageFilesTest.test_doc_mounts_the_six`.
      Evidence: `ImageFilesTest.test_doc_mounts_the_six` (#150).
      seen red: python -m unittest tests.test_image_files.ImageFilesTest.test_doc_mounts_the_six on main → AssertionError: False is not true : docs/container.md does not exist (#150)
      broken: the page mounts the driver's folder → AssertionError: False is not true : docs/container.md shows the unknown mount source '<home>' (#150)
      broken: the page shows a -v mount → AssertionError: False is not true : docs/container.md shows a -v flag (#150)
- [x] C10.7 **new** — Live: the test first checks that `docker/Dockerfile` exists (before any
      skip, so that on `main` it fails), then runs only when `DRIVER_CONTAINER_IMAGE` names a built
      image (skipped otherwise, as `DRIVER_LIVE_CLI` skips `tests/test_live_cli.py`): in that
      image, `python --version` prints "Python 3", `pip --version` exits 0,
      `git config --system --get safe.directory` prints "/work",
      `git config --system --get core.autocrlf` prints "true", `id -un` prints "node", and
      `claude --version`'s first line starts with the image's tag after the colon.
      Red today: `docker/Dockerfile` does not exist: AssertionError before the skip.
      Test: `ImageLiveTest.test_image_has_its_tools`.
      Evidence: `ImageLiveTest.test_image_has_its_tools`, run with `DRIVER_CONTAINER_IMAGE=agentic-workflow-driver-session:2.1.322` on this machine (#150); CI skips its Docker part.
      Live, so not replayed: CI and the replay have no image; a reader checked the live run and its break in #150: with `USER node` made `USER root`, the rebuilt image's `id -un` printed root and the test failed twice. That break is not replayable and has no manifest entry.
      seen red: python -m unittest tests.test_image_live.ImageLiveTest.test_image_has_its_tools on main → AssertionError: False is not true : docker/Dockerfile does not exist (#150)
- [x] C10.8 **new** — With the container keys, `run-steps.py --once` driven in-process with the
      fake `docker`: `version` exiting 1 with "Cannot connect to the Docker daemon" prints only
      "cannot start: Docker does not run: Cannot connect to the Docker daemon" on stderr and exits
      2; `image inspect` exiting 1 prints only "cannot start: the image `img:1` is not built;
      docs/container.md says how"; a `container_secrets` that does not exist prints only "cannot
      start: the secrets file `<secrets>` does not exist". In each case no issue is read and the
      PC's `--claude` is never run.
      Red today: the keys are ignored; the PC's Claude Code is checked and a session starts.
      Test: `BoxPreflightTest.test_docker_down`, `BoxPreflightTest.test_no_image`,
      `BoxPreflightTest.test_no_secrets`.
      Evidence: `BoxPreflightTest.test_docker_down`, `BoxPreflightTest.test_no_image`, `BoxPreflightTest.test_no_secrets` (#151).
      seen red: python -m unittest tests.test_box_preflight on main → AssertionError: 0 != 2 (#151)
      broken: Docker down not reported → AssertionError: Lists differ: ["cannot run a session: the image's claude[774 chars]ume"] != ['cannot start: Docker does not run: Canno[27 chars]mon'] (#151)
      broken: the image not inspected → AssertionError: Lists differ: ["cannot run a session: the image's claude[774 chars]ume"] != ['cannot start: the image `img:1` is not b[29 chars]how'] (#151)
      broken: the secrets file not checked → AssertionError: Lists differ: ["cannot run a session: the image's claude[774 chars]ume"] != ['cannot start: the secrets file `<secrets[14 chars]ist'] (#151)
- [x] C10.9 **new** — As C10.8, with Docker, the image and the secrets file there: the image's
      `claude --version` printing "2.1.100" prints Day 2's line "cannot run a session: Claude Code
      2.1.100 is older than <the oldest>, the oldest the driver was checked on"; its `--help`
      lacking `--settings` prints "cannot run a session: the image's claude --help lists no
      --settings"; the PC's `--claude` is never run. `on` with the image's version line not in
      `live-checked.txt` prints the live check's line naming the image's version.
      Red today: as C10.8.
      Test: `BoxPreflightTest.test_image_cli_checked`, `BoxPreflightTest.test_on_live_check_reads_the_image`.
      Evidence: `BoxPreflightTest.test_image_cli_checked`, `BoxPreflightTest.test_on_live_check_reads_the_image` (#151; their breaks recorded again in #152, which changed what they report).
      seen red: python -m unittest tests.test_box_preflight on main → AssertionError: 0 != 2 (#151)
      broken: the PC's claude checked in place of the image's → AssertionError: Lists differ: ["cannot start: the session's container cannot run the probe: exit 0"] != ["cannot run a session: the image's claude --help lists no --settings"] (#152)
      broken: on's live check reads the PC's version → AssertionError: Lists differ: ["cannot start: the session's container ca[23 chars]t 0"] != ['cannot start: Claude Code `2.1.400 (Clau[65 chars]eck'] (#152)
      broken: --once reads the live-check record → AssertionError: Tuples differ: (2, 0) != (0, 1) (#151)
      broken: on skips the version check → AssertionError: Tuples differ: (0, "opened: #5 from `day-01/track-a-x`\no[707 chars]alse) != (2, '', ['cannot start: Claude Code `2.1.4[85 chars]alse) (#151)
- [x] C10.10 **new** — `python hooks/probe.py <a temporary folder> <a missing folder>` prints
      "written <the first>" and "refused <the second>", in that order, exits 0, and leaves the
      temporary folder empty.
      Red today: `hooks/probe.py` does not exist.
      Test: `ProbeTest.test_written_and_refused`.
      Evidence: `ProbeTest.test_written_and_refused` (#152).
      seen red: python -m unittest tests.test_probe tests.test_reach_live on main → AssertionError: False is not true : hooks/probe.py does not exist (#152)
      broken: the probe prints written for a folder it cannot write (C10.10) → AssertionError: Tuples differ: (0, ['written <tmp>', 'written <tmp>/missing'], []) != (0, ['written <tmp>', 'refused <tmp>/missing'], []) (#152)
- [x] C10.11 **new** — With the container keys and the fake `docker`'s probe printing
      `written /driver/hooks` and the expected line for the other five, `--once` prints "cannot
      start: the session's container can write `/driver/hooks`" on stderr and exits 2; no issue is
      opened or commented, the run log has no line, and no `run` named `driver-<uuid>` was asked of
      the fake. The probe's `run` had the name `driver-probe-<uuid>`, no `-i`, the six mounts of
      C10.2 and the inner command of In scope.
      Red today: no probe runs; the session starts.
      Test: `ReachCheckTest.test_writable_hooks_refuse`.
      Evidence: `ReachCheckTest.test_writable_hooks_refuse` (#152; its break recorded again in #153, where the session runs in the container).
      seen red: python -m unittest tests.test_reach_check on main → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`\n') != (2, '') (all four tests fail on `main`: `FAILED (failures=5)`, the fifth a subtest) (#152)
      broken: a written folder that must refuse not read (C10.11) → AssertionError: Tuples differ: (1, 'park: the session ended without a res[59 chars])\n') != (2, '') (#153)
- [x] C10.12 **new** — As C10.11, the probe printing `refused /state/refusals`: "cannot start: the
      session's container cannot write `/state/refusals`", exit 2; with `<state>/refusals` and
      `<state>/claude` missing before the run, both exist after it, though the probe made nothing.
      The probe exiting 1 with "python: not found" as its last stderr line: "cannot start: the
      session's container cannot run the probe: python: not found"; printing five lines and
      exiting 0: the same line ending "exit 0".
      Red today: as C10.11.
      Test: `ReachCheckTest.test_unwritable_log_refuses`, `ReachCheckTest.test_probe_failure_refuses`.
      Evidence: `ReachCheckTest.test_unwritable_log_refuses`, `ReachCheckTest.test_probe_failure_refuses` (#152; two breaks recorded again in #153).
      seen red: python -m unittest tests.test_reach_check on main → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`\n') != (2, '') (all four tests fail on `main`: `FAILED (failures=5)`, the fifth a subtest) (#152)
      broken: a refused folder that must write not read (C10.12) → AssertionError: Tuples differ: (1, 'park: the session ended without a res[63 chars], []) != (2, '', ["cannot start: the session's cont[34 chars]s`"]) (#153)
      broken: the mounted folders not made before the probe (C10.12) → AssertionError: Tuples differ: ([], [False, False]) != ([], [True, True]) (#152)
      broken: a probe that printed too few lines believed (C10.12) → AssertionError: Tuples differ: (1, 'park: the session ended without a res[63 chars], []) != (2, '', ["cannot start: the session's cont[32 chars] 0"]) (#153)
- [x] C10.13 **new** — `on` checks before each step, not only the first: with two steps to take
      and the probe passing before the first and printing `written /state` before the second,
      `on` runs the first step's session, then prints "cannot start: the session's container can
      write `/state`" and exits 2, with no second `start` line, no second `run` named
      `driver-<uuid>`, and no comment on the run's issue for the second step.
      Red today: as C10.11.
      Test: `ReachCheckTest.test_on_checks_before_each_step`.
      Evidence: `ReachCheckTest.test_on_checks_before_each_step` (#152; its break recorded again in #153).
      seen red: python -m unittest tests.test_reach_check on main → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`\n') != (2, '') (all four tests fail on `main`: `FAILED (failures=5)`, the fifth a subtest) (#152)
      broken: on not checking the reach before a step (C10.13) → AssertionError: Tuples differ: (1, 2, 2, 2) != (2, 1, 1, 2) (#153)
- [x] C10.14 **new** — Live: the test first checks that `hooks/probe.py` exists (before any skip,
      so that on `main` it fails), then, run only when `DRIVER_CONTAINER_IMAGE` is set, calls
      `driver.box.reach` with this repository's folders, a scratch state folder and a scratch
      clone as the project, and gets `None`: the probe printed `refused` for the first three and
      `written` for the last three.
      Red today: `hooks/probe.py` does not exist: AssertionError before the skip.
      Test: `ReachLiveTest.test_reach_in_the_container`.
      Evidence: `ReachLiveTest.test_reach_in_the_container`, run with `DRIVER_CONTAINER_IMAGE=agentic-workflow-driver-session:2.1.322` on this machine (#152); CI skips its Docker part.
      Live, so not replayed: CI and the replay have no image; a reader checked the live run and its break in #152: with `/driver/hooks` mounted writable, the test failed twice with "cannot start: the session's container can write `/driver/hooks`". `break.py` refuses that report (a container path reads as absolute), so it has no manifest entry.
      seen red: python -m unittest tests.test_probe tests.test_reach_live on main → AssertionError: False is not true : hooks/probe.py does not exist (#152)
- [x] C10.15 **new** — With the container keys, `driver.once.run` driven in-process on a fake
      session that opens a pull request prints "opened: #5 from `day-01/track-a-x`" as without
      them; the fake `docker` was asked one `run` named `driver-<uuid>`, whose list is
      `driver.box.command(...)` around `claude -p` with today's flags, `--settings
      /state/container-settings.json`, `--append-system-prompt-file /driver/rules/session.md` and
      `--session-id <uuid>`; the run log's `start` and `pid` lines end with
      `"container": "driver-<uuid>"`, and `start`'s `claude` is the image's version line.
      Red today: the session starts with the PC's `claude` and no `docker`; no `container` key.
      Test: `BoxSessionTest.test_session_runs_in_the_container`.
      Evidence: `BoxSessionTest.test_session_runs_in_the_container` (#153).
      seen red: python -m unittest tests.test_box_session.BoxSessionTest.test_session_runs_in_the_container on main → AssertionError: Tuples differ: (0, True, [{'args': ['-p', '--model', 'opus', '--out[783 chars]d>']) != (0, True, [], ['driver-probe-<uuid>', 'driver-<uuid>']) (#153)
      broken: the start line's claude read from the PC, not the image → AssertionError: Lists differ: [('st[38 chars]'2.1.170 (Claude Code)'), ('pid', ['container'[21 chars]one)] != [('st[38 chars]'2.1.322 (Claude Code)'), ('pid', ['container'[21 chars]one)] (#153)
      broken: the session's container not named for its session → AssertionError: Tuples differ: (0, True, [], ['driver-probe-<uuid>', 'driver-other-<uuid>']) != (0, True, [], ['driver-probe-<uuid>', 'driver-<uuid>']) (#153)
- [x] C10.16 **new** — As C10.15, on a fake whose first run ends at the usage limit, its
      transcript written to `<state>/claude/projects/-work/<session>.jsonl`, and whose second run
      opens a pull request: the driver waits and resumes, the second `run` with `--resume` in
      place of `--session-id` inside the container's list and the same name; and a fix's resume
      through `driver.loop.resume` (C06's red-checks fake) also runs as `docker run` with
      `--resume`. A limit transcript under `CLAUDE_CONFIG_DIR` and none under `<state>/claude`
      starts no wait.
      Red today: as C10.15; and `limit_reset` reads only `CLAUDE_CONFIG_DIR`.
      Test: `BoxSessionTest.test_limit_read_from_the_state`, `BoxSessionTest.test_resumes_in_the_container`.
      Evidence: `BoxSessionTest.test_limit_read_from_the_state`, `BoxSessionTest.test_resumes_in_the_container` (#153).
      seen red: python -m unittest tests.test_box_session.BoxSessionTest.test_limit_read_from_the_state on main → AssertionError: Tuples differ: (0, False, True) != (0, True, True) (#153)
      seen red: python -m unittest tests.test_box_session.BoxSessionTest.test_resumes_in_the_container on main → AssertionError: Tuples differ: (0, []) != (0, [[], []]) (#153)
      broken: the usage limit read from CLAUDE_CONFIG_DIR with the container keys → AssertionError: Tuples differ: (0, False, True) != (0, True, True) (#153)
- [x] C10.17 **hold** — Without the container keys, the usage limit is read as Day 9 built it:
      `python -m unittest tests.test_usage_limit` passes with the file unedited.
      Evidence: the command above passes, `tests/test_usage_limit.py` unedited since `495bf69` (#153).
      broken: the resumed session read as any outcome, not the limit again (C09.2) → AssertionError: Tuples differ: (1, 2, ['park: the session ended in an error: `unknown` (session `<uuid>`)'], 1) != (1, 2, ['park: the usage limit was reached (session `<uuid>`)'], 1) (#153)
- [x] C10.18 **hold** — Without the container keys, the run log's lines keep their keys:
      `python -m unittest tests.test_runlog tests.test_runlog_fix tests.test_once_outcome` passes
      with the files unedited.
      Evidence: the command above passes, the three files unedited since `495bf69` (#153).
      broken: run_session writes no pid line → AssertionError: 1 != 0 (#153)
      broken: begin writing no issue on the start line → AssertionError: Tuples differ: (0, 1, False) != (0, 1, True) (#153)
- [x] C10.19 **hold** — Without the container keys the driver never runs Docker: on a config with
      neither key, `--once` and `on` run with a `--docker` that records every call and exits 1,
      reach the outcomes of the first case in `tests/test_once_run.py` and in `tests/test_on.py`,
      and the fake records no call. True since Track A added `--docker`; Track D1 adds the test
      and breaks it once (D10.12).
      Test: `BoxSessionTest.test_no_keys_no_docker`.
      Evidence: `BoxSessionTest.test_no_keys_no_docker` (#153); the tag changed to `hold` in #154 (D10.12).
      seen red: python -m unittest tests.test_box_session.BoxSessionTest.test_no_keys_no_docker on 495bf69 → FAILED (errors=1) (#153)
      broken: docker asked without the container keys → AssertionError: Tuples differ: (0, True, [['--version']]) != (0, True, []) (#153)
- [x] C10.20 **new** — As C10.15, on a fake session that sleeps until the fake `docker` is asked
      `kill driver-<uuid>`, then exits by itself: past `--session-minutes` the fake records that
      `kill`, its `run` records that it ended by itself (not by the tree kill), and the park line is
      as without the container; on an open STOP issue, the same, and the halt file names the STOP
      issue as without the container.
      Red today: no `docker kill` is asked; the session is ended by the tree kill.
      Test: `BoxKillTest.test_bound_kills_the_container`, `BoxKillTest.test_stop_kills_the_container`.
      Evidence: `BoxKillTest.test_bound_kills_the_container`, `BoxKillTest.test_stop_kills_the_container` (#155).
      seen red: python -m unittest tests.test_box_kill tests.test_box_halt tests.test_box_recovery.BoxRecoveryTest.test_running_container_waits on main → AssertionError: Tuples differ: (1, False, False, False) != (0, True, True, False) (#155)
      broken: the bound's kill left the container running → AssertionError: Tuples differ: (1, True, False, []) != (1, True, True, [{'ended': 'itself'}]) (#155)
      broken: the STOP's kill left the container running → AssertionError: Tuples differ: (1, False, [], True) != (1, True, [{'ended': 'itself'}], True) (#155)
- [x] C10.21 **new** — `run-steps.py halt --docker <fake>` on a state with no lock whose run log's
      newest `pid` line names `"container": "driver-s1"`, a pid that is gone, and no later `end`:
      with the fake's `kill` exiting 0, `halt` prints exactly "halt: set; killed container
      `driver-s1` of session `s1`" and exits 0, and asks no `inspect`; with `kill` failing "Error
      response from daemon: cannot kill container: driver-s1: No such container: driver-s1",
      exactly "halt: set; no driver is running"; failing "permission denied", "halt: set; could not
      kill container `driver-s1`: permission denied" and then "halt: set; no driver is running".
      Red today: `halt` runs no `docker kill`; it prints "halt: set; no driver is running" alone.
      Test: `BoxHaltTest.test_halt_kills_the_container`, `BoxHaltTest.test_halt_container_gone`.
      Evidence: `BoxHaltTest.test_halt_kills_the_container`, `BoxHaltTest.test_halt_container_gone` (#155).
      seen red: python -m unittest tests.test_box_kill tests.test_box_halt tests.test_box_recovery.BoxRecoveryTest.test_running_container_waits on main → AssertionError: Tuples differ: (1, False, False, False) != (0, True, True, False) (#155)
      broken: halt killed no container → AssertionError: Tuples differ: (0, ['halt: set; no driver is running'], []) != (0, ['halt: set; killed container `driver-s1` of session `[26 chars]1']]) (#155)
      broken: halt said a container already gone → AssertionError: Tuples differ: (0, ['halt: set; could not kill container `driver-s1`: Err[120 chars]ng']) != (0, ['halt: set; no driver is running']) (#155)
- [x] C10.22 **new** — Recovery waits on a running container: with the container keys, a run log
      whose newest `pid` line names `"container": "driver-s1"` and a pid that is gone, with the
      fake's `inspect` printing "true", makes `--once` print "wait: session `s1` is still running
      (container `driver-s1`)" and exit 0, starting nothing.
      Red today: a gone pid is a gone session; the crash park is printed.
      Test: `BoxRecoveryTest.test_running_container_waits`.
      Evidence: `BoxRecoveryTest.test_running_container_waits` (#155).
      seen red: python -m unittest tests.test_box_kill tests.test_box_halt tests.test_box_recovery.BoxRecoveryTest.test_running_container_waits on main → AssertionError: Tuples differ: (1, False, False, False) != (0, True, True, False) (#155)
      broken: Recovery parked on a running container → AssertionError: Tuples differ: (1, False, False, False) != (0, True, True, False) (#155)
- [x] C10.23 **hold** — Without a `container` on the `pid` line, sessions are killed and Recovery
      reads as before: `python -m unittest tests.test_session_bound tests.test_once_stop
      tests.test_halt tests.test_halt_race tests.test_once_halt tests.test_recovery_table
      tests.test_runlog_recovery` passes with the files unedited.
      Evidence: the command above passes, the seven files unedited since `495bf69` (#155).
      broken: the kill past the bound removed → AssertionError: True is not false : a process of the session still runs (#155)
- [x] C10.24 **new** — `driver.status.level_2_run` over, oldest first, a container session `c1`
      (its `start` line with `container`) whose `end` says "opened: #5 from `x`", a PC session
      `p1` (no `container`) whose `end` says "opened: #6 from `y`", `merged` #6 (changed false),
      `merged` #5 (changed false), gives 1; with the two `merged` lines in the other order, 0; and
      a log of one `merged` line for #9 (changed false) and no session lines gives 0.
      Red today: every `merged` line with `changed` false counts: 2, 2 and 1.
      Test: `Level2ContainerTest.test_only_container_sessions_count`.
      Evidence: `Level2ContainerTest.test_only_container_sessions_count` (#157).
      seen red: python -m unittest tests.test_level_2_container on main → AssertionError: 2 != 1 (#157)
      broken: level_2_run counts a merge whatever session opened it, container or not → AssertionError: 2 != 1 (#157)
      Replaces: C08.10 — was: a `merged` line with `changed` false counts whichever session opened its pull request, and a log of `merged` lines alone counts them.
      Replaces: C09.14 — was: `level_2_run` over two `merged` lines with `"changed": false` and no session lines gives 2.
- [x] C10.25 **hold** — The rest of C08.10 and C09.14 holds: `status` prints, under "refusals: 3",
      "  2 Bash: {"command": "git push --force"}" and "  1 Edit: {}"; after the `cost` line,
      "level 2: <k> of 15 pull requests in a row merged without a change asked", 0 for a log with
      no `merged` line; a `closed` line, a `merged` line with `changed` `null` or absent, and
      `driver/loop.py`'s "still red after two fixes" park each end the count. `tests/test_status_trial.py`,
      `tests/test_level_2_sentence.py` and `scripts/test_driver_runs.py` pass with their logs given
      a container `start` and an "opened" `end` line for each counted `merged` pull request, and
      no other edit; `tests/test_status.py` passes unedited.
      Evidence: `StatusTrialTest.test_count_ends`, `Level2SentenceTest`, `python scripts/test_driver_runs.py` and `tests/test_status.py` pass, the last unedited since `495bf69` (#157).
      broken: a closed line no longer ends the level 2 count → AssertionError: 'level 2: 3 of 15 pull requests in a row merged without a change asked' != 'level 2: 1 of 15 pull requests in a row merged without a change asked' (#157)
- [x] C10.26 **new** — `status` on `docs/trial/run.jsonl` (the Day 8 trial's log, its sessions run
      on the PC) prints "level 2: 0 of 15 pull requests in a row merged without a change asked";
      `docs/trial/day-08.md` is not edited, and its `cost` line is still the one `status` gives.
      `TrialRecordTest.test_cost_line_is_status` compares the `cost` line and checks the level 2
      line against this criterion's.
      Red today: `status` prints "level 2: 3 of 15 ...".
      Test: `TrialRecordTest.test_cost_line_is_status`.
      Evidence: `TrialRecordTest.test_cost_line_is_status` (#157); `docs/trial/day-08.md` unedited since `495bf69`.
      seen red: python -m unittest tests.test_trial_record.TrialRecordTest.test_cost_line_is_status on main → AssertionError: 'level 2: 3 of 15 pull requests in a row merged without a change asked' != 'level 2: 0 of 15 pull requests in a row merged without a change asked' (#157)
      broken: level_2_run skips the container check → AssertionError: 'level 2: 3 of 15 pull requests in a row merged without a change asked' != 'level 2: 0 of 15 pull requests in a row merged without a change asked' (#157)
      Replaces: C08.12 — was: the record's `cost` and level 2 lines are both those `status` gives on the copy of the run log ("level 2: 3 of 15").
- [x] C10.27 **new** — `setup_check.protection_lines` with classic protection whose
      `enforce_admins.enabled` is false and no rules gives
      `("FAIL", 'main: administrators may bypass the rules; turn on "Do not allow bypassing the above settings"')`
      right after the pull request line; with it true, `("ok", "main: no one may bypass the
      rules")` there; with main unprotected (404) and no rules, the FAIL line.
      Red today: no line names bypassing; the list is one line shorter.
      Test: `BypassTest.test_classic_enforce_admins`.
      Evidence: `BypassTest.test_classic_enforce_admins` (#158).
      seen red: python -m unittest tests.test_setup_bypass on main → AssertionError: 10 != 11 (#158)
      broken: classic enforce_admins ignored → AssertionError: Tuples differ: ('FAIL', 'main: administrators may bypass t[58 chars]gs"') != ('ok', 'main: no one may bypass the rules') (#158)
- [x] C10.28 **new** — With no classic protection (404) and a `pull_request` rule with
      `"ruleset_id": 7`: `repos/<repo>/rulesets/7` giving `"bypass_actors": []` gives the ok line;
      one actor, the FAIL line; no `bypass_actors` key, `("FAIL", "main's ruleset 7: cannot read:
      bypass_actors not shown (needs admin)")`; a 403, `("FAIL", "main's ruleset 7: cannot read:
      no permission (needs admin)")`.
      Red today: as C10.27.
      Test: `BypassTest.test_ruleset_bypass_actors`.
      Evidence: `BypassTest.test_ruleset_bypass_actors` (#158).
      seen red: python -m unittest tests.test_setup_bypass on main → AssertionError: 10 != 11 (#158)
      broken: ruleset bypass_actors read the other way → AssertionError: Tuples differ: ('ok', 'main: no one may bypass the rules') != ('FAIL', 'main: administrators may bypass t[58 chars]gs"') (#158)
- [x] C10.29 **hold** — The other lines stay: `python scripts/test_setup_check.py` passes with
      only these edits, in the seven tests the bypass line reaches: its fake's protection answers
      given `"enforce_admins": {"enabled": true}`; `fake()`'s `keys` given the path
      `repos/<repo>/rulesets/<id>` and its ruleset test a `ruleset_id` and an answer with
      `"bypass_actors": []`; and `test_an_unprotected_main_fails_each_required_check_by_name`'s
      count `len(setup_check.REQUIRED) + 2` made `+ 3`. `tests.yml` does not run it;
      `spec-drift-tests.yml` runs every `scripts/test_*.py`.
      Evidence: the command above passes with the seven tests' edits alone (#158); broken once at the close, which #158 had not done (D10.21).
      broken: the bypass line put in place of the pull request line → AssertionError: 10 != 11
- [x] C10.30 **new** — Live: one step of the trial's project ran in the container. In
      `docs/trial/day-10.md`: the run log's `start`, `pid` and `end` lines with
      `"container": "driver-<session>"`; the `end` line's outcome "opened: #<n> from `<branch>`"
      and its `cost_usd`; the pull request's URL and its head commit's author name, the image's
      `GIT_NAME` (`gh pr view <n> --json commits`), which the PC's `git config user.name` is not;
      and `git status --short` in the project's checkout on the PC, empty after it.
      Red today: no session has run in the container; `docs/trial/day-10.md` does not exist.
      Test: `TrialTenTest.test_record_names_the_container_run` (reads the record's lines).
      Evidence: `TrialTenTest.test_record_names_the_container_run` (#159): bearing #101, opened from the container, its head commit's author `Driver session`.
      seen red: python -m unittest tests.test_trial_ten on main → AssertionError: docs/trial/day-10.md does not exist (#159)
      broken: the record's head commit author set to the PC's user → AssertionError: 'Yusuprozimemet' != 'Driver session' (#159)
- [x] C10.31 **hold** — The files Days 8 to 10 do not change are unchanged since `495bf69`:
      Verify's diff prints nothing. Its list is C08.1's with `driver/settings.py` and `hooks`
      taken out (Day 9's Tracks B1 and B2 edited `driver/settings.py`, `hooks/guard.py` and
      `hooks/halt.py` and added `hooks/hook_log.py`; Tracks A and C2 here edit `settings.py` and
      add `hooks/probe.py`), and `driver/config.py` (Track A) and `driver/preflight.py` (Track C1)
      taken out.
      broken: a byte added to driver/decide.py → import re (#148)
      Evidence: `git -c core.safecrlf=false diff --exit-code 495bf69` over Verify's list prints nothing on `main` at `03bb9e9` (#148).
      Replaces: C08.1 — was: the files Day 8 does not change are unchanged since `f9f43fd`, over a list that holds `driver/settings.py`, `driver/config.py`, `driver/preflight.py` and `hooks`.
- [x] C10.32 **hold** — Recovery parks on a stopped container as on a gone pid: with the container
      keys, the run log of C10.22, and the fake's `inspect` printing "false" or exiting 1 with
      "error: no such object: driver-s1", `--once` prints Day 7's crash park, "park: the run log
      names session `s1` for this step, with no end", exits 1 and prints no wait line. True on
      `main` since Day 7; Track D2 adds the test and breaks it once (D10.13).
      Test: `BoxRecoveryTest.test_stopped_container_parks`.
      Evidence: `BoxRecoveryTest.test_stopped_container_parks` (#155); split from C10.22 and tagged `hold` in #156 (D10.13).
      broken: Recovery waited on a stopped container → AssertionError: Tuples differ: (0, False, ['wait: session `s1` is still running (container `driver-s1`)']) != (1, True, []) (#155)

## Verify
```bash
python -m unittest tests.test_box_config tests.test_box_command tests.test_image_files tests.test_image_live tests.test_box_preflight tests.test_probe tests.test_reach_check tests.test_reach_live tests.test_box_session tests.test_box_kill tests.test_box_halt tests.test_box_recovery tests.test_level_2_container tests.test_setup_bypass tests.test_trial_ten tests.test_trial_record tests.test_config tests.test_hooks tests.test_once_run tests.test_usage_limit tests.test_runlog tests.test_runlog_fix tests.test_once_outcome tests.test_session_bound tests.test_once_stop tests.test_halt tests.test_halt_race tests.test_once_halt tests.test_recovery_table tests.test_runlog_recovery tests.test_status_trial tests.test_level_2_sentence tests.test_status -v
python scripts/test_setup_check.py
python scripts/test_driver_runs.py
git -c core.safecrlf=false diff --exit-code 495bf69 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py rules/session.md tests/test_failures.py tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_once_halt.py tests/test_live_once.py tests/test_once_stop.py
```
`tests/test_image_live.py` and `tests/test_reach_live.py` skip their Docker part unless
`DRIVER_CONTAINER_IMAGE` is set; on this machine, with the image built as `docs/container.md`
says, run them with the variable set as well.

Where the tests live: `ContainerConfigTest` in `tests/test_box_config.py`; `BoxCommandTest` in
`tests/test_box_command.py`; `ImageFilesTest` in `tests/test_image_files.py`; `ImageLiveTest` in
`tests/test_image_live.py`; `BoxPreflightTest` in `tests/test_box_preflight.py`; `ProbeTest` in
`tests/test_probe.py`; `ReachCheckTest` in `tests/test_reach_check.py`; `ReachLiveTest` in
`tests/test_reach_live.py`; `BoxSessionTest` in `tests/test_box_session.py`; `BoxKillTest` in
`tests/test_box_kill.py`; `BoxHaltTest` in `tests/test_box_halt.py`; `BoxRecoveryTest` in
`tests/test_box_recovery.py`; `Level2ContainerTest` in `tests/test_level_2_container.py`;
`TrialRecordTest` in `tests/test_trial_record.py` (Day 8's, edited by Track E); `BypassTest` in
`tests/test_setup_bypass.py`; `TrialTenTest` in `tests/test_trial_ten.py`. The fake `docker` is
`tests/fake_docker.py` (Track C1).

## Notes
- Picks up H09.1: C10.11–C10.14 check from inside the container that `<state>/refusals` is
  writable and the driver's hooks, its rules and the halt file's folder are not, and C10.16
  reads the usage limit from the container's Claude Code folder. D09.2 is the Defect behind H09.1,
  not a hand-off; `spec-drift.py` lists it with Day 10 because it names the day. D09.21's "Day 10"
  is this repository's: Day 9's Phase 2 plan-auditor's fourth finding (#140: which
  `setup-check.py` reports the bypass line, and how `enforce_admins` is read), which Track F
  answers (C10.27–C10.29). The "Day 10" in `scripts/spec_drift_specs.py:417` and
  `scripts/test_spec_drift.py:1629` and `:1728` is bearing's and hands nothing here. H09.2 stays
  Day 13's; H09.3 stays the maintainer's.
- The first draft of this day (a second Windows account) was audited before any work and dropped
  for the container (`plan.md`, "Course corrections", 2026-11-11). From that audit, carried here:
  a STOP kills in `stop_session`, not `kill_session` (C10.20); `halt` has a second kill, of the
  run log's live session, besides the lock's (C10.21); `on` checks before each step, not only the
  first (C10.13); the bypass line reaches tests in `scripts/test_setup_check.py`, which CI runs
  (C10.29: seven, the second audit counted); a ruleset with no `bypass_actors` is a FAIL, not an
  ok (C10.28); and the transcripts' folder is wired into both reads, not only accepted by
  `limit_reset` (C10.16).
- Why the count ends at a pull request no container session opened, rather than passing over it:
  the 15 are "in a row" (`plan.md`, Levels), and a run that mixes PC and container sessions has
  not shown the container's setup 15 times running. The Day 8 trial's 3 do not count (`plan.md`,
  the maintainer's choice on #147), so `status` on its log now says 0 (C10.26); its record keeps
  the 3 it printed then.
- Why `--mount` and not `-v`: a Windows source holds a drive letter's colon, which `-v` reads as a
  separator; `--mount` names source and target by key.
- Why the hooks and the rules are mounted and not the driver's folder: the folder holds `.env`,
  `driver.json`, `.git` and `.claude/`, none of which a session needs, and `plan.md` lists only
  "the driver's hooks, its rules and the settings file". The settings file is in `<state>`.
- Why `driver-probe-<session>` and not `driver-<session>`: the probe's container is gone before
  the session's starts (`--rm`), but a name of its own keeps a slow removal from refusing the
  session's `run` ("Conflict. The container name ... is already in use"). The session's uuid is
  made before the probe for this, and given to `begin()`.
- The file the probe writes in `/work` is removed before the session starts; a probe killed
  between the two leaves it, and Day 7's clean-tree check then parks the next start.
- `guard.py`, given `/driver`, refuses a session's command with a `/driver` path segment
  (`/driver(?![\w.-])`); bearing at `c214b09` has no such path.
- Track C was split into C1 and C2 because the preflight, the probe, the fake and the edits to
  `on` and `--once` together would pass 400 lines (Day 9's Track A measured 360 for one wait and
  resume).
- **Assumed** — Docker Desktop runs on this machine: `docker version --format {{.Server.Version}}`
  → 29.4.3 (2026-11-11). CI's Linux runners have Docker, but no test except C10.7, C10.14 and
  C10.30 runs it.
- **Assumed** — the six mounts on Windows: a throwaway `python:3.12.15-slim` container refused
  writes to `/driver`, `/driver/hooks` and `/state`, and wrote `/work`, `/state/refusals` and
  `/claude` (spec-auditor, 2026-11-11). The spike's results (pipes, the halt hook from a
  read-only mount, `docker kill` ending `claude -p`, the transcript at `projects/-work/`) were
  shown with the spike's image (`plan.md`); C10.14 and C10.30 show them again with this day's.
- **Assumed** — killing the `docker` client leaves the container running (`plan.md`, spike), so
  `kill_session` and `stop_session` need `docker kill` first: shown on 2026-11-11.
- **Assumed** — `docker kill` of a missing container prints "Error response from daemon: cannot
  kill container: X: No such container: X" and exits 1; `docker inspect` of one prints "error: no
  such object: X" and exits 1 (spec-auditor, Docker 29.4.3, 2026-11-11). `docker version` with the
  daemon down: not run; Track C1 runs it with Docker Desktop stopped and quotes its last stderr
  line in the PR.
- **Assumed** — GitHub leaves `bypass_actors` out of `repos/<repo>/rulesets/<id>` for a caller
  without admin rights: `gh api repos/github/docs/rulesets/<id>` → `has("bypass_actors")` false for
  all three, `current_user_can_bypass` "never" (spec-auditor, gh 2.93.0, 2026-11-11). bearing has
  no ruleset (`gh api repos/Yusuprozimemet/bearing/rulesets --jq length` → 0).
- **Assumed** — bearing's `main` today: `gh api repos/Yusuprozimemet/bearing/branches/main/protection
  --jq .enforce_admins.enabled` → false (2026-11-11); `setup-check.py --repo
  Yusuprozimemet/bearing` prints C10.27's FAIL line until the maintainer turns on "Do not allow
  bypassing the above settings".
- **Assumed** — the push with the fine-grained token from the container, and a whole step there:
  not run (`plan.md`, "Unverified"); C10.30 is the run that shows them.
- **Defect** D10.1 — found: dashboard · cause: spec · made: Day 09 · C08.1 held `driver/settings.py`
  and `hooks` unchanged since `f9f43fd`, but Day 9's Tracks B1 and B2 edited `driver/settings.py`,
  `hooks/guard.py` and `hooks/halt.py` and added `hooks/hook_log.py` (97 insertions) with no
  `Replaces:` line, so the replay reports C08.1 broken; C10.31 replaces it over the list without
  them (this spec-change PR).
- **Defect** D10.2 — found: auditor · cause: spec · made: Day 10 · the container mounted the whole
  driver folder, `.env`, `driver.json` and `.git` with it, where `plan.md` mounts only the hooks,
  the rules and the settings file; now `<home>/hooks` and `<home>/rules` (this spec-change PR).
- **Defect** D10.3 — found: auditor · cause: spec · made: Day 10 · Track E's count also changes
  C08.12's level 2 line and `scripts/test_driver_runs.py`'s, with no `Replaces: C08.12`; now
  C10.26 replaces it and C10.25 names both files (this spec-change PR).
- **Defect** D10.4 — found: auditor · cause: spec · made: Day 10 · the bypass line was said to
  change five tests by their fake alone; it changes seven, one by its count and the fake by a new
  path (C10.29) (this spec-change PR).
- **Defect** D10.5 — found: auditor · cause: spec · made: Day 10 · the live tests skipped on
  `main` once Track A had added `driver/box.py`, so they could not be seen red; each now checks
  its own track's file before the skip (C10.7, C10.14) (this spec-change PR).
- **Defect** D10.6 — found: auditor · cause: spec · made: Day 10 · C10.19 (then C10.29) was tagged
  `hold` but fails until Tracks A and D1; now `new` (this spec-change PR).
- **Defect** D10.7 — found: auditor · cause: spec · made: Day 10 · `halt`'s output for a container
  session whose pid is gone was unsaid, and its kill of that pid printed a pid that differed by
  system; now `live_container` and C10.21's exact lines, and `live_session` keeps its pid rule
  (this spec-change PR).
- **Defect** D10.8 — found: auditor · cause: spec · made: Day 10 · the probe was named after a
  session uuid made only later, in `begin()`; now made before the probe (this spec-change PR).
- **Defect** D10.9 — found: auditor · cause: spec · made: Day 10 · Day 2's checks in the image
  need `driver/preflight.py`, which the frozen list held, and their lines and order were unsaid;
  now unfrozen, worded, and the Docker checks stop at the first (C10.8, C10.9) (this spec-change PR).
- **Defect** D10.10 — found: auditor · cause: spec · made: Day 10 · `token-usage.py` was to count
  the container's transcripts, but it keeps only folders named after this repository's path;
  now Track G reads the cost from the run log, and the count is Day 13's (H10.2) (this
  spec-change PR).
- **Defect** D10.11 — found: auditor · cause: spec · made: Day 10 · the image's base and Python
  were not the spike's: bookworm's system Python refuses `pip install`, and no user was named; now
  trixie, `/opt/venv` and `USER node`, as the spike's (this spec-change PR).
- **Defect** D10.12 — found: seen red · cause: spec · made: Day 10 · D10.6 tagged C10.19 `new` for a
  red that lasted only until Track A: once `--docker` was accepted, the driver ran no Docker
  without the keys, so the test passed on `main` before Track D1, and "Track tests seen red"
  failed D1's PR (#153) on it. Now `hold`; its red before Track A was seen on 495bf69
  (`SystemExit: 2`), and #153 breaks it once ("docker asked without the container keys").
- **Defect** D10.13 — found: seen red · cause: spec · made: Day 10 · C10.22 was tagged `new` over
  two tests, but its second half, the crash park on a stopped or missing container, is Day 7's
  row unchanged, so `BoxRecoveryTest.test_stopped_container_parks` passed on `main` and "Track
  tests seen red" failed Track D2's PR (#155) on it. That half is now C10.32, `hold`; #155 breaks
  it once ("Recovery waited on a stopped container").
- **Hand-off** H10.1 → Day 12: `live-check` runs on the PC's Claude Code; the image is only
  checked to be at a version it listed (C10.9). Whether the level 2 merge needs `live-check` run in
  the image is Day 12's call.
- **Hand-off** H10.2 → Day 13: the container's transcripts are in `<state>/claude/projects/-work/`,
  which `scripts/token-usage.py` and `scripts/publish-counts.py` do not read; the level 2 record's
  cost needs them counted, and `plan.md`'s "Unverified" item on it stays open until then.
- **Defect** D10.14 — found: review · cause: implementation · made: Day 10 · the implementer's
  `setUp` in `tests/test_box_command.py` imported `driver.box` for every test, so on `main` the
  settings and `--docker` tests failed on the missing module, not on their own red; the import
  moved into the one test that uses it (#149).
- **Defect** D10.15 — found: break on purpose · cause: implementation · made: Day 10 · the mounts
  test built its expected paths with `os.path.join`, so a break's report held `\` on Windows and
  `/` on Linux, which CI's replay would not match; the comparison now writes `/` (#149).
- **Defect** D10.16 — found: break on purpose · cause: implementation · made: Day 10 · the first
  settings break's report held the container path `/driver/hooks`, which `scripts/break.py`
  refuses as absolute; the break now renames the file, and the assertion compares the name (#149).
- **Defect** D10.17 — found: break on purpose · cause: environment · made: none · same-as: D05.5 ·
  Git Bash rewrote `--find 'target=/state,...'` and `--find "source=<state>/claude,..."` into
  Windows paths, so breaks in #149 and #150 found nothing until run with `MSYS_NO_PATHCONV=1`.
- **Defect** D10.18 — found: Track A · cause: implementation · made: Day 09 ·
  `UsageLimitTest.test_far_reset_parks` fails on and off under `scripts/test-parallel.py`, the
  driver's exit code still `None` when the test reads it: once each in #149, #150 and #152, each
  time passing alone and under `--repeat`. No file of Day 10 touches its path.
- **Defect** D10.19 — found: break on purpose · cause: process · made: Day 10 · Track B's brief let
  the file test use `assertIn` and `assertNotIn`, which print the whole file into the failure, so
  `scripts/break.py` refused the first two reports (absolute paths from the Dockerfile's text); the
  test now asserts with its message alone (#150).
- **Defect** D10.20 — found: break on purpose · cause: implementation · made: Day 10 · C10.11's
  test first failed on a line holding `/driver/hooks`, and C10.13's on one holding the session's
  uuid, both of which `scripts/break.py` refuses; the tests now compare the exit code and counts
  first (#152).
- **Defect** D10.21 — found: close · cause: process · made: Day 10 · C10.29, a `hold`, was never
  broken on purpose: #158 broke C10.27 and C10.28 only. The close broke it once ("the bypass line
  put in place of the pull request line") and added it to the manifest.
- **Defect** D10.22 — found: seen red · cause: implementation · made: Day 10 · C10.19's test
  imported `driver.box` at the top of the module, so on `495bf69` it failed on the import, not on
  the spec's `SystemExit: 2`; the import moved into the one test that uses it (#153).
- **Defect** D10.23 — found: Track E · cause: spec · made: Day 10 · In scope says a counted
  session's outcome "starts 'opened: #<pr> '", with a trailing space, which `scripts/test_driver_runs.py`'s
  "opened: #12" end line does not have; the code matches `opened: #(\d+)` and compares the number,
  as `driver/loop.py` reads it, which still tells #5 from #50 (#157, a departure recorded there).
- **Defect** D10.24 — found: self · cause: process · made: Day 10 · Track G's first `--once` was
  refused, "the driver's repository has changes: `tests/test_trial_ten.py`": the track's test was
  left uncommitted in the driver's folder; it was stashed and the run started again (#159).
- **Defect** D10.25 — found: self · cause: process · made: Day 10 · the first draft of
  `docs/trial/day-10.md` said the `end` line's one refusal was bearing's read guard on a Read with
  no range; the transcript shows the Read had `limit` 200 and returned the file, so the record now
  says the CLI counted a denial for a call that ran, cause unknown (#159).
- #153 rewrote three of Day 7's and Day 9's breaks' finds (`ruff format` split the `begin` call once
  `container=` was added) and recorded them again under their names: "run_session writes no pid
  line", "begin writing no issue on the start line" and "the resumed session read as any outcome,
  not the limit again (C09.2)". Day 7's and Day 9's manifests keep their finds, which replay at
  their own closing commits. #152 and #153 likewise recorded again the C1 and C2 breaks whose
  reports had changed; the criteria above carry the newest report of each, and the manifest each
  name once.
- C10.7 and C10.14 are live: their Docker part skips in CI and in the replay. At the close both
  passed on this machine with `DRIVER_CONTAINER_IMAGE=agentic-workflow-driver-session:2.1.322`.
- Track G opened bearing #101 from the container and left it open for the maintainer; its record
  is `docs/trial/day-10.md`.
- **Defect** D10.26 — found: evidence replay · cause: spec · made: Day 10 · C10.19 named
  "`tests.test_once_run`'s first case" and "`tests.test_on`'s", which the replay reads as tests
  `test_once_run` and `test_on` of a class `tests` and fails "not defined"; the close names the
  files by path, the meaning unchanged.
- The blind relabel (`scripts/relabel.py`), run again after D10.26, agreed on 26 of 26 stages,
  24 of 26 causes and 26 of 26 `made:`. Kept: D10.18 `implementation`, as the test reads the
  driver's exit code before the driver has ended, which the rater read as unclear; D10.19
  `process`, since the brief, not the implementer, allowed the assertions that print the whole
  file (as D09.22 and D09.23). The first run, on 25, also read D10.17 as `made: Day 10`; kept
  `none`, as Git Bash's path conversion is the machine's (as D05.5).
