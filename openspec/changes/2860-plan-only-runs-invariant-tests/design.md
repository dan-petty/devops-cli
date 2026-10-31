# Design

## Context

See proposal.md for the problem and the scope (#2860). The job `Tests & Coverage` is a required check of the `main` ruleset. A plan pull request holds only files under `openspec/changes/<issue>-<slug>/`. The full suite takes about 300 s to 370 s for it and checks nothing that the plan can break, except a few tests of `tests/invariants`.

## Goals / Non-Goals

**Goals:**
- A plan-only pull request runs `tests/invariants` and nothing more of the suite.
- Any other event and any other pull request runs the full suite as before.
- The required check `Tests & Coverage` reports success for a plan-only pull request.
- The rule is a path rule. No label, title or author can turn it on.

**Non-Goals:**
- Reduced runs for `docs/**` or the README. Tests read those files: the docs inventory, the claims of AGENTS.md, the links. That needs its own issue.
- A change to `devops ci test` or to the gate row.

## Decisions

### 1. One filter named for the files outside the plan

- **Decision**: The filter `outside_plan` is `'**'` with `'!openspec/changes/[0-9]*-*/**/*'`, and the action runs with `predicate-quantifier: some-with-excludes`. The output is `true` when any changed file is not a plan file. A plan-only pull request has `outside_plan == 'false'`.
- **Reason**: The action says `true` when ANY file matches. "Every file is a plan file" is the same as "no file is outside the plan".
- **Alternative: `predicate-quantifier: every` with positive patterns.** Rejected. `every` asks that one file matches ALL the patterns. The output is still true when any file matches, so it cannot say "all files".
- **Alternative: a shell step with `git diff --name-only` and `grep -v`.** Rejected. It is hand-written parsing of a file list, and the repository already pins the action for this job form in two jobs.
- **Alternative: `paths-ignore` on the workflow.** Rejected. The required checks would stay pending, and the pull request could not merge.

### 2. The plan folder is `[0-9]*-*`, not "anything but archive"

- **Decision**: The excluded pattern names the grammar of an active change folder: `<issue>-<slug>`, then at least one more path part. The archive folder starts with `archive`, a spec folder is not under `changes`, and a file directly in `openspec/changes/` has no folder. All of them stay outside the plan, so the full suite runs.
- **Alternative: `openspec/changes/!(archive)/**`.** Rejected. Node showed that it also matches a file directly in `openspec/changes/`, such as a README. A pattern that fails safe is better: a path that matches none of the plan forms runs the full suite.
- The glob `[0-9]*-*` is wider than the regex `\d+-[^/]+` of `CONST_OPENSPEC_CHANGE_NAME_RE`. A folder such as `2a-x` counts as a plan folder here. `tests/invariants/test_change_folders.py` then fails the pull request, because it names the folder wrongly. The wider glob thus costs nothing.

### 3. The reduced run is `pytest`, not `devops ci test`

- **Decision**: The step `Plan-Only Invariant Tests` runs `uv run pytest tests/invariants`.
- **Alternative: `uv run devops ci test tests/invariants/`.** Rejected. Measured: the command prints `nothing to verify` and exits 0 for a directory. A step that passes while it runs no test is a hole.
- **Alternative: `uv run devops ci test tests/invariants/test_*.py`.** Rejected. If the glob matches nothing, the shell passes the pattern as text, and the command again verifies nothing.
- **Alternative: a new option for `devops ci test` or for the gate row.** Rejected. It adds code and a changed command interface for a one-line need.
- `pytest` takes the `addopts` of `pyproject.toml`, so the reduced run uses the same workers, the same hypothesis profile and the same plugins as the full suite.

### 4. No coverage in the reduced run

- **Decision**: The reduced run has no `--cov`. The step `Changed-Line Coverage` has the extra condition `steps.changes.outputs.outside_plan != 'false'`.
- **Reason**: Coverage of `tests/invariants` alone is far under the floor `fail_under = 85`. `coverage xml` also fails when no data exists. A plan holds no Python line, so no figure can be wrong.
- **Alternative: keep the step and let it pass on empty data.** Rejected. It needs new script code to treat a missing data file as success, which could also hide a real fault in the full run.

### 5. Fail closed

- **Decision**: The gate step runs when `outside_plan != 'false'`. When the filter step is skipped (a push or a manual run), when it fails to set an output, or when it says `true`, the full suite runs. Only the exact text `false` selects the reduced run. The filter step has no `continue-on-error`, so an API failure fails the job.
- A pull request that lists more than 3000 files is cut off by the REST API. Such a list has to be all plan files in its first 3000 entries to count as plan-only. A plan of that size does not exist.

### 6. Where the contract lives

- **Decision**: `tests/invariants/test_workflow_contracts.py` gets one function that returns the problems of the job `test` and tests that call it. A second test evaluates the patterns of the filter against sample paths.
- A mutation test removes the filter, the reduced run and the extra condition one at a time, and expects a problem each time.

## Risks / Trade-offs

- [A test outside `tests/invariants` reads a plan file] -> Checked: the others use temporary directories. If one appears, it fails on the next pull request that is not plan-only, and its author moves it or widens the rule in a new issue.
- [The action changes the meaning of `some-with-excludes`] -> The action is pinned by commit, and the contract test pins the pattern and the quantifier.
- [The 150 s goal is not met on the runner] -> The setup steps (checkout with full history, the toolchain, promtool) stay. If the first plan-only run is over 150 s, a new issue narrows them. This change does not guess.
