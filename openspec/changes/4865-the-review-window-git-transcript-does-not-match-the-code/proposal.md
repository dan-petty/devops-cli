# Proposal: #4865

## Why

The git transcript of `review_window` (`tests/fixtures/git/review_window.json`) did not match the code: the two contract cases of `review_window` failed and the `git` row of `devops ci` reported a difference. The code's git read the system configuration file of the host (`/etc/gitconfig`), because `Workspace.environment()` set `HOME`, `LC_ALL` and `DEVOPS_CLI_USER_DATA_ROOT` only, while the git that builds the repository sets `GIT_CONFIG_NOSYSTEM` and `GIT_CONFIG_GLOBAL`. A recording was therefore not the same on every host. Closes #4865.

## What Changes

- `Workspace.environment()` in `tests/support/git_scenarios.py` sets `GIT_CONFIG_NOSYSTEM` at `1` and `GIT_CONFIG_GLOBAL` at `os.devnull`, as `setup_env` does for the git that builds the repository.
- `tests/core/test_git_recording.py` gains a test of that environment, a test that the `review_window` transcript holds `lizard.complexity` with status `ok` and three files, and a test that two recordings of the scenario give the same text.
- The change alters no behavior a consumer observes: it edits the test harness and its tests, so it sets `skip_specs: true`.

## Capabilities

None. The change is test infrastructure and adds no capability.

## Impact

- A recording of `review_window` is the same on every host, and the `git` row passes.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18 with git 2.55.0 and lizard 1.26.1: `uv run pytest tests/core/test_git_contract.py -k review_window` passes, and `uv run python -c "import sys; from tests.support.git_recording import main; sys.exit(main(['--check']))"` reports that the 20 transcripts match.
- The committed transcript already holds `lizard.complexity` with status `ok` and three files; a recording without the review extra records `skipped` and drops the `cat-file blob` exchanges, which the new test refuses.

## Existing Tool Considered

No open, maintained tool covers the need. The repository's own git fake and recorder (`tests/support/git_scenarios.py`, `tests/support/git_recording.py`) own it, and `git` itself gives the isolation with `GIT_CONFIG_NOSYSTEM` and `GIT_CONFIG_GLOBAL`. The change edits the harness and adds three tests.
