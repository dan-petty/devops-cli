# Design

## Decisions

- **Read all checks with `gh pr checks <n> --json name,state,bucket,workflow,link`, not only the required ones.**: The GraphQL rollup of PR #7481 on 2026-11-28 held 29 checks, and `isRequired` was true for 3 of them (Static Analysis, Tests & Coverage, Semantic PR title). Fail-to-Pass Check, CodeQL, Plan Check and Trivy are not required. The verdict refuses each failed check today (`src/devops_cli/github/merge_readiness.py:330`), so `--required` would lower that threshold, which rule 5 of `AGENTS.md` forbids.
- **When gh answers `no checks reported`, read the rules of the base branch with `read_required_check_names`.**: Rules with a `required_status_checks` rule keep the pending stand-in, because GitHub does not merge until each required check reports. Rules with none give the no-CI advisory, because GitHub merges such a pull request with no check. A read of the rules that fails keeps the pending stand-in, as an unread workflow file did.
- **Match the gh answer `no checks reported` by the start of its stderr line.**: gh exits 1 for that answer and for a failed check (`pkg/cmd/pr/checks/checks.go`), so the exit code alone cannot tell them apart. gh v2.106.0 prints the error text as one line (`internal/ghcmd/cmd.go`, `printError`). Each other failure fails closed.
- **Keep the field `MergeReadiness.no_ci` and its consumers in `pr ready` and `pr monitor`.**: Only the source of the field changes, so the exit codes of both commands keep their map.
- **Give `devops pr checks` no fallback.**: gh already reads the check runs and the commit statuses. A failed gh read exits 1 with the cause, as a failed check does.

## Rejected alternatives

- **`gh pr checks --required`.**: `populateStatusChecks` in `pkg/cmd/pr/checks/checks.go` answers both a branch that requires no check and required checks that have not started with exit 1 (`no checks reported` or `no required checks reported`), so `--required` cannot replace the trigger guess alone. It also drops 26 of the 29 checks of PR #7481.
- **`gh pr view <n> --json statusCheckRollup`.**: It gives each run of each check suite. `gh pr checks` removes the older runs with `eliminateDuplicates` (`pkg/cmd/pr/checks/aggregate.go`), and `gh pr view` does not, so the verdict would need its own removal again, which #5383 had to fix.
- **Keep the guess from the workflow triggers.**: It copies the `on.pull_request` filters of GitHub (`src/devops_cli/github/workflow_triggers.py`, 129 lines and 285 lines of tests, with `wcmatch`), and needed #5144 and #5408 to fix it. The rules of the base branch are the rule that GitHub applies to the merge.
- **Keep the REST fallback of `devops pr checks`.**: It read the check runs, each page of the commit statuses and their combined state (`src/devops_cli/github/check_verdict.py:272-470`), which gh reads in one GraphQL query.

## Known limit

A required check whose workflow has not started is not in the list of gh while other checks are. The REST read had the same limit, because it listed only the check runs that exist. GitHub still refuses the merge (`mergeable_state: blocked`), and `check-readiness` blocks on that state.
