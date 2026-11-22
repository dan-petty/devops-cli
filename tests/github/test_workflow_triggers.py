"""Whether a workflow file can start a check on a pull request: its triggers, and the branch and
path filters of each pull request trigger, by the rules of GitHub's workflow syntax reference
(#5144, #5408).

`starts_on_pull_request` is pure, so each test gives it a workflow text and the change of a pull
request. The rows of GitHub's filter pattern cheat sheet are cited as the reference gives them.
"""

from __future__ import annotations

import json

import pytest

from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.workflow_triggers import PullRequestChange, starts_on_pull_request

_JOBS = 'jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: "true"\n'


def _workflow(on: object) -> str:
    """A workflow whose bare `on` key, which YAML 1.1 reads as `True`, holds `on` as JSON, which
    is YAML flow syntax."""
    return f"name: CI\non: {json.dumps(on)}\n{_JOBS}"


def _filtered(key: str, *patterns: object, event: str = "pull_request") -> str:
    """A workflow whose `event` has the one filter `key` with `patterns`."""
    return _workflow({event: {key: list(patterns)}})


def _change(*files: str, base: str = "main") -> PullRequestChange:
    """A pull request into `base` that changes `files`."""
    return PullRequestChange(base=base, files=files)


@pytest.mark.parametrize(
    ("pattern", "path", "takes"),
    [
        ("*", "README.md", True),
        ("*", "server.rb", True),
        ("*", "docs/README.md", False),
        ("**", "all/the/files.md", True),
        ("**", ".github/renovate.json", True),
        ("*.js", "app.js", True),
        ("*.js", "index.js", True),
        ("*.js", "js/index.js", False),
        ("docs/*", "docs/README.md", True),
        ("docs/*", "docs/file.txt", True),
        ("docs/*", "docs/mona/octocat.txt", False),
        ("docs/**", "docs/README.md", True),
        ("docs/**", "docs/mona/octocat.txt", True),
        ("docs/**/*.md", "docs/README.md", True),
        ("docs/**/*.md", "docs/mona/hello-world.md", True),
        ("docs/**/*.md", "docs/a/markdown/file.md", True),
        ("**/docs/**", "docs/hello.md", True),
        ("**/docs/**", "dir/docs/my-file.txt", True),
        ("**/docs/**", "space/docs/plan/space.doc", True),
        ("**/README.md", "README.md", True),
        ("**/README.md", "js/README.md", True),
        ("**/*src/**", "a/src/app.js", True),
        ("**/*src/**", "my-src/code/js/app.js", True),
        ("**/*-post.md", "my-post.md", True),
        ("**/*-post.md", "path/their-post.md", True),
        ("**/migrate-*.sql", "migrate-10909.sql", True),
        ("**/migrate-*.sql", "db/migrate-v1.0.sql", True),
        ("**/migrate-*.sql", "db/sept/migrate-v1.sql", True),
        ("k8s/**", "README.md", False),
        ("**/*.yml", ".github/renovate.json", False),
    ],
)
def test_a_paths_pattern_matches_as_the_cheat_sheet_says(
    pattern: str, path: str, takes: bool
) -> None:
    """`*` stops at `/`, a `**` segment crosses folders, and a path must match from the root. A
    name that starts with `.` matches too, so `.github/renovate.json` is a change like any other."""
    assert starts_on_pull_request(_filtered("paths", pattern), _change(path)) is takes


@pytest.mark.parametrize(
    ("pattern", "base", "takes"),
    [
        ("feature/*", "feature/my-branch", True),
        ("feature/*", "feature/your-branch", True),
        ("feature/*", "feature/beta-a/my-branch", False),
        ("feature/**", "feature/beta-a/my-branch", True),
        ("feature/**", "feature/your-branch", True),
        ("feature/**", "feature/mona/the/octocat", True),
        ("main", "main", True),
        ("releases/mona-the-octocat", "releases/mona-the-octocat", True),
        ("*", "main", True),
        ("*", "releases", True),
        ("*", "all/the/branches", False),
        ("**", "all/the/branches", True),
        ("*feature", "mona-feature", True),
        ("*feature", "feature", True),
        ("*feature", "ver-10-feature", True),
        ("v2*", "v2", True),
        ("v2*", "v2.0", True),
        ("v2*", "v2.9", True),
        ("releases/**", "main", False),
    ],
)
def test_a_branches_pattern_matches_the_base_branch_as_the_cheat_sheet_says(
    pattern: str, base: str, takes: bool
) -> None:
    """`branches` of a pull request event matches the branch that the pull request targets."""
    change = _change("src/app.py", base=base)
    assert starts_on_pull_request(_filtered("branches", pattern), change) is takes


@pytest.mark.parametrize(
    ("patterns", "path", "takes"),
    [
        (("sub-project/**", "!sub-project/docs/**"), "sub-project/index.js", True),
        (("sub-project/**", "!sub-project/docs/**"), "sub-project/src/index.js", True),
        (("sub-project/**", "!sub-project/docs/**"), "sub-project/docs/readme.md", False),
        (("*.md", "!README.md"), "hello.md", True),
        (("*.md", "!README.md"), "README.md", False),
        (("*.md", "!README.md"), "docs/hello.md", False),
        (("*.md", "!README.md", "README*"), "hello.md", True),
        (("*.md", "!README.md", "README*"), "README.md", True),
        (("*.md", "!README.md", "README*"), "README.doc", True),
    ],
)
def test_the_last_pattern_that_matches_decides(
    patterns: tuple[str, ...], path: str, takes: bool
) -> None:
    """A `!` pattern after a positive match excludes the path, and a positive pattern after it
    includes the path again: wcmatch's own `NEGATE` flag ignores that order."""
    assert starts_on_pull_request(_filtered("paths", *patterns), _change(path)) is takes


def test_a_negative_branch_pattern_excludes_the_base_branch() -> None:
    workflow = _filtered("branches", "releases/**", "!releases/*-alpha")
    assert (
        starts_on_pull_request(workflow, _change("a.py", base="releases/10")),
        starts_on_pull_request(workflow, _change("a.py", base="releases/10-alpha")),
    ) == (True, False)


@pytest.mark.parametrize(
    ("files", "takes"),
    [
        (("docs/README.md",), False),
        (("docs/README.md", "docs/mona/octocat.txt"), False),
        (("docs/README.md", "src/app.py"), True),
    ],
)
def test_paths_ignore_skips_a_pull_request_only_when_it_holds_every_changed_file(
    files: tuple[str, ...], takes: bool
) -> None:
    assert starts_on_pull_request(_filtered("paths-ignore", "docs/**"), _change(*files)) is takes


@pytest.mark.parametrize(("base", "takes"), [("mona/octocat", False), ("main", True)])
def test_branches_ignore_skips_a_pull_request_into_a_matching_branch(
    base: str, takes: bool
) -> None:
    workflow = _filtered("branches-ignore", "mona/octocat")
    assert starts_on_pull_request(workflow, _change("a.py", base=base)) is takes


@pytest.mark.parametrize(
    ("base", "path", "takes"),
    [("main", "k8s/app.yaml", True), ("main", "README.md", False), ("dev", "k8s/app.yaml", False)],
)
def test_the_branch_and_the_path_filter_must_both_take_the_pull_request(
    base: str, path: str, takes: bool
) -> None:
    workflow = _workflow({"pull_request": {"branches": ["main"], "paths": ["k8s/**"]}})
    assert starts_on_pull_request(workflow, _change(path, base=base)) is takes


@pytest.mark.parametrize(
    ("workflow", "takes"),
    [
        (_filtered("paths", "**"), False),
        (_filtered("paths-ignore", "docs/**"), False),
        (_workflow({"pull_request": None}), True),
    ],
    ids=["paths", "paths-ignore", "no-filter"],
)
def test_a_pull_request_that_changes_no_file_is_taken_by_no_path_filter(
    workflow: str, takes: bool
) -> None:
    """GitHub starts no filtered workflow for an empty diff; a workflow with no path filter runs."""
    assert starts_on_pull_request(workflow, _change()) is takes


@pytest.mark.parametrize(
    ("text", "takes"),
    [
        (f"name: CI\non: pull_request\n{_JOBS}", True),
        (f"name: CI\non: pull_request_target\n{_JOBS}", True),
        (_workflow(["push", "pull_request_target"]), True),
        (_workflow(["push", "workflow_dispatch"]), False),
        (f"name: CI\non:\n  pull_request:\n{_JOBS}", True),
        (f"name: CI\n'on':\n  pull_request_target:\n{_JOBS}", True),
        (_workflow({"push": {"paths": ["**"]}}), False),
        (_workflow({"pull_request_target": {"paths": ["k8s/**"]}}), False),
        (
            _workflow({"pull_request": {"paths": ["k8s/**"]}, "pull_request_target": None}),
            True,
        ),
        (f"name: None\n{_JOBS}", False),
        ("- not\n- a mapping\n", False),
    ],
    ids=[
        "string",
        "string-target",
        "list-target",
        "list-push-only",
        "bare-on-key",
        "quoted-on-key",
        "push-mapping",
        "target-path-filter-skips",
        "second-event-has-no-filter",
        "no-trigger",
        "no-mapping",
    ],
)
def test_the_triggers_of_a_workflow_decide_for_a_readme_change(text: str, takes: bool) -> None:
    """`pull_request` and `pull_request_target` are the triggers that start a check on a pull
    request; the filters of each one judge it on its own."""
    assert starts_on_pull_request(text, _change("README.md")) is takes


def test_a_workflow_that_is_not_valid_yaml_is_no_answer() -> None:
    """The caller keeps the pending check for a file that it cannot read."""
    with pytest.raises(GitHubUnreadError, match="not valid YAML"):
        starts_on_pull_request("name: [unclosed\n", _change("README.md"))


@pytest.mark.parametrize(
    ("workflow", "change"),
    [
        (_filtered("paths", "k8s/**"), PullRequestChange(base="main", files=None)),
        (_filtered("paths-ignore", "docs/**"), PullRequestChange(base="main", files=None)),
        (_filtered("branches", "releases/**"), _change("a.py", base="")),
        (_workflow({"pull_request": {"paths": "k8s/**"}}), _change("README.md")),
        (_filtered("paths", "k8s/**", 5), _change("README.md")),
        (
            _workflow({"pull_request": {"paths": ["k8s/**"], "paths-ignore": ["docs/**"]}}),
            _change("README.md"),
        ),
        (
            _workflow({"pull_request": {"branches": ["dev"], "branches-ignore": ["main"]}}),
            _change("README.md"),
        ),
        (_filtered("paths", "*.jsx?"), _change("page.js")),
        (_filtered("branches", "v[12].[0-9]+.[0-9]+"), _change("a.py", base="v1.10.1")),
        (_filtered("paths", "**.js"), _change("src/js/app.js")),
        (
            _filtered("branches", "releases/**-alpha"),
            _change("a.py", base="releases/beta/3-alpha"),
        ),
        (_workflow({"pull_request": {"types": ["closed"]}}), _change("README.md")),
    ],
    ids=[
        "paths-files-unknown",
        "paths-ignore-files-unknown",
        "branches-base-unknown",
        "filter-not-a-list",
        "pattern-not-a-string",
        "both-path-forms",
        "both-branch-forms",
        "question-mark-quantifier",
        "plus-quantifier",
        "globstar-inside-a-segment",
        "globstar-inside-a-branch-segment",
        "types-only",
    ],
)
def test_a_filter_that_cannot_be_judged_takes_the_pull_request(
    workflow: str, change: PullRequestChange
) -> None:
    """The workflow can then start a check, so the caller keeps the wait. GitHub reads `?` and `+`
    as quantifiers and `**` inside a segment as any characters, which wcmatch does not."""
    assert starts_on_pull_request(workflow, change) is True


def test_a_branch_filter_still_judges_a_pull_request_whose_files_are_unknown() -> None:
    change = PullRequestChange(base="main", files=None)
    assert starts_on_pull_request(_filtered("branches", "releases/**"), change) is False
