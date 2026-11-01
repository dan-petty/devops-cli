"""Run a fixture of `devops roadmap eval implement` and report it (#3030).

A run clones this repository at the base commit of the fixture into a temporary folder, takes the
remote away, writes the plan of the fixture over the change folder and commits it, then runs the
group through `run_step`, the path the Job uses, with the item of the fixture. So the run reads
nothing from GitHub, pushes nothing and leaves the checkout it cloned from as it was. Then it
evaluates the six properties (`implement_eval_properties`): the four of a diff on the diff of the
result, the two of commands in the tree of a done step.

A check of the recorded results of a fixture makes no model call. It evaluates the four diff
properties of each recorded diff and compares the failed ones with the record. With commands, it
clones the base, applies the diff, runs the two command properties too and compares all six.
"""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from pydantic import BaseModel, ConfigDict

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import (
    CONST_ROADMAP_EVAL_IMPLEMENT_REPORTS,
    CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.exceptions.roadmap import ImplementEvalError, RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.implement_eval import (
    ALL_PROPERTIES,
    COMMAND_PROPERTIES,
    DIFF_PROPERTIES,
    LoadedCase,
)
from devops_cli.roadmap.implement_eval_properties import (
    PropertyResult,
    Status,
    command_results,
    diff_results,
    no_tree,
    skipped,
)
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from devops_cli.roadmap.store import Item

_OPERATION = "roadmap.eval.implement"
_EVAL_NAME = "devops eval"
_EVAL_EMAIL = "eval@example.com"
_ISSUE_URL = "https://example.com/issues/{number}"
_ORIGIN = "origin"
RECORDED = "recorded"
REFUSED = "refused"


class FixtureItems:
    """The roadmap of a fixture: it holds its one item, and `run_step` reads it in place of the
    issue on GitHub."""

    def __init__(self, loaded: LoadedCase) -> None:
        self._item = Item(
            number=loaded.case.issue,
            title=loaded.case.title,
            url=_ISSUE_URL.format(number=loaded.case.issue),
            body=loaded.body,
        )

    def item(self, number: int) -> Item | None:
        """The item of the fixture, or None for another issue."""
        return self._item if number == self._item.number else None


class PropertyRecord(BaseModel):
    """A property as the report holds it."""

    model_config = ConfigDict(frozen=True)

    name: str
    status: str
    detail: str = ""


class ResultReport(BaseModel):
    """One result of one fixture: a run of the step, or a recorded diff. `status` is the end of a
    step (`done`, `stopped` or `refused`) or `recorded`. `expected` and `matches` are set for a
    recorded result: the properties it is recorded to fail, and whether it fails exactly those."""

    model_config = ConfigDict(frozen=True)

    fixture: str
    result: str
    issue: int
    group: int
    status: str
    reason: str = ""
    properties: tuple[PropertyRecord, ...]
    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    seconds: float = 0.0
    expected: tuple[str, ...] | None = None
    matches: bool | None = None

    @property
    def first_failed(self) -> str | None:
        """The first property that failed, in the order of the properties."""
        return next((p.name for p in self.properties if p.status == Status.FAIL.value), None)

    def count(self, status: Status) -> int:
        """How many properties ended `status`."""
        return sum(p.status == status.value for p in self.properties)


class RunReport(BaseModel):
    """The report of a run: the model (empty for a check of recorded results) and each result."""

    model_config = ConfigDict(frozen=True)

    model: str = ""
    results: tuple[ResultReport, ...]

    def count(self, status: Status) -> int:
        """How many properties of all results ended `status`."""
        return sum(result.count(status) for result in self.results)

    @property
    def differing(self) -> int:
        """How many recorded results fail other properties than their record says."""
        return sum(result.matches is False for result in self.results)


def _records(results: Sequence[PropertyResult]) -> tuple[PropertyRecord, ...]:
    return tuple(
        PropertyRecord(name=r.prop.value, status=r.status.value, detail=r.detail) for r in results
    )


# ── The scratch clone ─────────────────────────────────────────────────────────────────────


def make_clone(loaded: LoadedCase, repo: Path, work: Path) -> Path:
    """A clone of `repo` in `work/clone` at the base of the fixture, with no remote, a local
    identity, and the plan of the fixture committed in the change folder. Returns its path. The
    clone shares the objects of `repo`, so it copies none and links none: a link fails when the
    temporary folder is on another file system. Raises `ImplementEvalError` when `repo` lacks the
    base commit."""
    clone = work / "clone"
    git(
        work,
        "clone",
        "--shared",
        "--no-checkout",
        "--quiet",
        str(repo),
        str(clone),
        operation=_OPERATION,
    )
    git(clone, "remote", "remove", _ORIGIN, operation=_OPERATION)
    for key, value in (
        ("user.name", _EVAL_NAME),
        ("user.email", _EVAL_EMAIL),
        ("commit.gpgsign", "false"),
    ):
        git(clone, "config", key, value, operation=_OPERATION)
    try:
        git(clone, "checkout", "--quiet", "--detach", loaded.case.base, operation=_OPERATION)
    except GitOperationError as exc:
        raise ImplementEvalError(
            MESSAGES.roadmap.eval_implement_no_commit.format(name=loaded.name, sha=loaded.case.base)
        ) from exc
    folder = clone / loaded.tasks_path
    folder.parent.mkdir(parents=True, exist_ok=True)
    for name, text in loaded.plan.items():
        (folder.parent / name).write_text(text, encoding="utf-8")
    git(clone, "add", "-A", operation=_OPERATION)
    if git(clone, "status", "--porcelain", operation=_OPERATION):
        message = f"docs(openspec): the plan of the fixture (#{loaded.case.issue})"
        git(clone, "commit", "--quiet", "-m", message, operation=_OPERATION)
    return clone


def _result_diff(clone: Path, start: str) -> str:
    """The diff from the commit `start` to the checkout, as the step committed it: no rename, no
    external program, and the whole text, which `git` of `clone_git` would strip."""
    done = run_subprocess(
        [
            BIN_GIT,
            "-C",
            str(clone),
            "diff",
            "--no-color",
            "--no-ext-diff",
            "--no-textconv",
            "--no-renames",
            start,
            "HEAD",
        ],
        quiet=True,
        check=True,
    )
    return done.stdout


# ── The model and the report folder ───────────────────────────────────────────────────────


def eval_model(name: str | None) -> tuple[Any, int, str]:
    """The model of a run, the window of its task, and its name. `name` replaces the model of the
    task `ai.tasks.implement`; the provider and the gateway stay those of the task."""
    from devops_cli.ai.client.factory import get_task_model
    from devops_cli.config.settings import load_settings

    settings = load_settings()
    if name is not None:
        tasks = settings.ai.tasks
        swapped = tasks.model_copy(
            update={"implement": tasks.implement.model_copy(update={"model": name})}
        )
        settings = settings.model_copy(
            update={"ai": settings.ai.model_copy(update={"tasks": swapped})}
        )
    task = settings.ai.for_task("implement")
    return get_task_model("implement", settings=settings), task.context_window, task.model


def report_directory() -> Path:
    """The folder of the JSON reports, under the data directory."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    return resolve_data_path(load_settings().data.dir) / CONST_ROADMAP_EVAL_IMPLEMENT_REPORTS


# ── A run ─────────────────────────────────────────────────────────────────────────────────


def _step_properties(
    loaded: LoadedCase, clone: Path, start: str, outcome: StepOutcome
) -> list[PropertyResult]:
    """The six properties of a step: the commands run in the tree of a done step, and a stopped
    step leaves them skipped."""
    if outcome.status is StepStatus.DONE:
        diff = _result_diff(clone, start)
        return [
            *diff_results(loaded, diff, removed=outcome.removed),
            *command_results(loaded, clone),
        ]
    return [
        *diff_results(loaded, outcome.diff, cut=outcome.diff_cut, removed=outcome.removed),
        *no_tree(outcome.reason),
    ]


def run_case(loaded: LoadedCase, *, repo: Path, model: Any, window: int) -> ResultReport:
    """Run the group of the fixture with `model`, in a scratch clone of `repo`, and evaluate the
    properties. A step that refuses to start (inputs over the window) is reported as `refused`
    with its properties skipped. Raises `ImplementEvalError` when `repo` lacks the base commit,
    and `AICredentialsError` when the model refuses the key."""
    case = loaded.case
    with TemporaryDirectory(prefix="devops-eval-") as work:
        clone = make_clone(loaded, repo, Path(work))
        start = git(clone, "rev-parse", "HEAD", operation=_OPERATION)
        began = time.monotonic()
        try:
            outcome = run_step(
                FixtureItems(loaded),
                item=case.issue,
                group=case.group,
                source=clone,
                model=model,
                window=window,
            )
        except RoadmapImplementError as refusal:
            reason = str(refusal)
            return ResultReport(
                fixture=case.name,
                result=REFUSED,
                issue=case.issue,
                group=case.group,
                status=REFUSED,
                reason=reason,
                properties=_records(skipped(ALL_PROPERTIES, reason)),
            )
        seconds = time.monotonic() - began
        properties = _step_properties(loaded, clone, start, outcome)
    return ResultReport(
        fixture=case.name,
        result="step",
        issue=case.issue,
        group=case.group,
        status=outcome.status.value,
        reason=outcome.reason,
        properties=_records(properties),
        requests=outcome.requests,
        tool_calls=outcome.tool_calls,
        input_tokens=outcome.input_tokens,
        output_tokens=outcome.output_tokens,
        seconds=seconds,
    )


# ── A check of the recorded results ───────────────────────────────────────────────────────


def _applied_commands(loaded: LoadedCase, repo: Path, diff: str) -> list[PropertyResult]:
    """The two command properties of the recorded `diff`, run in a scratch clone with the diff
    applied. A diff that does not apply leaves them skipped, with git's reason."""
    with TemporaryDirectory(prefix="devops-eval-") as work:
        clone = make_clone(loaded, repo, Path(work))
        patch = Path(work) / "recorded.diff"
        patch.write_text(diff, encoding="utf-8")
        try:
            git(clone, "apply", "--whitespace=nowarn", str(patch), operation=_OPERATION)
        except GitOperationError as exc:
            reason = MESSAGES.roadmap.eval_implement_apply_failed.format(reason=exc)
            return skipped(COMMAND_PROPERTIES, reason)
        return command_results(loaded, clone)


def check_recorded(
    loaded: LoadedCase, *, repo: Path | None = None, commands: bool = False
) -> list[ResultReport]:
    """Each recorded result of the fixture, evaluated. The four diff properties come from the
    diff alone. With `commands` and `repo`, the two command properties run in a scratch clone of
    `repo` with the diff applied. `matches` says that the failed properties are those that the
    record expects: all six with commands, else the four of the diff. A command property that was
    skipped (the diff does not apply) is no failure, so it differs from a record that expects it
    to fail."""
    case = loaded.case
    reports: list[ResultReport] = []
    for recorded in case.results:
        diff = loaded.diffs[recorded.name]
        properties = diff_results(loaded, diff)
        if commands and repo is not None:
            properties += _applied_commands(loaded, repo, diff)
        compared = ALL_PROPERTIES if commands and repo is not None else DIFF_PROPERTIES
        failed = tuple(r.prop for r in properties if r.prop in compared and r.status is Status.FAIL)
        expected = tuple(p for p in compared if p in recorded.fails)
        reports.append(
            ResultReport(
                fixture=case.name,
                result=recorded.name,
                issue=case.issue,
                group=case.group,
                status=RECORDED,
                properties=_records(properties),
                expected=tuple(p.value for p in expected),
                matches=failed == expected,
            )
        )
    return reports


# ── The report ────────────────────────────────────────────────────────────────────────────


def _property_lines(result: ResultReport) -> list[str]:
    texts = MESSAGES.roadmap
    lines: list[str] = []
    for record in result.properties:
        detail = texts.eval_implement_detail.format(detail=record.detail) if record.detail else ""
        lines.append(
            texts.eval_implement_property.format(
                status=record.status, prop=record.name, detail=detail
            )
        )
    return lines


def _expected_line(result: ResultReport) -> list[str]:
    """The line that says whether a recorded result fails what the record says, or none."""
    texts = MESSAGES.roadmap
    if result.expected is None:
        return []
    shown = ", ".join(result.expected) or texts.eval_implement_nothing
    if result.matches:
        return [texts.eval_implement_as_recorded.format(fails=shown)]
    actual = ", ".join(p.name for p in result.properties if p.status == Status.FAIL.value)
    return [
        texts.eval_implement_not_recorded.format(
            expected=shown, actual=actual or texts.eval_implement_nothing
        )
    ]


def _result_lines(result: ResultReport) -> list[str]:
    texts = MESSAGES.roadmap
    lines = [
        texts.eval_implement_head.format(
            name=result.fixture,
            result=result.result,
            status=result.status,
            issue=result.issue,
            group=result.group,
        )
    ]
    if result.reason:
        lines.append(texts.eval_implement_reason.format(reason=result.reason))
    if result.requests:
        lines.append(
            texts.eval_implement_cost.format(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                requests=result.requests,
                tool_calls=result.tool_calls,
                seconds=result.seconds,
            )
        )
    lines += _property_lines(result)
    if result.first_failed:
        lines.append(texts.eval_implement_first_failed.format(prop=result.first_failed))
    return [*lines, *_expected_line(result)]


def render_report(report: RunReport) -> str:
    """The report as text: a block for each result, then the totals."""
    texts = MESSAGES.roadmap
    count = len(report.results)
    title = (
        texts.eval_implement_title.format(count=count, model=report.model)
        if report.model
        else texts.eval_implement_title_check.format(count=count)
    )
    lines = [title, ""]
    for result in report.results:
        lines += [*_result_lines(result), ""]
    lines.append(
        texts.eval_implement_totals.format(
            passed=report.count(Status.OK),
            failed=report.count(Status.FAIL),
            skipped=report.count(Status.SKIPPED),
        )
    )
    if report.differing:
        lines.append(texts.eval_implement_differ.format(count=report.differing))
    return "\n".join(lines) + "\n"


def write_report(report: RunReport, directory: Path, moment: datetime) -> Path:
    """Write the report as JSON in `directory`, in a new file whose name starts with `moment` and
    ends with a unique part, so that two runs of the same second keep two files. Returns the path."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = moment.strftime("%Y%m%d-%H%M%S")
    handle, name = tempfile.mkstemp(prefix=f"implement-{stamp}-", suffix=".json", dir=directory)
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(report.model_dump_json(indent=2) + "\n")
    return Path(name)


def render_dry_run(cases: Sequence[LoadedCase], *, model: str) -> str:
    """What a run does, making no request: the steps, and the model requests of each."""
    from devops_cli.dry_run.requests import PlannedRequest

    texts = MESSAGES.roadmap
    steps = [
        texts.eval_implement_dry_step.format(
            name=c.name, issue=c.case.issue, group=c.case.group, sha=c.case.base[:12]
        )
        for c in cases
    ]
    requests = [
        PlannedRequest(
            method=texts.implement_model_request,
            target=texts.eval_implement_model_target.format(
                model=model, group=c.case.group, issue=c.case.issue, name=c.name
            ),
            repeat=texts.implement_model_repeat.format(limit=CONST_ROADMAP_IMPLEMENT_MAX_REQUESTS),
        ).line()
        for c in cases
    ]
    lines = [texts.eval_implement_dry_title, *steps, "", texts.eval_implement_dry_requests]
    return "\n".join([*lines, *(f"{n}. {line}" for n, line in enumerate(requests, 1))]) + "\n"
