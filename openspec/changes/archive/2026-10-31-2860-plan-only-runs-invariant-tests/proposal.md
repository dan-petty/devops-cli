# Proposal

## Why

A pull request that only adds a plan under `openspec/changes/<issue>-<slug>/` runs the full test suite (#2860). The stage job opens one such pull request for each Ready P0 and P1 bug. On 2026-10-31 three plan pull requests ran the job `Tests & Coverage` for 361 s (#2857), 371 s (#2858) and 297 s (#2859). They hold no source or test change. AGENTS.md rule 5 treats a check that averages more than 5 minutes as a P0 bug.

`ci.yml` already scopes work by what changed. The jobs `Docs Site Build` and `Image Pins` use `dorny/paths-filter`, always run, gate their steps and report success. This change gives the job `Tests & Coverage` the same form.

## What Changes

- The job `test` of `.github/workflows/ci.yml` gets a `dorny/paths-filter` step that finds a plan-only pull request. A pull request is plan-only when every changed file is `openspec/changes/<issue>-<slug>/<file>`. A file in `openspec/changes/archive/`, in `openspec/specs/`, `openspec/config.yaml`, `.github/` or any other place makes the pull request not plan-only.
- A plan-only pull request runs `uv run pytest tests/invariants` and nothing more of the suite. Those tests read the change folders: names and forms, private addresses, the pull request template and the architectural rules.
- Every other pull request, every push to `main` and every manual run still runs `uv run devops ci --check --no-cache --only test`.
- The step `Changed-Line Coverage` does not run for a plan-only pull request. The reduced run writes no coverage data, so the step has nothing to read, and a plan holds no Python line to cover.
- The job keeps its name, its place in the workflow and its `if`. A job whose steps are skipped reports success, so the required check `Tests & Coverage` is met.
- `docs/SDLC.md` names the rule in the CI section.
- A workflow contract test fails when the filter is missing, when a path outside `openspec/changes/<issue>-<slug>/` counts as plan-only, or when the reduced run is missing.
- This change alters no behavior a consumer observes. It changes a CI workflow, a test and a document, so it has no spec delta and sets `skip_specs: true`. The requirement of `ci-coverage-reports` for the step `Changed-Line Coverage` stays true when the step runs.
- This change fits one pull request.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `.github/workflows/ci.yml`: job `test` gets the filter step, the reduced run and two step conditions. Its `permissions` gain `pull-requests: read`, which the filter needs to list the changed files.
- `tests/invariants/test_workflow_contracts.py`: new contract tests for the filter, the plan-only paths and the reduced run.
- `tests/commands/test_ci.py`: the test of the step `Changed-Line Coverage` expects the new condition.
- `docs/SDLC.md`: new section for the plan-only rule.

## Feasibility

Checked on 2026-10-31 against the real workflow, the pinned action and the measured run time.

- The pin `dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d` (v4.0.3) was fetched into a scratch directory and read. Its `action.yml` has the input `predicate-quantifier` with the values `some`, `every` and `some-with-excludes`. Its README says the output of a filter is `true` when any changed file matches the filter.
- The statement "every changed file matches X" has no direct form: the output is true when ANY file matches. The inverse form works. The filter `outside_plan` matches a file that is NOT a plan file. The pull request is plan-only when `outside_plan` is `false`. With `some-with-excludes`, a file matches when it matches one pattern and none of the negated patterns. The filter is `'**'` and `'!openspec/changes/[0-9]*-*/**/*'`. In `src/filter.ts`, a negated pattern is an exclusion, and an exclusion is final.
- Renamed and deleted files: `src/main.ts` reads the files of the pull request with `pulls.listFiles`. It turns a renamed file into an added file with the new name and a deleted file with `previous_filename`. A file that leaves `src/` for the plan folder thus still lists its old path, and the old path is outside the plan. A removed file keeps its path with the status `deleted`. The filter has no status rule, so a deleted file counts as a changed file.
- Permissions: on `pull_request` events the action calls the REST API `GET /repos/{owner}/{repo}/pulls/{n}/files`. It needs `pull-requests: read`, as `docs-site` and `image-pins` already grant. It needs no checkout on this event.
- Pattern semantics: picomatch 2.3.1, the version in the lock file of the action, was installed with `npm install --ignore-scripts` into a scratch directory. Node 24 ran picomatch with the options of the action (`dot: true`) and the same split of inclusions and exclusions as `createRuleItem`, over 22 sample paths. Plan files in any depth under `openspec/changes/<issue>-<slug>/` are plan files. A file in `openspec/changes/archive/`, a file directly in `openspec/changes/`, a folder with a name that does not start with digits, `openspec/specs/`, `openspec/config.yaml`, `.github/`, `src/`, `tests/` and `docs/` are outside. The contract test reads the same patterns and checks the same sample paths with `PurePosixPath.full_match`. The two matchers agree on every sample.
- Run time: `uv run pytest tests/invariants` ran 385 tests in 41.5 s with 16 workers and in 41.3 s serial on this host. The full gate took 297 s to 371 s on the runner for the three plan pull requests. The 150 s goal of the issue is a measure on the pull request, which a person reads on the first plan-only pull request after the merge.
- `devops ci test tests/invariants/` does not work for this. It maps source and test files to covering tests. A directory maps to no test, so the command prints `No source or test files supplied; nothing to verify.` and exits 0. Such a step would pass while it runs nothing. The step runs `pytest` directly, which exits 5 when the directory is missing or holds no test.
- Reduced coverage: a pytest run with `--cov=src` over `tests/invariants` would fail the global floor of 85 %, so the reduced run uses no coverage option. A plan holds no Python line, so no changed-line figure exists.
- Job-level safety: the job `test` keeps `if: github.event_name != 'schedule'` and has no `needs`. The filter step runs only on `pull_request`. On `push` and `workflow_dispatch` the step is skipped, its outputs are empty, and the condition `!= 'false'` selects the full suite.
- The set of tests in `tests/invariants` is the set the issue names. Other tests that touch `openspec/` use temporary directories. The docs inventory classes the files of `openspec/changes/**/*.md` as records, so a new plan file needs no inventory entry.

## Existing Tool Considered

- `dorny/paths-filter` v4.0.3 is in `ci.yml` already, pinned by commit, in two jobs. It covers the need, with the `some-with-excludes` quantifier. The change builds no filter code.
- `pytest` runs the reduced selection. No new option for `devops ci test` is built: that command cannot take a directory today, and a step that names `tests/invariants` for `pytest` is one line.
- GitHub `on.pull_request.paths-ignore` was considered. It would skip the whole workflow for a pull request, so the required checks would stay pending and block the merge. It is not usable.
- This change deletes no internal code.
