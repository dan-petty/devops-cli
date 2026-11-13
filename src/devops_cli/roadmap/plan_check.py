"""The plan check of a plan pull request (#3201).

`devops roadmap plan-check <pull-request>` reads the change folder at the head of the pull
request, runs the stage gates with no model, and checks the pull request itself: the title, the
body, the check `Semantic PR title`, and a base spec that moved since the plan. A pull request that
the implement job has taken over holds the title and body of a delivery, so it is no plan and the
command reports no problem for it (#3224).

The gates take a `StageProposal` and a `StagedTree`, so the command reads a checkout: it fetches
`refs/pull/<number>/head` and reads the head files with `git show` and `git ls-tree`. The GitHub
client gives the title, the body, the base and the check runs. Each problem has a path, a rule and
a message; a person reads one line for each and an agent reads the JSON array.

The implement job takes the plan pull request of the item over and writes the title and the body
of a delivery, which closes the issue and plans none (PR #3961). Such a pull request is no plan,
so the command reports no problem for it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from devops_cli.config.constants import CONST_OPENSPEC_CHANGES_DIR, CONST_OPENSPEC_SPECS_DIR
from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.config.settings import load_settings
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions.git import GitOperationError
from devops_cli.github.check_verdict import (
    CheckBucket,
    CheckVerdictSummary,
    read_check_runs,
)
from devops_cli.github.client import IssueView, PullRequest
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool
from devops_cli.roadmap.clone_git import checkout_at, git
from devops_cli.roadmap.plan_read import (
    PlanReadError,
    change_root,
    files_at,
    read_change,
    specs_at,
    tree_files,
)
from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, SUMMARY_MAX_CHARS, summary_length
from devops_cli.roadmap.request_plan import planned_session_read
from devops_cli.roadmap.stage.stage_change import (
    STAGING_TYPE,
    StageProposal,
    check_proposal,
    closing_keyword_in,
    issue_dependencies,
    measure_groups,
    shared_texts,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_validate import validate_change
from devops_cli.roadmap.stores.store import split_record

GIT_OPERATION: Final[str] = "roadmap.plan-check"
SEMANTIC_TITLE_CHECK: Final[str] = "Semantic PR title"
_CHANGES: Final[str] = CONST_OPENSPEC_CHANGES_DIR
_SPECS: Final[str] = CONST_OPENSPEC_SPECS_DIR
_PROPOSAL: Final[str] = "proposal.md"
_REQUIREMENT: Final[re.Pattern[str]] = re.compile(r"^### Requirement: (?P<name>.+?)[ \t]*$", re.M)
_SCENARIO: Final[str] = "#### Scenario:"
_PLANS: Final[re.Pattern[str]] = re.compile(r"^Plans #(?P<issue>[0-9]+)$")
_TITLE: Final[re.Pattern[str]] = re.compile(
    rf"^{re.escape(STAGING_TYPE)}: plan #(?P<issue>[0-9]+) (?P<summary>\S.*)$"
)
# A plan pull request holds the plan title, or the `Plans #<issue>` line of its body. The implement
# job takes the plan pull request over and rewrites both to the form of a delivery (#2665), and the
# run of that edit may read the delivery form: that pull request is no plan, and the plan form no
# longer applies to it (#3224).
_PLAN_TITLE: Final[str] = f"{STAGING_TYPE}: plan #"


class PlanReads(Protocol):
    """The GitHub reads that the plan check makes."""

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """The title and the head and base commits of the pull request."""
        ...

    def get_issue(self, repo: str, number: int) -> IssueView:
        """The issue or pull request `number`, with its body."""
        ...


CheckReader = Callable[[str, str, str], CheckVerdictSummary]


@dataclass(frozen=True)
class PullFacts:
    """The pull request as the check reads it."""

    number: int
    title: str
    body: str
    head_sha: str
    base_sha: str
    base_ref: str


@dataclass(frozen=True)
class PlanProblem:
    """One problem of a plan: the file, the rule and the message of the stage job."""

    path: str
    rule: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"path": self.path, "rule": self.rule, "message": self.message}


@dataclass(frozen=True)
class PlanCheckResult:
    """The problems of a plan, in the order that the command reports them."""

    problems: tuple[PlanProblem, ...]

    @property
    def ok(self) -> bool:
        return not self.problems


def _session_client() -> PlanReads:
    from devops_cli.github.session import get_github_session

    return get_github_session().client


def issue_number(body: str) -> int | None:
    """The issue of the `Plans #<issue>` line of `body`, or None when it holds none."""
    for line in body.splitlines():
        match = _PLANS.fullmatch(line.strip())
        if match is not None:
            return int(match["issue"])
    return None


def _is_a_delivery(body: str) -> bool:
    """Whether `body` is the body of the delivery of the item, and not the body of a plan.

    The implement job takes the plan pull request of the item over and writes the title and the
    body of a delivery, which closes the issue and plans none (PR #3961). A pull request that has
    become the delivery is no plan, so the command judges it no more. A body that plans an issue
    keeps the rules of a plan, also when it holds a closing keyword: that plan closes an issue
    when it merges.
    """
    return issue_number(body) is None and closing_keyword_in(body) is not None


def read_pull(client: PlanReads, repo: str, number: int) -> PullFacts:
    """The title, body and commits of pull request `number`."""
    pull = client.get_pull(repo, number)
    issue = client.get_issue(repo, number)
    return PullFacts(
        number=number,
        title=pull.title,
        body=issue.body or "",
        head_sha=pull.head.sha,
        base_sha=pull.base.sha,
        base_ref=pull.base.ref,
    )


def is_plan(facts: PullFacts) -> bool:
    """Whether the pull request is a plan: its title holds the plan title, or its body holds the
    `Plans #<issue>` line. A pull request that the implement job has taken over holds neither, so
    it is a delivery and the plan form no longer applies to it (#3224, PR #3961)."""
    if _is_a_delivery(facts.body):
        return False
    return facts.title.strip().startswith(_PLAN_TITLE) or issue_number(facts.body) is not None


def _pull_problems(facts: PullFacts, checks: CheckVerdictSummary) -> list[PlanProblem]:
    texts = MESSAGES.roadmap
    issue = issue_number(facts.body)
    expected = issue if issue is not None else facts.number
    problems: list[PlanProblem] = []
    title = facts.title.strip()
    match = _TITLE.fullmatch(title)
    if match is None or (issue is not None and int(match["issue"]) != issue):
        problems.append(
            PlanProblem("title", "title", texts.plan_check_title.format(number=expected))
        )
    else:
        after = title.partition(": ")[2]
        length = summary_length(after)
        if length > SUMMARY_MAX_CHARS:
            problems.append(
                PlanProblem(
                    "title",
                    "title-length",
                    texts.plan_check_title_long.format(length=length, limit=SUMMARY_MAX_CHARS),
                )
            )
    if issue is None:
        problems.append(
            PlanProblem(
                "body", "body-plans", texts.plan_check_body_plans.format(number=facts.number)
            )
        )
    keyword = closing_keyword_in(facts.body)
    if keyword is not None:
        problems.append(
            PlanProblem(
                "body", "body-closing", texts.plan_check_body_closes.format(keyword=keyword)
            )
        )
    measured = len(facts.body)
    if measured > BODY_MAX_CHARS:
        problems.append(
            PlanProblem(
                "body",
                "body-length",
                texts.plan_check_body_long.format(length=measured, limit=BODY_MAX_CHARS),
            )
        )
    problems.extend(_check_problems(checks))
    return problems


def _check_problems(checks: CheckVerdictSummary) -> list[PlanProblem]:
    texts = MESSAGES.roadmap
    if checks.unread_reason:
        return [
            PlanProblem(
                "checks",
                "semantic-pr-title",
                texts.plan_check_check_unread.format(
                    name=SEMANTIC_TITLE_CHECK, reason=checks.unread_reason
                ),
            )
        ]
    found = next((item for item in checks.items if item.name == SEMANTIC_TITLE_CHECK), None)
    if found is None:
        return [
            PlanProblem(
                "checks",
                "semantic-pr-title",
                texts.plan_check_check_missing.format(name=SEMANTIC_TITLE_CHECK),
            )
        ]
    if found.bucket is CheckBucket.PASS:
        return []
    return [
        PlanProblem(
            "checks",
            "semantic-pr-title",
            texts.plan_check_check_failed.format(
                name=SEMANTIC_TITLE_CHECK, state=found.state or found.bucket
            ),
        )
    ]


def _has_commit(source: Path, rev: str) -> bool:
    try:
        git(source, "cat-file", "-e", f"{rev}^{{commit}}", operation=GIT_OPERATION)
    except GitOperationError:
        return False
    return True


def _base_revision(source: Path, facts: PullFacts) -> str:
    if _has_commit(source, facts.base_sha):
        return facts.base_sha
    reference = f"origin/{facts.base_ref}" if facts.base_ref else ""
    if reference and _has_commit(source, reference):
        return reference
    git(
        source,
        "fetch",
        "--quiet",
        "origin",
        facts.base_ref or facts.base_sha,
        operation=GIT_OPERATION,
    )
    if reference and _has_commit(source, reference):
        return reference
    return facts.base_sha


def _plan_parent(source: Path, head: str, root: str) -> str:
    commit = git(
        source,
        "log",
        "-1",
        "--format=%H",
        "--diff-filter=A",
        head,
        "--",
        root,
        operation=GIT_OPERATION,
    )
    parent = f"{commit}^"
    return parent if commit and _has_commit(source, parent) else ""


def _spec_requirements(source: Path, rev: str, capability: str) -> dict[str, str]:
    """The statement of each requirement in the base spec of `capability` at `rev`."""
    if not rev:
        return {}
    path = f"{_SPECS}/{capability}/spec.md"
    if path not in tree_files(source, rev, operation=GIT_OPERATION):
        return {}
    text = files_at(source, rev, [path], operation=GIT_OPERATION)[path]
    matches = list(_REQUIREMENT.finditer(text))
    found: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.end() : end].split(_SCENARIO, 1)[0]
        found[match["name"].strip()] = " ".join(block.split())
    return found


def _quote(text: str) -> str:
    return f"`{text[:120]}`" if text else "nothing"


def _moved_problems(
    proposal: StageProposal, source: Path, plan_rev: str, base_rev: str
) -> list[PlanProblem]:
    texts = MESSAGES.roadmap
    problems: list[PlanProblem] = []
    for spec in proposal.specs:
        if not spec.modified:
            continue
        planned = _spec_requirements(source, plan_rev, spec.capability)
        base = _spec_requirements(source, base_rev, spec.capability)
        # The archive applies a rename before a MODIFIED block, so a requirement under the new
        # name of a rename replaces the base text of the old name (#5340).
        base_names = spec.base_names()
        for requirement in spec.modified:
            name = base_names.get(requirement.name.strip(), requirement.name.strip())
            before = planned.get(name, "")
            after = base.get(name)
            if after is None:
                problems.append(
                    PlanProblem(
                        f"{_SPECS}/{spec.capability}/spec.md",
                        "spec-moved",
                        texts.plan_check_moved_missing.format(
                            capability=spec.capability, requirement=name
                        ),
                    )
                )
            elif before != after:
                problems.append(
                    PlanProblem(
                        f"{_SPECS}/{spec.capability}/spec.md",
                        "spec-moved",
                        texts.plan_check_moved_changed.format(
                            capability=spec.capability,
                            requirement=name,
                            before=_quote(before),
                            after=_quote(after),
                        ),
                    )
                )
    return problems


def _gate_problems(
    proposal: StageProposal,
    root: str,
    head: str,
    source: Path,
    base_rev: str,
    issue_body: str,
) -> list[PlanProblem]:
    tree = StagedTree(tree_files(source, head, operation=GIT_OPERATION))
    known, requirements = specs_at(source, base_rev, operation=GIT_OPERATION)
    return [
        PlanProblem(root, "stage", message)
        for message in check_proposal(
            proposal,
            known,
            tree,
            requirements=requirements,
            issue_body=issue_body,
        )
    ]


def _dependency_problems(
    proposal: StageProposal, root: str, reads: PlanReads, repo: str
) -> list[PlanProblem]:
    """One problem for each issue that the plan names in `## Dependencies` and that is still open
    (#3224). A plan merges after the issue that it must deliver first, so an open one holds it
    back. The read is the one of `PlanReads`, so the check reaches no network of its own."""
    texts = MESSAGES.roadmap
    path = f"{root}/{_PROPOSAL}"
    return [
        PlanProblem(
            path,
            "issue-dependency",
            texts.plan_check_issue_dependency.format(number=number),
        )
        for number in issue_dependencies(proposal.dependencies)
        if reads.get_issue(repo, number).state == "open"
    ]


def _size_problems(
    proposal: StageProposal,
    root: str,
    head: str,
    source: Path,
    title: str,
    body: str,
    paths: Sequence[str],
) -> list[PlanProblem]:
    """The groups of the plan that the stage measure faults (#3499). `measure_groups`, the function
    of the stage job, measures each group on the tracked files of `head`, with the item and the
    files `paths` of the change folder as the shared text. `body` is the body of the issue with no
    record block, as the store reads it for the stage job. The files are read from the checkout,
    not from `git show`, which strips the end of a text, so the figure is the figure of the stage
    job. A group above the budget `roadmap.stage.step_tokens` is a problem. A group that changes
    a file that exists, and packs no file, is a problem too: the step starts with none of the
    files that it changes. A group that only creates files packs none by nature, so it is no
    problem. The plan holds no estimate of the lines of a created file, so a created file counts
    one line."""
    texts = MESSAGES.roadmap
    budget = load_settings().roadmap.stage.step_tokens
    with checkout_at(source, head, operation=GIT_OPERATION) as tree:
        files = {
            path: (tree / path).read_text(encoding="utf-8", errors="replace") for path in paths
        }
        shared = shared_texts(title, body, files)
        measured = measure_groups(tree, proposal.groups, shared=shared)
    path = f"{root}/tasks.md"
    problems: list[PlanProblem] = []
    for number, item in enumerate(measured, start=1):
        title = item.group.title
        if item.tokens > budget:
            message = texts.plan_check_group_over_budget.format(
                number=number, title=title, tokens=item.tokens, budget=budget
            )
            problems.append(PlanProblem(path, "group-over-budget", message))
        if item.files == 0 and not set(item.group.changes) <= set(item.group.creates):
            message = texts.plan_check_group_no_files.format(number=number, title=title)
            problems.append(PlanProblem(path, "group-no-files", message))
    return problems


def _validate_problems(
    tool: OpenSpecTool, source: Path, change: str, files: Mapping[str, str]
) -> list[PlanProblem]:
    problem = validate_change(tool, source, change, files)
    if problem is None:
        return []
    return [PlanProblem(change, "openspec", line) for line in problem.splitlines() if line.strip()]


def plan_check(
    repo: str,
    number: int,
    source: Path,
    *,
    tool: OpenSpecTool,
    client: PlanReads | None = None,
    check_reader: CheckReader = read_check_runs,
) -> PlanCheckResult:
    """The problems of plan pull request `number` of `repo`, read in the checkout `source`.

    A pull request that has become the delivery of the item is no plan: the command reports no
    problem for it.
    """
    reads = client or _session_client()
    facts = read_pull(reads, repo, number)
    if not is_plan(facts):
        return PlanCheckResult(())
    owner, name = repo.split("/", 1)
    checks = check_reader(owner, name, facts.head_sha)
    problems = _pull_problems(facts, checks)
    issue = issue_number(facts.body)
    if issue is None:
        return PlanCheckResult(tuple(problems))

    git(source, "fetch", "--quiet", "origin", f"refs/pull/{number}/head", operation=GIT_OPERATION)
    head = git(source, "rev-parse", "FETCH_HEAD", operation=GIT_OPERATION)
    files = tree_files(source, head, operation=GIT_OPERATION)
    root, folder_problems = change_root(files, issue)
    if root is None:
        return PlanCheckResult(
            tuple(
                [
                    *problems,
                    *(
                        PlanProblem(_CHANGES, "change-folder", message)
                        for message in folder_problems
                    ),
                ]
            )
        )

    base_rev = _base_revision(source, facts)
    plan_rev = _plan_parent(source, head, root)
    changed = [path for path in files if path == root or path.startswith(f"{root}/")]
    change_files = files_at(source, head, changed, operation=GIT_OPERATION)
    try:
        proposal = read_change(change_files)
    except PlanReadError as exc:
        problems.append(
            PlanProblem(
                exc.path,
                "read",
                MESSAGES.roadmap.plan_check_read.format(path=exc.path, reason=exc.reason),
            )
        )
        return PlanCheckResult(
            tuple(
                [
                    *problems,
                    *_validate_problems(tool, source, root.rsplit("/", 1)[-1], change_files),
                ]
            )
        )

    planned = reads.get_issue(repo, issue)
    body, _ = split_record(planned.body or "", issue=f"#{issue}")
    problems.extend(_gate_problems(proposal, root, head, source, base_rev, body))
    problems.extend(_dependency_problems(proposal, root, reads, repo))
    problems.extend(_size_problems(proposal, root, head, source, planned.title, body, changed))
    problems.extend(_validate_problems(tool, source, root.rsplit("/", 1)[-1], change_files))
    problems.extend(_moved_problems(proposal, source, plan_rev, base_rev))
    return PlanCheckResult(tuple(problems))


def plan_check_requests(repo: str, number: int) -> tuple[PlannedRequest, ...]:
    """The reads a plan check makes, as a dry run lists them."""
    texts = MESSAGES.roadmap
    return (
        planned_session_read(
            f"/repos/{repo}/pulls/{number}", texts.plan_check_request_pull.format(number=number)
        ),
        planned_session_read(
            f"/repos/{repo}/issues/{number}", texts.plan_check_request_body.format(number=number)
        ),
        planned_session_read(
            f"/repos/{repo}/issues/<issue>",
            texts.plan_check_request_issue,
            condition=texts.plan_check_request_issue_condition,
        ),
        planned_session_read(
            f"/repos/{repo}/issues/<dependency>",
            texts.plan_check_request_dependency_issue,
        ),
        planned_session_read(
            f"/repos/{repo}/commits/<head>/check-runs?per_page={DEFAULT_GH_REST_PER_PAGE}",
            texts.plan_check_request_checks,
        ),
    )
