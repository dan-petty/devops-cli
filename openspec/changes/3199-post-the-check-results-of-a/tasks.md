# Tasks

## 1. Read the check runs of a head commit and build the comment text

Reads: `src/devops_cli/github/rate_limiter.py`, `src/devops_cli/github/check_verdict.py`, `src/devops_cli/roadmap/pull_describe.py`. Changes: `src/devops_cli/github/pr_evidence.py` (new), `tests/github/test_pr_evidence.py` (new).

- [ ] 1.1 Write `tests/github/test_pr_evidence.py` first: a recorded check-runs reply of a head commit with a passing check, a skipped check and a `Fail-to-Pass Check` run, asserted against the comment text. Assert that a feat pull request with no such run gets no fail-to-pass section, and that a run with the agent attribution setting ends with the footer, and verify that `uv run devops ci test tests/github/test_pr_evidence.py` fails on the base
- [ ] 1.2 Add `src/devops_cli/github/pr_evidence.py`. It holds the marker constant `<!-- devops-cli:pr-evidence -->`, the fail-to-pass check name `Fail-to-Pass Check`, a function that reads the check runs of a commit through `run_gh`, a function that builds the comment text from the head SHA and the check runs, and a function that selects the comment that starts with the marker from a list of issue comments. The table gives each check its name, its conclusion and its link. Each skipped check gets its own line. Reuse the attribution footer builder of `src/devops_cli/roadmap/pull_describe.py`, and verify that `uv run devops ci test tests/github/test_pr_evidence.py` passes

## 2. Add the devops pr evidence command with its dry run

Reads: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_plans.py`, `src/devops_cli/lang/en/messages.py`, `tests/commands/test_pr_evidence.py` (new).

- [ ] 2.1 Write `tests/commands/test_pr_evidence.py` first: a recorded pull request with no marked comment gets one POST request, and a second run against a recorded comment that carries the marker sends one PATCH request and no POST. Assert that `devops pr evidence 42 --body '3 passed'` exits with a usage error and sends no request, and that `--dry-run` prints the comment text and the request plan and sends no write request, and verify that `uv run devops ci test tests/commands/test_pr_evidence.py` fails on the base
- [ ] 2.2 Add `plan_pr_evidence` to `src/devops_cli/github/pr_plans.py`: the read of the pull request, the read of the check runs, the read of the issue comments, and the POST or the PATCH that the marker decides. Add the `evidence` command to `src/devops_cli/commands/pr.py` with the `@dry_run_class("request-plan")` decorator, the `--repo` and `--dry-run` options, and no free-text option. Add the help and message strings to `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/commands/test_pr_evidence.py` passes

## 3. Document the command and regenerate the command reference

Reads: `CONTRIBUTING.md`, `README.md`. Changes: `CONTRIBUTING.md`, `README.md`.

- [ ] 3.1 In `CONTRIBUTING.md`, name `devops pr evidence <number>` as the command that writes the check-results comment and the fail-to-pass evidence, so no person types a count. Regenerate the command reference of `README.md` with `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes
- [ ] 3.2 CONTRIBUTING.md and README.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Criteria

- **WHEN** A test runs `devops pr evidence 42` against a recorded pull request with one head commit and two check runs. - **THEN** The command requests the check runs for that head commit SHA and builds a table with both check runs.: group 1
- **WHEN** The recorded head commit has a passing check and a skipped check, and the pull request is a fix with a fail-to-pass check run. - **THEN** The comment names the head commit, lists each check with its conclusion and link, links the fail-to-pass run, and names the skipped check on its own line.: group 1
- **WHEN** A test runs the command for a pull request with a feat title and no fail-to-pass check run. - **THEN** The comment text has no fail-to-pass section and no fail-to-pass link.: group 1
- **WHEN** A test runs the command twice and the recorded issue comments hold one comment with the marker line. - **THEN** The second run sends one PATCH request for the marked comment and no POST request for a new comment.: group 2
- **WHEN** A test runs `devops pr evidence 42 --body '3 passed'`. - **THEN** The command exits with a usage error and sends no request.: group 2
- **WHEN** A test runs `devops pr evidence 42 --dry-run` against a recorded pull request. - **THEN** The command prints the comment text and the request plan and sends no write request.: group 2
- **WHEN** A test runs the command with the agent attribution setting and a recorded pull request. - **THEN** The comment text ends with the attribution footer.: group 1

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
