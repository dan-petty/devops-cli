# Proposal

## Why

The implement job marks its delivery pull request ready for review with no quality gate evidence comment (#4129). The contributing guide asks every pull request to carry the check-results comment that `devops pr evidence` writes: the head commit, the status of the remote checks, the links and the skipped runs. The job leaves only its own bot step summary, so a person runs the command by hand. The publisher exists at `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(`, and the job never calls it.

## What Changes

- `publish_pr_evidence` at `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(` takes an optional keyword-only `head`, so a caller publishes the head commit that it already read.
- The evidence command keeps its requests and its output, and its docstring at `src/devops_cli/commands/pr.py:479:"""Write the check results of the head commit of a pull request as its one evidence comment.` names the head commit that it publishes.
- The new `_publish_evidence` of the ready step at `src/devops_cli/roadmap/implement/implement_run.py:2051:def _ready(self, pull: int) -> None:` publishes the delivery evidence between the readiness answer and the ready mark.
- A `GitHubOperationError` at `src/devops_cli/exceptions/git.py:86:class GitHubOperationError(DevOpsCLIError, RuntimeError):` from the publisher stops the item through the job's own stop class at `src/devops_cli/roadmap/implement/implement_run.py:302:class _StopError(Exception):`, so `gh pr ready` never runs and the pull request stays a draft.
- The test world holds one evidence comment of the job's login, routes its change, and records at each ready call the requests that the API had received, so the test asserts that the evidence comment is written before the ready mark.
- The three request-count assertions of `tests/roadmap/implement/test_roadmap_implement_phase_marks.py` gain the evidence listing read and the evidence change.
- `CONTEXT.md` and `docs/ROADMAP_WORKFLOW.md` name the evidence comment of the implement job before the ready mark.
- The spec delta modifies the requirement `A pull request that passes its checks is marked ready` of `roadmap-implement-job/pull-request`, with its three scenarios and one more for a failed publisher.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job/pull-request`: A pull request that passes its checks is marked ready

## Impact

- Code: `src/devops_cli/github/pr_evidence.py`, `src/devops_cli/commands/pr.py`, `src/devops_cli/roadmap/implement/implement_run.py`
- Documents: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`
- Tests: `tests/github/test_pr_evidence.py`, `tests/support/roadmap_implement.py`, `tests/roadmap/implement/test_roadmap_implement_job.py`, `tests/roadmap/implement/test_roadmap_implement_phase_marks.py`

## Feasibility

- The probes answer, word for word: "The path `src/devops_cli/roadmap/implement/implement_run.py` is a file of the staging commit." and "No commit in the history deleted or renamed it." The ready step of that module runs `mark_ready(self.repo, pull, draft=draft)`.
- The probes also answer, word for word: "The path `implement_run.py` is no file at the root of the staging commit." The bare name of the issue is shorthand for the module of the ready step, not a false premise.
- The `read_file` call on lines 2040 to 2110 of that module showed the gap that the issue names. The step reads the session, the pull status and the head at `src/devops_cli/roadmap/implement/implement_run.py:2053:client = get_github_session().client` and `src/devops_cli/roadmap/implement/implement_run.py:2055:head = status.head_sha or self._head()`, and it goes from the readiness answer straight to `src/devops_cli/roadmap/implement/implement_run.py:2097:mark_ready(self.repo, pull, draft=draft)` with no publisher call between them.
- The `read_file` call on lines 86 to 135 of the publisher showed that it exists at `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(`. It reads the pull request at `src/devops_cli/github/pr_evidence.py:105:pull = client.get_pull(repo, number)`, then the check runs at `src/devops_cli/github/pr_evidence.py:107:summary = read_check_runs(owner, name, pull.head.sha, session=session)`, and it writes that head with `src/devops_cli/github/pr_evidence.py:112:head_sha=pull.head.sha,`.
- The publisher keeps one comment: it matches its own at `src/devops_cli/github/pr_evidence.py:121:if comment.author == session.login and _opens_with_marker(comment.body)` and changes it at `src/devops_cli/github/pr_evidence.py:128:client.update_issue_comment(repo, own.id, body)`.
- The `search_code` call for the marker gave the constant that the plan relies on: `src/devops_cli/config/constants.py:4715:CONST_PR_EVIDENCE_MARKER: Final[str] = "<!-- devops-cli:pr-evidence -->"`, whose value is `<!-- devops-cli:pr-evidence -->`.
- The `read_file` call on lines 455 to 515 of the command showed its call site at `src/devops_cli/commands/pr.py:495:publish_pr_evidence(`, which passes no head, and its docstring at `src/devops_cli/commands/pr.py:479:"""Write the check results of the head commit of a pull request as its one evidence comment.`, which group 1 extends. The command's help text and its requests stay as they are.
- The `references` call for `publish_pr_evidence` answered "References to 'publish_pr_evidence': files 4, lines 14." It lists `src/devops_cli/commands/pr.py`, `src/devops_cli/github/pr_evidence.py` and `tests/github/test_pr_evidence.py`, all in the changes of group 1; the fourth hit sits under `openspec/changes/archive/` and is exempt.
- The `search_code` call for the failure class gave `src/devops_cli/exceptions/git.py:86:class GitHubOperationError(DevOpsCLIError, RuntimeError):`, and the unread error that the publisher raises is its subclass at `src/devops_cli/exceptions/git.py:154:class GitHubUnreadError(GitHubOperationError):`, so one catch of the publisher holds both.
- The `read_file` call on lines 100 to 140 of the test world showed that it answers the pull read with no head at `tests/support/roadmap_implement.py:118:"head": {"ref": BRANCH, "sha": ""},`, which is why the job passes the head that it read.
- The same read showed that the world lists the pull request comments through `tests/support/roadmap_implement.py:461:self.api.route("GET", listing, github_json(list(comments)))` and already changes comment 1 at `tests/support/roadmap_implement.py:455:api.route("PATCH", f"/repos/{STAGE_REPO}/issues/comments/1", github_json({"id": 1}))`. The plan seeds the evidence comment as 900 with a change route of its own, so the step comment stays 1.
- The `read_file` call on lines 390 to 530 of the test world showed that its ready answer records only the argv of the ready call at `tests/support/roadmap_implement.py:511:self.ready_calls.append(call.argv[1:])`, so that list alone cannot show the order of the evidence write and the ready mark.
- The `read_file` call on lines 270 to 300 of the API fake showed that it lists each request in the order it received it at `tests/support/fakes/github.py:286:return [f"{request.method} {request.url}" for request in self.sent]`, so a snapshot of that list at the ready call proves the order.
- The `read_file` call on lines 130 to 160 and 595 to 640 of the phase-marks module showed the request counts that move: `tests/roadmap/implement/test_roadmap_implement_phase_marks.py:603:assert _comment_calls(job_world) == ["GET", "POST"]` and `tests/roadmap/implement/test_roadmap_implement_phase_marks.py:629:assert (reads, len(marks)) == (1, 2)`. The helper at `tests/roadmap/implement/test_roadmap_implement_phase_marks.py:140:def _comment_calls(world: JobWorld) -> list[str]:` counts the evidence listing read and the evidence change, because it keeps each request whose path holds `issues/comments/`.
- The world answers the draft flag from its ready calls at `tests/support/roadmap_implement.py:502:"draft": not self.ready_calls,`, so the test of a failed publisher asserts the item Status, the record and `job_world.pull.ready_calls` and asserts nothing about that flag.
- Precondition of `publish_pr_evidence`: a client of the GitHub service and a network, because it reads the pull request, the check runs of the head and the comments, and writes one comment.
- Precondition of `get_github_session`: a client of the GitHub service, which the runner Job holds as its identity for the one repository.
- Precondition of `mark_ready`: a network and `gh`, which the runner lists among its tools.
- Precondition of `read_check_runs`: a network, because it reads the check runs of the head commit.
- `src/devops_cli/roadmap/implement/implement_pull.py:253:def draft_readiness(` needs no checkout, no client and no network: it is a pure function.
- The plan adds no command and no program of its own. Its verifies run `uv run devops ci test` and `uv run devops ci docs`, whose tools `uv`, `pytest`, `ruff` and `devops` the runner lists, so none of them is `NOT_IN_RUNNER`. The pod sets `readOnlyRootFilesystem: true`, `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `seccompProfile: RuntimeDefault`.
- The tests double the GitHub edge and the process edge and reach no network, no cluster and no real scanner, so no live failure class applies to them.
- The first check that the implementation runs against the real system is `uv run devops ci test tests/github/test_pr_evidence.py tests/commands/test_pr_evidence.py`, which fails before the head argument exists.
- The second is `uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py`, which fails before the job publishes the evidence and before the counts hold its requests.
- The live check is `uv run devops pr evidence <number>` on a real delivery pull request: the job then writes that same one comment by itself, so the two agree.
- The finding on the order assertion is answered: the plan records `self.api.requested` in the ready call, so the first new test asserts that the `PATCH` of comment 900 is in the list that the one ready call recorded. The assertion fails when the job publishes the evidence after it marks the pull request ready, because the ready call then records the list before the `PATCH`.
- The earlier finding on the `AGENTS.md` rules is answered: this plan names no rule number of that file and rests the premise on the code gap above.
- The earlier finding on the #4698 dependency is answered: `dependencies` is empty, because the evidence comment of the issue needs no gate lane, no patch-id and no base.
- The earlier finding on the failed-publisher test is answered: it asserts the item Status, the stopped step in the record and the empty ready list, and nothing about the draft flag.
- The earlier finding on the spec delta is answered: the evidence condition goes into the existing requirement through `modified`, with its three scenarios and one more, and no second requirement with the same trigger is added.
- The item is buildable as written: the ready step, the publisher, the command and the stop all exist at the staged commit, and only the call from the job is missing.

## Existing Tool Considered

The function at `src/devops_cli/github/pr_evidence.py:96:def publish_pr_evidence(` covers the need: it writes the head commit, the table of the check runs with their conclusions and links, the fail-to-pass link and the skipped runs, and it keeps one comment per pull request for the login that wrote it. The `devops pr evidence` command calls it already at `src/devops_cli/commands/pr.py:495:publish_pr_evidence(`, so the change adds the call from the implement job, one optional head argument and the stop on a failure, and it writes no second evidence builder.

## Dependencies

None.
