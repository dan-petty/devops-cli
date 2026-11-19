# Proposal

## Why

The implement job marks its delivery pull request ready for review with no quality gate evidence comment (#4129). `AGENTS.md` Rule 4 and Rule 6 and `CONTRIBUTING.md` ask for the comment on every pull request, and the job leaves only its own bot step summary. People run `devops pr evidence` by hand to read the head commit, the check status, the links and the skipped runs. The evidence publisher exists already; the job never calls it.

## What Changes

- The implement job calls `publish_pr_evidence` in `_ready` after the draft readiness answers ready and before `mark_ready`, so the delivery pull request holds the quality gate evidence comment before it leaves draft.
- A publisher that fails stops the item before `mark_ready`: the item is Blocked, the pull request stays a draft, and a retry posts the evidence.
- The test world answers the pull request read with the head commit that its pull fake holds and routes the check runs of that head, so the publisher reads the head that the job read.
- New tests in `tests/roadmap/implement/test_roadmap_implement_job.py` assert that the evidence comment is posted before `gh pr ready` and that a failed post stops the item.
- `CONTEXT.md` and `docs/ROADMAP_WORKFLOW.md` name the evidence step of the implement job.
- The spec delta adds one requirement to the capability `roadmap-implement-job/pull-request`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: The job publishes the evidence before it marks the pull request ready

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`

## Feasibility

- The probe answers, word for word: "The path `src/devops_cli/roadmap/implement/implement_run.py` is a file of the staging commit." The module defines `_ready` at `src/devops_cli/roadmap/implement/implement_run.py:2051:def _ready(self, pull: int) -> None:`.
- The probe answers, word for word: "`implement_run.py` is no file at the root of the staging commit." and "No commit in the history deleted or renamed it." The issue writes the bare name, and the staged commit holds the module under its package.
- The probe answers, word for word: "The path `AGENTS.md` is a file of the staging commit." and "The path `CONTRIBUTING.md` is a file of the staging commit."
- `file_symbols` of the job module gave `_checks` at line 1971 and `_ready` at line 2051.
- `read_file` of the job module showed `src/devops_cli/roadmap/implement/implement_run.py:2051:def _ready(self, pull: int) -> None:` and `src/devops_cli/roadmap/implement/implement_run.py:2097:mark_ready(self.repo, pull, draft=draft)`, with no evidence call between them, so the premise of the issue holds at the staged commit.
- `read_spec` of `roadmap-implement-job/pull-request` gave the requirement "A pull request that passes its checks is marked ready", which names `gh pr ready` and no evidence comment.
- `search_code` for `publish_pr_evidence` gave the publisher at `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(`, its import in `src/devops_cli/commands/pr.py:487: from devops_cli.github.pr_evidence import EvidenceAction, publish_pr_evidence`, and no use in the job module: `devops pr evidence` calls the publisher and the implement job does not.
- `read_file` of the publisher module showed `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(` posting or updating the one comment that opens with the marker and that the session login wrote, at `src/devops_cli/github/pr_evidence.py:121:if comment.author == session.login and _opens_with_marker(comment.body)`.
- `read_file` of the publisher module showed `src/devops_cli/github/pr_evidence.py:109:raise GitHubUnreadError(summary.unread_reason, details={"repo": repo, "pull": number})`, so an unread check stops the post.
- `read_file` of `src/devops_cli/exceptions/git.py` showed `class GitHubOperationError(DevOpsCLIError, RuntimeError):` and `class GitHubUnreadError(GitHubOperationError):`, so a stop that catches the first class catches both.
- `publish_pr_evidence` needs a client of the Git Hub session: it reads the pull request, the check runs of its head, the comments of the pull request and writes one comment.
- `get_git_hub_session` needs a client of the Git Hub session, which the runner Job holds as the App with a token for the one repository.
- `read_check_runs` needs a client of the Git Hub session, and `_ready` makes that call already.
- `mark_ready` needs a network and `gh` in the image, and the runner lists `gh`.
- `draft_readiness` and `_error_stop` need no checkout, no client and no network: both are pure.
- The plan adds no command and no program. Its verify commands, `uv run devops ci test` and `uv run devops ci docs`, run `uv`, `pytest`, `ruff` and the docs check, each a runner tool of the image, and no program of the plan is `NOT_IN_RUNNER`. The pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `secompProfile: RuntimeDefault`.
- The stop takes the class `ci_infra`, whose action is one retry, so a retry posts the evidence.
- The plan relies on no value of a constant of the staged tree, so it cites no constant value.
- `read_issue` of #4698 answered that the item is open and that its own refine still waits on #4691, so the gate line of comment 4 waits on that item. This plan publishes the evidence and plans no code for the gate line.
- The rule of `CONTRIBUTING.md` line 154 is not checked in this run; the plan cites no line of that file.

## Existing Tool Considered

`publish_pr_evidence` in `src/devops_cli/github/pr_evidence.py` covers the need: it builds the head commit, the table of the check runs with their conclusions and links, the fail-to-pass link and the skipped runs, and it keeps one comment per login and head. `devops pr evidence` already calls it, so the change adds only the call from the implement job and its stop on a failure.

## Dependencies

- #4698: The gate line of comment 4 names the gate lane, the Workflow, the patch-id and the base, which #4698 records, and #4698 is open, so the gate line waits on that item.
