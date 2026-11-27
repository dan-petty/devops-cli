"""Row 16 of `devops repos onboard`: whether the repository plans with OpenSpec (#3770)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_OPENSPEC_CONFIG_PATH, CONST_OPENSPEC_SPECS_DIR
from devops_cli.config.settings import load_settings
from devops_cli.core.process import DefaultProcessRunner, get_process_runner, set_process_runner
from devops_cli.github.onboard.model import (
    OnboardOptions,
    OnboardReport,
    Row,
    RowContext,
    RowState,
)
from devops_cli.github.onboard.run import onboard_repository
from devops_cli.github.repo_ref import RepoRef
from devops_cli.github.session import get_github_session
from devops_cli.openspec.tool import isolated_openspec, output_of
from tests.support.github_repository import (
    REPO,
    TEMPLATE_BRANCH,
    OnboardHarness,
    labels_text,
)

SPECS_PLACEHOLDER = f"{CONST_OPENSPEC_SPECS_DIR}/.gitkeep"
CONFIG = """schema: spec-driven
context: |
  Product: a sample repository, for its readers.
rules:
  proposal:
    - State the premise.
  specs:
    - Write each scenario as a test.
  design:
    - Name a rejected alternative.
  tasks:
    - Tick a task when its work is merged.
"""


def _ctx(
    harness: OnboardHarness, *, template_head: str | None = None, template_pull: int | None = None
) -> RowContext:
    """The context of a run of row 16, with the template pull request that row 9 recorded."""
    options = OnboardOptions(repo=RepoRef(REPO), confirm=False, workdir=harness.workdir)
    return RowContext(
        options=options,
        repo_payload={"default_branch": "main"},
        template_head=template_head,
        template_pull=template_pull,
    )


def _commit(harness: OnboardHarness, files: dict[str, str]) -> str:
    """A commit of REPO that holds `files` on top of its default branch, and its sha."""
    state = harness.state
    sha = f"seed{len(state.commits)}"
    state.commits[sha] = {**state.commits[state.refs["main"]], **files}
    return sha


def _default_branch_holds(harness: OnboardHarness, files: dict[str, str]) -> None:
    """Make the default branch of REPO hold `files`."""
    harness.state.refs["main"] = _commit(harness, files)


def _confirm(harness: OnboardHarness) -> OnboardReport:
    """One `--confirm` run of the rows over REPO."""
    options = OnboardOptions(repo=RepoRef(REPO), confirm=True, workdir=harness.workdir)
    return onboard_repository(options, session=get_github_session(), settings=load_settings())


def _row(report: OnboardReport, number: int) -> Row:
    """The row `number` of `report`."""
    return next(row for row in report.rows if row.number == number)


def _template_tree(harness: OnboardHarness) -> dict[str, str]:
    """The path and text of each entry of the last `git/trees` request that row 9 sent."""
    request = next(
        sent
        for sent in reversed(harness.api.sent)
        if sent.method == "POST" and sent.url.path.endswith("/git/trees")
    )
    return {entry["path"]: entry["content"] for entry in json.loads(request.content)["tree"]}


def test_openspec_row_reads_present(onboard_github: OnboardHarness) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    _default_branch_holds(harness, {CONST_OPENSPEC_CONFIG_PATH: CONFIG, SPECS_PLACEHOLDER: ""})

    row = openspec_row(get_github_session(), _ctx(harness))

    assert row.state is RowState.PRESENT
    assert row.failing is False
    assert row.reason is None
    assert harness.writes() == []


def test_openspec_row_reads_missing(onboard_github: OnboardHarness) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github

    row = openspec_row(get_github_session(), _ctx(harness))

    assert row.state is RowState.MISSING
    assert CONST_OPENSPEC_CONFIG_PATH in str(row.reason)
    assert row.failing is True
    assert harness.writes() == []


def test_openspec_row_reads_invalid_for_another_schema(onboard_github: OnboardHarness) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    _default_branch_holds(
        harness,
        {
            CONST_OPENSPEC_CONFIG_PATH: CONFIG.replace("schema: spec-driven", "schema: another"),
            SPECS_PLACEHOLDER: "",
        },
    )

    row = openspec_row(get_github_session(), _ctx(harness))

    assert row.state is RowState.INVALID
    assert "another" in str(row.reason)
    assert row.failing is True


def test_openspec_row_reads_invalid_for_text_that_does_not_parse(
    onboard_github: OnboardHarness,
) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    _default_branch_holds(
        harness, {CONST_OPENSPEC_CONFIG_PATH: "schema: [unclosed\n", SPECS_PLACEHOLDER: ""}
    )

    row = openspec_row(get_github_session(), _ctx(harness))

    assert row.state is RowState.INVALID
    assert "YAML" in str(row.reason)
    assert row.failing is True


def test_openspec_row_reads_invalid_with_no_specs_folder(onboard_github: OnboardHarness) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    _default_branch_holds(harness, {CONST_OPENSPEC_CONFIG_PATH: CONFIG})

    row = openspec_row(get_github_session(), _ctx(harness))

    assert row.state is RowState.INVALID
    assert CONST_OPENSPEC_SPECS_DIR in str(row.reason)
    assert "copier update" in str(row.reason)
    assert SPECS_PLACEHOLDER in str(row.reason)
    assert row.failing is True


def test_openspec_row_reads_waiting_on_the_template_head(onboard_github: OnboardHarness) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    head = _commit(harness, {CONST_OPENSPEC_CONFIG_PATH: CONFIG, SPECS_PLACEHOLDER: ""})

    row = openspec_row(get_github_session(), _ctx(harness, template_head=head, template_pull=42))

    assert row.state is RowState.WAITING
    assert "#42" in str(row.reason)
    assert row.failing is False


def test_openspec_row_reads_waiting_when_the_template_head_adds_the_specs_folder(
    onboard_github: OnboardHarness,
) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    _default_branch_holds(harness, {CONST_OPENSPEC_CONFIG_PATH: CONFIG})
    head = _commit(harness, {SPECS_PLACEHOLDER: ""})

    row = openspec_row(get_github_session(), _ctx(harness, template_head=head, template_pull=42))

    assert row.state is RowState.WAITING
    assert "#42" in str(row.reason)


def test_openspec_row_reads_missing_when_the_template_head_lacks_the_specs_folder(
    onboard_github: OnboardHarness,
) -> None:
    from devops_cli.github.onboard.openspec_row import openspec_row

    harness = onboard_github
    head = _commit(harness, {CONST_OPENSPEC_CONFIG_PATH: CONFIG})

    row = openspec_row(get_github_session(), _ctx(harness, template_head=head, template_pull=42))

    assert row.state is RowState.MISSING
    assert CONST_OPENSPEC_CONFIG_PATH in str(row.reason)
    assert CONST_OPENSPEC_SPECS_DIR in str(row.reason)
    assert "#42" in str(row.reason)


def test_the_template_pull_request_adds_the_openspec_files_of_the_template(
    onboard_github: OnboardHarness,
) -> None:
    from tests.support.github_repository import OPENSPEC_CONFIG

    harness = onboard_github

    _confirm(harness)

    assert [pull["state"] for pull in harness.state.pulls] == ["open"]
    entries = _template_tree(harness)
    assert entries[".github/labels.yml"] == labels_text("")
    assert entries[CONST_OPENSPEC_CONFIG_PATH] == OPENSPEC_CONFIG
    assert entries[SPECS_PLACEHOLDER] == ""


def test_a_config_file_that_exists_stays(onboard_github: OnboardHarness) -> None:
    harness = onboard_github
    seeded = "# the config of this repository\nschema: spec-driven\n"
    _default_branch_holds(harness, {CONST_OPENSPEC_CONFIG_PATH: seeded})

    report = _confirm(harness)

    assert CONST_OPENSPEC_CONFIG_PATH not in _row(report, 9).changes
    assert CONST_OPENSPEC_CONFIG_PATH not in _template_tree(harness)
    session = get_github_session()
    assert session.client.get_file_at(REPO, CONST_OPENSPEC_CONFIG_PATH, TEMPLATE_BRANCH) == seeded


def test_a_second_confirm_adds_no_openspec_file(onboard_github: OnboardHarness) -> None:
    harness = onboard_github

    _confirm(harness)
    commits, pulls = len(harness.state.commits), len(harness.state.pulls)

    _confirm(harness)

    assert (len(harness.state.commits), len(harness.state.pulls)) == (commits, pulls)
    assert [pull["state"] for pull in harness.state.pulls] == ["open"]


@pytest.mark.live("openspec")
def test_the_merged_tree_passes_openspec_validate_specs(
    onboard_github: OnboardHarness, tmp_path: Path
) -> None:
    """The tree that the onboarding pull request leaves behind passes the pinned validator. The
    validator runs under the real process runner, because the process fake answers a call that it
    does not know with exit 0, and a fixed answer would pass whatever the tree holds."""
    harness = onboard_github

    _confirm(harness)
    harness.state.merge_template_pull()

    tree = tmp_path / "merged"
    for path, text in harness.state.commits[harness.state.refs["main"]].items():
        (tree / path).parent.mkdir(parents=True, exist_ok=True)
        (tree / path).write_text(text, encoding="utf-8")

    previous = get_process_runner()
    set_process_runner(DefaultProcessRunner())
    try:
        with isolated_openspec() as tool:
            run = tool.run(("validate", "--specs", "--strict"), tree)
    finally:
        set_process_runner(previous)

    assert run.returncode == 0, output_of(run)
    assert (tree / CONST_OPENSPEC_CONFIG_PATH).is_file()
    assert (tree / SPECS_PLACEHOLDER).is_file()
    assert harness.calls("openspec") == []
