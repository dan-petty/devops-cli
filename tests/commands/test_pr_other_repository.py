"""`devops pr create` follows the rules of the repository that gets the pull request (#3767).

A repository whose base branch holds `openspec/config.yaml` plans with OpenSpec, as devops-cli
does: the body of a pull request needs the lines `Closes #<issue>` and `Change:`. Another
repository, such as an infrastructure repository with no OpenSpec, gets a draft with a title in
the form and the body it is given. `--head` names the branch of the pull request, so a checkout of
devops-cli opens a pull request in another repository. No case reaches GitHub: the files of the
repository are in the in-memory roadmap, and `gh` is the process fake.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.dry_run.state import set_dry_run
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.gh_process import answer_gh, gh_argv, mentions

REPO = "example/infra"
HEAD = "feat/19-node-memory-reservation"
LABELS = "".join(f'- name: "{name}"\n  color: "ededed"\n' for name in ("type/feature", "scope/k3s"))
TITLE = "feat(k3s): reserve memory for the system on each node"
PLAIN_BODY = "Reserve memory for the system and for kubelet, so a pod cannot take all of it."
NO_CLOSING_ISSUES = json.dumps(
    {
        "data": {
            "repository": {
                "pullRequest": {"closingIssuesReferences": {"totalCount": 0, "nodes": []}}
            }
        }
    }
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def infra(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The repository: its labels file and the pull request that gh opens, and no
    `openspec/config.yaml`."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    roadmap_store.seed_issue("feat(k3s): a pull request", pull_request=True)
    return roadmap_store


@pytest.fixture
def gh(gh_edge: ProcessFake) -> ProcessFake:
    """gh, which opens pull request 1 and finds that it closes no issue."""
    gh_edge.answer(
        ["gh", "pr", "create"], ProcessAnswer(stdout=f"https://example.com/{REPO}/pull/1\n")
    )
    gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
    return gh_edge


def _create(runner: CliRunner, body: str, *args: str) -> Any:
    return runner.invoke(
        app, ["create", "--title", TITLE, "--body", body, "--repo", REPO, "--head", HEAD, *args]
    )


def _creates(gh: ProcessFake) -> list[list[str]]:
    """The `gh pr create` commands that were sent."""
    return [argv for argv in gh_argv(gh) if argv[:2] == ["pr", "create"]]


@pytest.mark.usefixtures("infra")
def test_a_repository_without_openspec_gets_a_draft_with_the_body_it_is_given(
    runner: CliRunner, gh: ProcessFake
) -> None:
    result = _create(runner, PLAIN_BODY)
    created = _creates(gh)
    assert (result.exit_code, result.stderr, len(created)) == (0, "", 1), result.output
    args = created[0]
    assert (
        "--draft" in args,
        args[args.index("--head") + 1],
        args[args.index("--repo") + 1],
        args[args.index("--body") + 1],
    ) == (True, HEAD, REPO, PLAIN_BODY)


def test_a_repository_with_openspec_still_needs_the_closes_and_change_lines(
    runner: CliRunner, gh: ProcessFake, infra: InMemoryRoadmapStore
) -> None:
    infra.seed_file("openspec/config.yaml", "schema: spec-driven\n")
    result = _create(runner, PLAIN_BODY)
    assert (
        result.exit_code,
        _creates(gh),
        "no line `Closes #<issue>`" in result.stderr,
        "no line `Change:`" in result.stderr,
    ) == (1, [], True, True)


def test_the_openspec_file_of_the_base_branch_decides(
    runner: CliRunner, gh: ProcessFake, infra: InMemoryRoadmapStore
) -> None:
    """The default branch plans with OpenSpec, and the base branch `legacy` does not."""
    infra.seed_file("openspec/config.yaml", "schema: spec-driven\n")
    infra.seed_file(".github/labels.yml", LABELS, ref="legacy")
    result = _create(runner, PLAIN_BODY, "--base", "legacy")
    assert (result.exit_code, len(_creates(gh))) == (0, 1), result.output


@pytest.mark.usefixtures("infra")
def test_a_repository_without_openspec_still_checks_the_title(
    runner: CliRunner, gh: ProcessFake
) -> None:
    result = runner.invoke(
        app, ["create", "--title", "A plain title", "--body", PLAIN_BODY, "--repo", REPO]
    )
    assert (result.exit_code, _creates(gh), "is not in the form" in result.stderr) == (
        1,
        [],
        True,
    )


@pytest.mark.usefixtures("infra")
def test_the_fallback_opens_the_draft_from_the_head_it_is_given(
    runner: CliRunner, gh_edge: ProcessFake
) -> None:
    """The REST fallback posts `--head`, not the branch of the checkout that runs the command."""
    gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="main\n"))
    answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
    gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
    gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
    gh_edge.answer(
        ["gh", "api", f"repos/{REPO}"], ProcessAnswer(stdout='{"default_branch": "main"}')
    )
    post = {"html_url": f"https://example.com/{REPO}/pull/1", "number": 1}
    gh_edge.answer(
        mentions(f"repos/{REPO}/pulls", "title="), ProcessAnswer(stdout=json.dumps(post))
    )
    result = _create(runner, PLAIN_BODY)
    sent = gh_argv(gh_edge)
    lookup = next(argv for argv in sent if any("pulls?head=" in a for a in argv))
    posted = next(argv for argv in sent if any("title=" in a for a in argv))
    assert (
        result.exit_code,
        f"head={HEAD}" in posted,
        f"head=example:{HEAD}" in lookup[-1],
    ) == (0, True, True), result.output


@pytest.mark.usefixtures("infra")
def test_a_dry_run_names_the_head_and_checks_no_body_for_another_repository(
    runner: CliRunner, gh: ProcessFake, roadmap_store_repos: list[str]
) -> None:
    """A dry run reads nothing of GitHub, so it cannot know the rules of another repository: it
    checks the title, as it checks the scope of a title only in a real run."""
    set_dry_run(True)
    result = _create(runner, PLAIN_BODY)
    assert (result.exit_code, gh.calls, roadmap_store_repos, HEAD in result.stdout) == (
        0,
        [],
        [],
        True,
    ), result.output
