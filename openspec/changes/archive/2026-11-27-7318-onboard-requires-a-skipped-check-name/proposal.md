# Proposal

## Why

Row 10 of `devops repos onboard` counts a skipped check run as passed, so the ruleset of dan-petty/infra got the required check `K8s` from a job that only skipped and dan-petty/infra#178 could not merge (#7318). A skipped matrix job gave the leg names `Tests & Coverage (shard 1 of 5)` and `Changed-Test Independence (run 1 of 3)`, which no release pull request reports.

## What Changes

- `_Checks` at `src/devops_cli/github/onboard/template_pr.py:class _Checks` records the names that ended `success` and the names that ended `skipped`, and `_read_checks` fills both from the check runs of the head.
- `RowContext` at `src/devops_cli/github/onboard/model.py:class RowContext` carries `successful_checks` and `skipped_checks` in place of `reported_checks`, so row 10 tells a skipped run from a passing one.
- Row 10 in `src/devops_cli/github/onboard/settings_rows.py` adds a required check only from a check run that ended `success`.
- A matrix leg, a check name of the shape `<job> (<values>)`, gives way to the name of its job when a check run of that name ended `success`, so the ruleset requires the aggregate check that each pull request reports.
- Row 9 reads the check runs of the head of the newest template pull request, merged included, when the repository holds each template file, so a run of onboard reads the evidence that built the ruleset of a repository that it already changed.
- Row 10 leaves out each live required check that only a skipped check run gave, or that is the leg of a job that ended `success`, and its change line names each one after `; dropped`.
- A check that the required checks rule of the baseline settings file names stays required, so a repository with a path-filtered job declares its check there.
- The nightly run `devops repos onboard --all --plan` reports such a check as drift for each repository of `service.repos`, and a person removes it with `devops repos onboard <owner>/<name> --confirm --only 9,10`.
- `tests/support/github_repository.py` serves the template pull request of the state that the query names, so a case asserts the audit with no network.
- `docs/repos/onboard.md` states the rule of the required checks of rows 9 and 10, and the person step that removes a reported check.
- The change carries a spec delta for `repos-onboard`, because the rows, their states and their change lines are observable.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `repos-onboard`: A skipped check run adds no required check, A matrix leg gives way to its job name, Row 9 reads the checks of the newest template pull request, The ruleset requires the reported and the declared checks

## Impact

- Code: `src/devops_cli/github/onboard/template_pr.py`, `src/devops_cli/github/onboard/model.py`, `src/devops_cli/github/onboard/settings_rows.py`
- Documents: `docs/repos/onboard.md`
- Tests: `tests/github/onboard/test_onboard_rows.py`, `tests/support/github_repository.py`

## Feasibility

- The probe line says, word for word: `_with_required_checks` is defined at `src/devops_cli/github/onboard/settings_rows.py:640:def _with_required_checks(`, and that staged symbol builds the required checks of row 10.
- The probe line says, word for word: The path `src/devops_cli/github/onboard/settings_rows.py` is a file of the staging commit, and `src/devops_cli/github/onboard/settings_rows.py:def ruleset_row` passes `ctx.reported_checks` to that builder, so the lines 621 and 663 of the issue body come from an older commit.
- The probe line says, word for word: `The bound left the test module listing out.` The staged tree holds `tests/github/onboard/test_onboard_rows.py`, and that module holds the row 10 cases that the new cases join.
- The defect is at its source: `src/devops_cli/github/onboard/template_pr.py:40:_PASSED_CONCLUSIONS: Final[frozenset[str]] = frozenset({"success", "neutral", "skipped"})` counts `skipped` as passed, and `src/devops_cli/github/onboard/template_pr.py:def _read_checks` puts the name of each such run into the passing names of the check runs.
- `read_file` of the range 195 to 245 of `src/devops_cli/github/onboard/model.py` showed `reported_checks` as one flat tuple of passed names at `src/devops_cli/github/onboard/model.py:217:class RowContext:`, and `src/devops_cli/github/onboard/template_pr.py:def _checks_row` fills it from the passing names of the class `src/devops_cli/github/onboard/template_pr.py:class _Checks`, which the staged tree declares at `src/devops_cli/github/onboard/template_pr.py:64:class _Checks:`, with the fields `passed`, `failed` and `ended`.
- `references` for `reported_checks` answered 4 files: `src/devops_cli/github/onboard/model.py:class RowContext`, `src/devops_cli/github/onboard/settings_rows.py:def ruleset_row`, `src/devops_cli/github/onboard/template_pr.py:def _checks_row`, and the archived proposal of #7423, which stays as history.
- Row 10 keeps each live check today: `src/devops_cli/github/onboard/settings_rows.py:def _with_required_checks` copies each entry of the live ruleset into the desired set, so a name that only skipped stays in the ruleset on each later run.
- Row 9 reads no check run when the repository holds each template file, inside `src/devops_cli/github/onboard/template_pr.py:def template_row`, so a repository that onboard already changed gave row 10 no evidence; group 2 reads the checks of the newest template pull request there.
- The audit needs no new access: `docs/repos/onboard.md:96:devops repos onboard --all --plan --only 0,1,2,3,4,5,6,7,8,9,10,11` is the nightly drift run over each repository of `service.repos`, and its token holds `docs/repos/onboard.md:103:read on Actions, Checks, Environments, Issues, Metadata, Pull requests and Secrets`.
- The count of repositories that onboard already changed is unverified: no tool of this run counts them, and the census command `uv run devops repos onboard --all --plan --only 9,10` needs a client of the GitHub API, a network and the token of the owner, so a person runs it. The plan narrows the claim to the repositories of `service.repos`, which that run names, and a repository that prints no dropped name needs no removal.
- The test harness serves only an open pull request today, inside `tests/support/github_repository.py:def _pulls`, so group 2 makes the query `state` decide, and the new cases reach no network.
- The new cases fail on the base commit: a `K8s` check run that ended `skipped` becomes a required check, a leg name stays required beside its job name, and a live required check that only skipped stays in the ruleset. First check: `uv run devops ci test tests/github/onboard/test_onboard_rows.py`.
- Check against the real system: `uv run devops repos onboard <owner>/<repo> --plan --only 9,10` must print `; dropped <name>` for a required check that only a skipped run gave; it needs a client of the GitHub API, a network and the token of the owner, so a person runs it.
- Precondition of `src/devops_cli/github/onboard/template_pr.py:def _read_checks`: a client of the GitHub API and a network, because it reads the check runs of a head.
- Precondition of the pull request listing that group 2 adds inside `src/devops_cli/github/onboard/template_pr.py:def template_row`: a client of the GitHub API and a network, because it reads `GET /repos/<repo>/pulls?state=all`.
- Precondition of `src/devops_cli/github/onboard/template_pr.py:def template_row`: a client of the GitHub API and a network, because it opens the template pull request, reads its files and reads the check runs of its head.
- Precondition of `src/devops_cli/github/onboard/settings_rows.py:def ruleset_row`: a client of the GitHub API and a network, because it reads the live ruleset, reads the settings file of the default branch and writes the ruleset.
- Runner capability of `uv run devops ci test tests/github/onboard/test_onboard_rows.py`: `uv`, `python` and `pytest` come from the image tools, no program of the run is NOT_IN_RUNNER, and the pod settings `runAsNonRoot`, `readOnlyRootFilesystem`, `capabilities.drop: ALL` and `allowPrivilegeEscalation: false` hold; the fake GitHub answers each request, so the run reaches no network.
- Runner capability of `uv run devops ci docs`: `uv` and `python` come from the image tools, and `vale` is NOT_IN_RUNNER, so the docs group relies on no live docs check.
- No new failure class: the plan adds no program to the image and no command to the gate, and both verifies are rows of `uv run devops ci` that exist.

## Existing Tool Considered

No open, maintained tool derives the required checks of a ruleset from the check runs of a template pull request, or resolves the name of a skipped reusable-workflow job: the alternatives block of the issue records no tool, and the open items that name `repos onboard` change other things (#7326 the thresholds, #7445 the change line of row 10, #6784 the baseline of the seven repositories). The change extends the check-name logic of row 10 at about 3k tokens and 3 hours to build, keep and fix it, and it deletes no internal code.

## Dependencies

None.
