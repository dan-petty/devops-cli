"""Row 16: whether the repository plans with OpenSpec (#3770).

The row reads `openspec/config.yaml` and the `openspec/specs/` folder at the default branch. It
reads `present` when the file names the schema `spec-driven` and the folder exists, `missing` when
the default branch holds no config file, and `invalid` when a condition fails. Row 9 adds the
OpenSpec files of the repository template to the template pull request, so the row reads `waiting`
while the head of that pull request passes each condition. The row sends no write.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import yaml

from devops_cli.config.constants import CONST_OPENSPEC_CONFIG_PATH, CONST_OPENSPEC_SPECS_DIR
from devops_cli.github.onboard.model import Row, RowContext, RowState

if TYPE_CHECKING:
    from devops_cli.github.session import GitHubSession

ROW_NUMBER: Final[int] = 16
ROW_NAME: Final[str] = "OpenSpec"
# The schema that the planner of the stage job reads.
_OPENSPEC_SCHEMA: Final[str] = "spec-driven"


@dataclass(frozen=True)
class _Setup:
    """What one commit holds of the setup: whether the config file is there, and each condition of
    `present` that it fails."""

    has_config: bool
    failures: tuple[str, ...]

    @property
    def complete(self) -> bool:
        """Whether the commit passes each condition of `present`."""
        return not self.failures


def _config_failure(text: str) -> str | None:
    """Why the text of the config file fails its condition, or None."""
    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError:
        return f"{CONST_OPENSPEC_CONFIG_PATH} does not parse as YAML"
    if not isinstance(config, dict):
        return f"{CONST_OPENSPEC_CONFIG_PATH} is no YAML mapping"
    schema = config.get("schema")
    if schema != _OPENSPEC_SCHEMA:
        return f"{CONST_OPENSPEC_CONFIG_PATH} names schema {schema!r}, not {_OPENSPEC_SCHEMA}"
    return None


def _specs_failure(session: GitHubSession, repo: str, ref: str) -> str | None:
    """Why the specs folder fails its condition at `ref`, with the step that adds it, or None."""
    if session.client.folder_exists_at(repo, CONST_OPENSPEC_SPECS_DIR, ref):
        return None
    return (
        f"{CONST_OPENSPEC_SPECS_DIR}/ is absent: the next `copier update` of the repository "
        f"template, which Renovate brings, adds it, or commit {CONST_OPENSPEC_SPECS_DIR}/.gitkeep"
    )


def _read_setup(session: GitHubSession, repo: str, ref: str) -> _Setup:
    """The setup at `ref`, and each condition of `present` that it fails."""
    text = session.client.get_file_at(repo, CONST_OPENSPEC_CONFIG_PATH, ref)
    failures: list[str] = []
    if text is None:
        failures.append(f"{CONST_OPENSPEC_CONFIG_PATH} is absent")
    else:
        failure = _config_failure(text)
        if failure is not None:
            failures.append(failure)
    specs = _specs_failure(session, repo, ref)
    if specs is not None:
        failures.append(specs)
    return _Setup(has_config=text is not None, failures=tuple(failures))


def _reason(branch: _Setup, head: _Setup | None, pull: int | None) -> str:
    """The reason of a row off its baseline: each failed condition of the default branch, then
    each one that the head of the open template pull request fails."""
    lines = list(branch.failures)
    if head is not None and not head.complete:
        name = f"#{pull}" if pull is not None else "the open template pull request"
        lines.extend(f"{name} fails: {failure}" for failure in head.failures)
    return "; ".join(lines)


def _waiting_reason(pull: int | None) -> str:
    """The reason of a row that waits for the merge of the template pull request."""
    if pull is None:
        return "the open template pull request holds the OpenSpec setup; merge it"
    return f"#{pull} holds the OpenSpec setup; merge it"


def openspec_row(session: GitHubSession, ctx: RowContext) -> Row:
    """Row 16: `present`, `missing`, `invalid`, or `waiting` while the head of the open template
    pull request passes each condition of `present`."""
    branch = _read_setup(session, ctx.repo, ctx.default_branch)
    if branch.complete:
        return Row(ROW_NUMBER, ROW_NAME, RowState.PRESENT)
    head = None if ctx.template_head is None else _read_setup(session, ctx.repo, ctx.template_head)
    if head is not None and head.complete:
        return Row(
            ROW_NUMBER, ROW_NAME, RowState.WAITING, reason=_waiting_reason(ctx.template_pull)
        )
    state = RowState.MISSING if not branch.has_config else RowState.INVALID
    return Row(ROW_NUMBER, ROW_NAME, state, reason=_reason(branch, head, ctx.template_pull))


__all__ = ["ROW_NAME", "ROW_NUMBER", "openspec_row"]
