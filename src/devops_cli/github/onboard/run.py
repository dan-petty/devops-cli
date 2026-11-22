"""The order of the rows of one onboarding run, the output, and the dry run.

`onboard_repository` runs the rows in the order that their reads and writes need, and gives them
in number order. A read that fails makes its row `not readable`, and a write that fails makes it
`failed`; the other rows still run, and the next run goes on from the live state. With `--confirm`,
a failed preflight stops the run before its first write.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.onboard.baseline import (
    Baseline,
    BaselineUnreadableError,
    check_answer_flags,
    read_answers,
    render_answers,
    render_baseline,
    resolve_ref,
)
from devops_cli.github.onboard.model import (
    OnboardOptions,
    OnboardReport,
    PersonStep,
    Row,
    RowContext,
    RowState,
)
from devops_cli.github.onboard.routes import READS, ROUTES, RouteWriteError, RouteWriter
from devops_cli.github.onboard.service_rows import (
    app_row,
    cluster_row,
    labels_row,
    rag_row,
    service_row,
    webhook_row,
)
from devops_cli.github.onboard.settings_rows import (
    code_quality_row,
    create_row,
    environment_row,
    preflight_row,
    probe_rulesets,
    read_repository,
    release_secret_row,
    repository_row,
    ruleset_row,
    security_row,
    token_scopes,
)
from devops_cli.github.onboard.template_pr import ready_row, template_row

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.github.session import GitHubSession

# The number and name of each row, in the order of the output (design of #6773).
ROW_NAMES: Final[dict[int, str]] = {
    0: "Preflight",
    1: "Create",
    2: "Repository",
    3: "Security",
    4: "Code Quality",
    5: "Environment",
    6: "Release secret",
    7: "App check",
    8: "Labels",
    9: "Template pull request",
    10: "Ruleset",
    11: "Ready",
    12: "Webhook",
    13: "Service",
    14: "Cluster",
    15: "RAG",
}
# The states of a template pull request whose checks have not passed: the ruleset waits, so it
# requires only the checks that reported (D3).
_OPEN_CHECKS: Final[frozenset[RowState]] = frozenset({RowState.WAITING, RowState.FAILED})


def _guarded(number: int, step: Callable[[], Row]) -> Row:
    """The row that `step` gives, or `failed` for a write that failed and `not readable` for a
    read that failed."""
    try:
        return step()
    except RouteWriteError as exc:
        return Row(number, ROW_NAMES[number], RowState.FAILED, reason=exc.message)
    except DevOpsCLIError as exc:
        return Row(number, ROW_NAMES[number], RowState.NOT_READABLE, reason=exc.message)


class _Run:
    """One run of the rows over one repository."""

    def __init__(self, session: GitHubSession, options: OnboardOptions, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.writer = RouteWriter(session, confirm=options.confirm)
        self.ctx = RowContext(options=options)
        self.rows: dict[int, Row] = {}
        self.baseline: Baseline | None = None
        self.baseline_error: str | None = None
        self.baseline_steps: tuple[PersonStep, ...] = ()
        self.kept: tuple[str, ...] = ()

    def wanted(self, number: int) -> bool:
        only = self.ctx.options.only
        return only is None or number in only

    def put(self, number: int, step: Callable[[], Row]) -> Row | None:
        """Run row `number` unless `--only` leaves it out, or an earlier row stopped the run."""
        if not self.wanted(number):
            return None
        if self.ctx.stopped is not None:
            row = Row(number, ROW_NAMES[number], RowState.SKIPPED, reason=self.ctx.stopped)
        else:
            row = _guarded(number, step)
        self.rows[number] = row
        return row

    def with_baseline(self, number: int, step: Callable[[Baseline], Row]) -> Row | None:
        """Run row `number` with the baseline, or make it `not readable` with the reason."""
        baseline = self.baseline
        if baseline is None:
            reason = self.baseline_error or "the baseline was not read"
            return self.put(
                number,
                lambda: Row(
                    number,
                    ROW_NAMES[number],
                    RowState.NOT_READABLE,
                    reason=reason,
                    steps=self.baseline_steps,
                ),
            )
        return self.put(number, lambda: step(baseline))

    def read_baseline(self, template: str) -> None:
        """Read the answers file, check the flags, resolve the ref and render the template."""
        options, ctx = self.ctx.options, self.ctx
        answers = (
            read_answers(self.session, ctx.repo, ctx.default_branch)
            if ctx.repo_payload is not None
            else None
        )
        check_answer_flags(answers, options)
        try:
            ref = resolve_ref(self.session, template, options, answers)
            given = render_answers(answers, options, plan_limited=ctx.plan_limited)
            self.baseline = render_baseline(self.session, template, options.repo.name, ref, given)
        except BaselineUnreadableError as exc:
            self.baseline_error = exc.message
            self.baseline_steps = (exc.step,) if exc.step else ()


def _skip_rest(run: _Run, reason: str) -> None:
    """Mark each row after row 1 skipped, for a repository that does not exist."""
    for number in ROW_NAMES:
        if number > 1 and run.wanted(number):
            run.rows[number] = Row(number, ROW_NAMES[number], RowState.SKIPPED, reason=reason)


def _settings_rows(run: _Run) -> None:
    """Rows 2 to 8: the settings, the release flow, the Apps and the labels."""
    session, writer, ctx, settings = run.session, run.writer, run.ctx, run.settings
    run.with_baseline(2, lambda baseline: repository_row(writer, ctx, baseline))
    run.with_baseline(3, lambda baseline: security_row(session, writer, ctx, baseline))
    run.put(4, lambda: code_quality_row(session, writer, ctx))
    run.with_baseline(5, lambda baseline: environment_row(session, writer, ctx, baseline, settings))
    run.with_baseline(
        6, lambda baseline: release_secret_row(session, writer, ctx, baseline, settings)
    )
    run.put(7, lambda: app_row(ctx, settings))

    def labels() -> Row:
        row, differing = labels_row(session, writer, ctx, run.baseline)
        run.kept = (*run.kept, *(f"label {name}" for name in differing))
        return row

    run.put(8, labels)


def _pull_rows(run: _Run, template: str) -> None:
    """Rows 9 to 11: the template pull request, the ruleset and the merge."""
    session, writer, ctx = run.session, run.writer, run.ctx

    def template_pull(baseline: Baseline) -> Row:
        row, kept = template_row(session, writer, ctx, baseline, template)
        run.kept = (*run.kept, *(f"file {path}" for path in kept))
        return row

    pull = run.with_baseline(9, template_pull)
    if pull is not None and pull.state in _OPEN_CHECKS and not ctx.checks_passed:
        reason = "the ruleset waits for the checks of the template pull request"
        run.put(10, lambda: Row(10, ROW_NAMES[10], RowState.SKIPPED, reason=reason))
    else:
        run.with_baseline(10, lambda baseline: ruleset_row(session, writer, ctx, baseline))
    state = pull.state if pull is not None else RowState.SKIPPED
    run.with_baseline(11, lambda _baseline: ready_row(session, writer, ctx, state))


def _preflight(run: _Run, step: Callable[[], Row]) -> None:
    """Run row 0. With `--confirm`, a failed row 0 stops the run before its next write."""
    preflight = run.put(0, step)
    if run.ctx.options.confirm and preflight is not None and preflight.state is RowState.FAILED:
        run.ctx.stopped = "the preflight failed"


def onboard_repository(
    options: OnboardOptions,
    *,
    session: GitHubSession,
    settings: Settings,
) -> OnboardReport:
    """Run rows 0 to 15 over one repository and give the report.

    Raises `AnswerFlagError` when a flag differs from `.copier-answers.yml`, before any write.
    """
    run = _Run(session, options, settings)
    ctx, writer = run.ctx, run.writer
    template = settings.github.template_repository
    scopes = token_scopes(session)
    read_repository(session, ctx)
    if ctx.repo_payload is None:
        # Without a repository, row 0 checks the scopes only, before row 1 can create it.
        _preflight(run, lambda: preflight_row(session, ctx, None, scopes=scopes, probe=None))
    create = run.put(1, lambda: create_row(session, writer, ctx))
    if ctx.repo_payload is None:
        reason = ctx.stopped or "the repository does not exist yet"
        if create is not None and create.state is RowState.PENDING:
            reason = "--confirm creates the repository first"
        _skip_rest(run, reason)
        return _report(run)
    probe = probe_rulesets(session, ctx)
    run.read_baseline(template)
    _preflight(run, lambda: preflight_row(session, ctx, run.baseline, scopes=scopes, probe=probe))
    _settings_rows(run)
    _pull_rows(run, template)
    run.put(12, lambda: webhook_row(session, writer, ctx, settings))
    run.put(13, lambda: service_row(writer, ctx, settings))
    run.put(14, lambda: cluster_row(ctx))
    run.put(15, lambda: rag_row(writer, ctx, settings))
    return _report(run)


def _report(run: _Run) -> OnboardReport:
    return OnboardReport(
        repo=run.ctx.repo,
        template_ref=run.baseline.ref if run.baseline else None,
        rows=tuple(run.rows[number] for number in sorted(run.rows)),
        kept=run.kept,
        confirm=run.ctx.options.confirm,
    )


def _row_lines(row: Row) -> list[str]:
    """The lines of one row: its number, name and state, its reason, and each change."""
    head = f"{row.number}. {row.name}: {row.state.value}"
    lines = [head if row.reason is None else f"{head} ({row.reason})"]
    lines.extend(f"   - {change}" for change in row.changes)
    return lines


def render_report(report: OnboardReport) -> str:
    """The report as text: the rows, the kept files and labels, then the person steps."""
    ref = report.template_ref or "no template ref"
    lines = [f"# Onboarding of {report.repo} at {ref}"]
    for row in report.rows:
        lines.extend(_row_lines(row))
    if report.kept:
        lines.extend(["", "Kept as the repository holds them:"])
        lines.extend(f"  - {item}" for item in report.kept)
    lines.append("")
    steps = report.person_steps
    if not steps:
        lines.append("Person steps: none.")
    else:
        lines.append("Person steps:")
        lines.extend(
            f"{index}. {step.text} ({step.document})" for index, step in enumerate(steps, start=1)
        )
    return "\n".join(lines)


def planned_requests(
    options: OnboardOptions, template: str
) -> tuple[list[PlannedRequest], list[PlannedRequest]]:
    """The reads and the writes of a run, from `READS` and `ROUTES`, for a dry run. Nothing is
    sent and no program starts."""
    repo = options.repo.display

    def fill(text: str) -> str:
        return text.replace("{repo}", repo).replace("{template}", template)

    def selected(row: int) -> bool:
        return options.only is None or row in options.only

    reads = [
        PlannedRequest(method=f"row {row}", target=fill(text))
        for row, text in READS
        if selected(row)
    ]
    writes = [
        PlannedRequest(
            method=f"row {route.row} {route.method}",
            target=f"{fill(route.path)} ({route.what}; owner: {route.owner.value})",
        )
        for route in ROUTES
        if selected(route.row)
    ]
    return reads, writes


__all__ = [
    "ROW_NAMES",
    "onboard_repository",
    "planned_requests",
    "render_report",
]
