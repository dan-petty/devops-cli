# Task: Changed-Line Coverage on Pull Requests (diff-cover) (#850)

**Issue**: [#850](https://github.com/dan-petty/devops-cli/issues/850)
**Status**: Done
**Milestone**: v0.2.32
**Priority**: priority/p2-medium
**Scope**: scope/ci, scope/github

## Description

Coverage is gated only in total (`[tool.coverage.report] fail_under = 90`), so an untested new function inside a well-covered module passes every gate. On pull requests, the `Tests & Coverage` job now runs diff-cover 10.6.0 (dev group) over the `.data/coverage.xml` that its gate step already writes. It measures against the pull request's own base branch (`origin/${BASE_REF}`, with `BASE_REF` taken from `github.base_ref` through `env`) and writes the markdown report to the job summary. It then appends the `pragma: no cover` lines the pull request adds under `src`, with their file names. diff-cover truncates its output file, so it writes first and the pragma list is appended after it. The checkout fetches full history (`fetch-depth: 0`) so the merge base is always found.

The report is advisory. It has no `--fail-under`, and it is not a check row, so `uv run devops ci` and the pre-push gate are unchanged. The step fails the job only when git or diff-cover itself fails, never because of the coverage figure.

## Backtest

The last 10 merged pull requests into `release/**` that change `src`, measured at each squash commit. Each suite ran in a scratch worktree with `pytest -n 4 --cov=src --cov-report=xml`, with `HOME` and `TMPDIR` on fresh scratch directories, followed by `diff-cover .data/coverage.xml --compare-branch=<sha>^` (diff-cover 10.6.0). "Changed lines" counts only the lines diff-cover can measure. It skips lines that carry no coverage information, such as comments, docstrings and continuation lines inside one statement.

| PR | Commit | Changed lines | Missing | Changed-line coverage | Below 90 | Test failures at the commit |
| :--- | :--- | ---: | ---: | ---: | :--- | :--- |
| #1488 | `0b06ff409` | 79 | 6 | 92.4% | no | none |
| #1487 | `a525a81c0` | 256 | 52 | 79.7% | yes | none |
| #1484 | `8dfb0c1a7` | 27 | 8 | 70.4% | yes | 1: `test_no_direct_data_dir_path_construction_in_src` flags `ai/client/network.py` at this commit |
| #1483 | `0f945db4e` | 131 | 14 | 89.3% | yes | none |
| #1482 | `b7edb8f8a` | 0 | 0 | n/a (two entries inside one list literal) | no | none |
| #1481 | `f8ebd601a` | 101 | 3 | 97.0% | no | none |
| #1480 | `b22837db9` | 23 | 3 | 87.0% | yes | none |
| #1479 | `a01fdacfd` | 46 | 10 | 78.3% | yes | none |
| #1477 | `fb3bad1e7` | 0 | 0 | n/a (docstring and comments only) | no | none |
| #1476 | `95ced1a17` | 1 | 0 | 100.0% | no | none |

- Rule (owner decision D4): the step becomes blocking, with `--fail-under` set to `[tool.coverage.report] fail_under` (90), once a backtest over the last 10 merged pull requests shows that fewer than 1 in 10 would fail. That change adds a test that reads the value through `tomllib`, so the step and `pyproject.toml` cannot drift.
- Result: not met, so the step stays advisory. 5 of 10 pull requests (#1487, #1484, #1483, #1480, #1479) fall below 90.

## Acceptance Criteria

- [x] On a pull request into `release/**`, the summary measures coverage against that release branch. The step runs diff-cover with `--compare-branch="origin/${BASE_REF}"`, and `BASE_REF` is `github.base_ref`. Run locally under `bash --noprofile --norc -eo pipefail` with `BASE_REF=release/v0.2.32`, the step's script wrote a summary headed `Diff: origin/release/v0.2.32...HEAD`, and it listed an added `pragma: no cover` line under its file name.
- [x] `uv run devops ci` is unchanged: no `src` file changes, and no check row runs diff-cover.
- [x] `test_changed_line_coverage_step_is_advisory_on_pull_requests` in `tests/test_ci.py` parses `ci.yml` and asserts that the step follows the gate step, runs only on `pull_request`, takes the base ref through `env`, reads `.data/coverage.xml`, writes the summary and the pragma list, and has no `--fail-under` and no `${{` in its script. It also asserts that the checkout fetches full history and that no check row runs diff-cover.
- [x] The CI parity check (`_validate_ci_workflow_parity`) allowlists the step as an advisory report that is never a check row.
- [x] actionlint (with shellcheck), `uv lock --check` and `uv audit` pass.
- [x] The step adds under 15 s. diff-cover took 0-3 s per commit in the backtest, and the whole script ran in under 1 s locally.
- Pending a person: the pull request's `Tests & Coverage` run summary shows `Diff: origin/release/v0.2.32...HEAD`, followed by the "Added pragma: no cover lines" section.
  - `gh pr checks <pr>`, then open the `Tests & Coverage` run's Summary page (`gh run view <run-id> --web`).
- Pending a person: the step takes under 15 s on GitHub.
  - `gh api repos/dan-petty/devops-cli/actions/jobs/<job-id> --jq '.steps[]|select(.name=="Changed-Line Coverage")|[.started_at,.completed_at]'`
- Pending a person (owner settings, the same step #842 already lists as "without `code_coverage`"): remove the inert `code_coverage` rule from rulesets 21466414 and 23059172, since nothing feeds it.
  - `gh api repos/dan-petty/devops-cli/rulesets/<id> --jq '{name,target,enforcement,conditions,bypass_actors,rules:[.rules[]|select(.type!="code_coverage")]}' > /tmp/rs.json && gh api -X PUT repos/dan-petty/devops-cli/rulesets/<id> --input /tmp/rs.json`

## Deliverables

- [x] `pyproject.toml`: `diff-cover==10.6.0` in the dev group. `uv.lock` adds diff-cover 10.6.0 and chardet 7.6.0.
- [x] `.github/workflows/ci.yml`: the `test` job checks out full history and runs the `Changed-Line Coverage` step after `Tests & Coverage Quality Gate`, on pull requests only.
- [x] `tests/test_ci.py`: the step's shape test, and the step's entry on the CI parity allowlist.
- [x] `RELEASE_CYCLE.md`: Step 3 lists the advisory report, and the CI note says the `Tests & Coverage` job writes it to its job summary on pull requests.
- [x] `changelog.d/850.md` under `### Added`.
- Dropped: the threshold constant in `config/constants.py`. Nothing would read it while the step is advisory, and the blocking threshold is `[tool.coverage.report] fail_under`, so a constant would duplicate it.
- Dropped: marking the `docs/ROADMAP.md:1010` entry rescoped. `docs/ROADMAP.md` is generated and the entry no longer exists. No issue tracks its vanished-test report, so that report needs its own issue if it is still wanted.

## Known Limits

- `workflow_dispatch` runs, such as those from `devops pr update --dispatch-ci`, skip the step, because they carry no base ref.
- `Tests & Coverage` is not yet a required check on either ruleset. Until #842's owner settings step lands, a blocking step would block nothing.
- The step is skipped when the gate step fails, because no complete `.data/coverage.xml` exists then.
