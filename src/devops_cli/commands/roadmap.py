"""`devops roadmap`: the roadmap on GitHub. Intake is the one way new work becomes an item,
refine readies items, stage makes a Ready item Staged, implement takes a Staged or Planned item
to a ready pull request, return sends an item back to New, claim and release say who works
on an item, and explain says why the stage job and the implement job take an item or leave it out.

Every command opens the roadmap store of the repository: labels and milestones hold the Items
and their fields, and no command reads or writes a project board (ADR 0016). Intake reads
`.github/labels.yml` at `--ref`. `intake`, `refine`, `stage`, `implement`, `return`, `claim` and
`release` write GitHub state only with `--confirm`; `stage` and `implement` also write git, only to
the staged branch of an item and never to the default branch. `implement --confirm` runs steps only
in a runner pod. Outside one, `implement --item <n> --confirm` starts the runner Job for the item
(#2913). `explain` reads GitHub and git, calls no model and writes nothing. A person plans the
milestones; no command sets one.

Every job's `--dry-run` makes no request at all (#412, #1125): it returns the job's result type
marked as a dry run and prints the requests a run makes, each with its exact `gh` command.
Intake's `--plan`, and intake with no mode flag, read GitHub and call the model, and write
nothing.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
    DEFAULT_ROADMAP_REFINE_LIMIT,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError, RoadmapRunError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, write_stdout
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.claim import (
    Claimant,
    apply_claim,
    dry_run_claim,
    plan_claim,
    render_claim_plan,
)
from devops_cli.roadmap.intake import (
    Filer,
    NewCandidate,
    Outcome,
    apply_intake,
    dry_run_intake,
    plan_intake,
    raise_for_failed_placements,
    render_intake,
    render_intake_dry_run,
)
from devops_cli.roadmap.intake_model import build_intake_model
from devops_cli.roadmap.intake_requests import SpendMeter
from devops_cli.roadmap.request_plan import render_dry_run
from devops_cli.roadmap.store import RoadmapStore

app = new_typer(help=HELP.roadmap.app, no_args_is_help=True)

RepoOption = Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)]
RefOption = Annotated[str | None, typer.Option("--ref", help=HELP.roadmap.ref)]


@contextmanager
def _exit_on_failure(action: str) -> Iterator[None]:
    """Report a failed read or write as `action` failing, and exit 1."""
    try:
        yield
    except DevOpsCLIError as exc:
        print_error(f"{action}: {exc}", safe=True)
        raise typer.Exit(1) from exc


def _target(repo: str | None) -> str:
    """The repository: `--repo`, or the checkout's origin, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


def _open_store(repo: str | None) -> tuple[str, RoadmapStore]:
    """The repository and its roadmap store."""
    target = _target(repo)
    return target, roadmap_store.get_roadmap_store(target)


def _one_mode(**modes: bool) -> None:
    """Refuse more than one mode flag."""
    if sum(modes.values()) > 1:
        flags = [f"--{name.replace('_', '-')}" for name in modes]
        listed = f"{', '.join(flags[:-1])} and {flags[-1]}"
        _refuse(MESSAGES.roadmap.plan_modes_exclusive.format(modes=listed))


def _refuse(message: str) -> NoReturn:
    print_error(message)
    raise typer.Exit(1)


def _new_candidate(title: str | None, body_file: Path | None) -> tuple[str, str] | None:
    """The title and body `--title` and `--body-file` give together, or None when neither is."""
    if title is None and body_file is None:
        return None
    if title is None or body_file is None:
        _refuse(MESSAGES.roadmap.intake_title_needs_body)
    return title, body_file.read_text(encoding="utf-8")


def _intake_dry_run(
    repo: str | None,
    ref: str | None,
    issues: Collection[int],
    new: NewCandidate | None,
    limit: int | None,
) -> None:
    """Print the requests an intake run makes, making none: no store opens, no model is built."""
    target = _target(repo)
    with _exit_on_failure("Could not plan intake"):
        planned = dry_run_intake(target, ref=ref, issues=issues, new=new, limit=limit)
    render_intake_dry_run(planned, repo=target)


@app.command("intake", help=HELP.roadmap.intake)
@dry_run_class("request-plan")
def intake_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    issue: Annotated[
        list[int] | None, typer.Option("--issue", min=1, help=HELP.roadmap.intake_issue)
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help=HELP.roadmap.intake_title)] = None,
    body_file: Annotated[
        Path | None,
        typer.Option(
            "--body-file", exists=True, dir_okay=False, help=HELP.roadmap.intake_body_file
        ),
    ] = None,
    source: Annotated[str | None, typer.Option("--source", help=HELP.roadmap.intake_source)] = None,
    filed_by: Annotated[
        Filer, typer.Option("--filed-by", help=HELP.roadmap.intake_filed_by)
    ] = Filer.AGENT,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.intake_limit)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.intake_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.intake_plan)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.intake_confirm)] = False,
) -> None:
    """Turn candidates into items: possible duplicates, type, priority, Value, Effort and
    placement."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    given = _new_candidate(title, body_file)
    if given is not None and issue:
        _refuse(MESSAGES.roadmap.intake_issue_or_title)
    new = (
        NewCandidate(title=given[0], body=given[1], source=source, filed_by=filed_by)
        if given is not None
        else None
    )
    if dry_run or is_dry_run():
        _intake_dry_run(repo, ref, issue or (), new, limit)
        return
    if not (plan_only or confirm):
        print_info(MESSAGES.roadmap.intake_plain_note)
    _intake(repo, ref, issue or (), new, limit, confirm=confirm)


def _intake(
    repo: str | None,
    ref: str | None,
    issues: Sequence[int],
    new: NewCandidate | None,
    limit: int | None,
    *,
    confirm: bool,
) -> None:
    with _exit_on_failure("Could not plan intake"):
        # Counts from here the requests the identity's ledger paces, gh's and the session's.
        meter = SpendMeter()
        target, store = _open_store(repo)
        plan = plan_intake(
            store,
            repo=target,
            model=meter.model(build_intake_model()),
            ref=ref,
            issues=issues,
            new=new,
            limit=limit,
        )
    if not confirm:
        plan = replace(plan, spend=meter.spend())
    write_stdout(render_intake(plan, repo=target))
    if not plan.has_writes:
        if new is not None and confirm and any(d.outcome is Outcome.SKIP for d in plan.decisions):
            raise typer.Exit(1)
        return
    if not confirm:
        print_info(MESSAGES.roadmap.intake_preview)
        return
    with _exit_on_failure("Intake stopped part-way; run it again to finish"):
        applied = apply_intake(store, plan)
    print_success(MESSAGES.roadmap.intake_applied.format(placed=applied.placed))
    for number in applied.filed:
        print_info(MESSAGES.roadmap.intake_filed.format(number=number))
    with _exit_on_failure("Intake finished with candidates it could not write"):
        raise_for_failed_placements(applied)


@app.command("intake-eval", help=HELP.roadmap.intake_eval)
def intake_eval_cmd(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.intake_eval_dry_run)
    ] = False,
) -> None:
    """Score intake's duplicate judgement against the evaluation set."""
    from devops_cli.config.settings import get_ai_api_key, load_settings
    from devops_cli.roadmap import duplicate_eval
    from devops_cli.roadmap.intake_model import GatewayIntakeModel, gateway_address

    cases = duplicate_eval.load_cases()
    settings = load_settings()
    gateway = gateway_address(settings.ai)
    if dry_run or is_dry_run():
        write_stdout(duplicate_eval.render_duplicate_dry_run(cases, gateway=gateway))
        return
    labels = duplicate_eval.checkout_labels()
    meter = SpendMeter()
    intake_model = GatewayIntakeModel(
        settings.ai, api_key=get_ai_api_key(settings), embedder=duplicate_eval.SameVector()
    )
    score = duplicate_eval.evaluate_duplicates(cases, meter.model(intake_model), labels)
    model = settings.ai.for_task("analysis").model
    spend = meter.spend()
    spent = MESSAGES.roadmap.intake_eval_spent.format(
        calls=spend.model_calls, github=spend.rest + spend.search + spend.graphql
    )
    report = duplicate_eval.render_duplicate_score(score, model=model, gateway=gateway, spend=spent)
    write_stdout(report)
    if score.failed:
        print_error(MESSAGES.roadmap.intake_eval_failed.format(failed=score.failed))
        raise typer.Exit(1)


@app.command("refine", help=HELP.roadmap.refine)
@dry_run_class("request-plan")
def refine_cmd(
    repo: RepoOption = None,
    source: Annotated[Path, typer.Option("--source", help=HELP.roadmap.refine_source)] = Path("."),
    item: Annotated[int | None, typer.Option("--item", help=HELP.roadmap.refine_item)] = None,
    limit: Annotated[
        int, typer.Option("--limit", help=HELP.roadmap.refine_limit)
    ] = DEFAULT_ROADMAP_REFINE_LIMIT,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.refine_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.refine_confirm)] = False,
) -> None:
    """Refine roadmap items to Ready with proposed design, tasks and acceptance criteria."""
    _one_mode(dry_run=dry_run, confirm=confirm)
    target_repo = repo or get_repo_origin_name(source)
    if not target_repo or "/" not in target_repo:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)

    if dry_run or is_dry_run():
        from devops_cli.roadmap.refine import dry_run_refine
        from devops_cli.roadmap.request_plan import render_dry_run

        plan = dry_run_refine(target_repo, item=item, limit=limit)
        render_dry_run("refine", target_repo, plan.requests, plan.write_requests)
        return

    from devops_cli.roadmap.refine import (
        apply_refine,
        plan_refine,
        raise_for_failed_items,
        render_refine_plan,
    )

    with _exit_on_failure("Could not plan refinement"):
        _, store = _open_store(target_repo)
        plan = plan_refine(store, repo=target_repo, source=source, item_number=item, limit=limit)
    write_stdout(render_refine_plan(plan) + "\n")
    if not confirm:
        print_info(MESSAGES.roadmap.preview_only)
    elif plan.has_writes:
        with _exit_on_failure("Could not apply refinement"):
            applied = apply_refine(store, plan)
            print_success(
                f"Refined {applied.refined_count} item(s): {applied.readied_count} set to "
                f"Ready, {applied.split_count} marked for split."
            )
    with _exit_on_failure("Refinement incomplete"):
        raise_for_failed_items(plan)


@app.command("alternatives", help=HELP.roadmap.alternatives)
def alternatives_cmd(
    repo: RepoOption = None,
    item: Annotated[
        int | None, typer.Option("--item", min=1, help=HELP.roadmap.alternatives_item)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.alternatives_limit)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.alternatives_dry_run)
    ] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.alternatives_plan)] = False,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.alternatives_confirm)
    ] = False,
) -> None:
    """Check open items for an open, maintained tool that already covers their need."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    target = _target(repo)
    from devops_cli.roadmap import alternatives as job

    if dry_run or is_dry_run():
        planned = job.dry_run_alternatives(target, item=item, limit=limit)
        render_dry_run("alternatives", target, planned.requests, planned.write_requests)
        return
    with _exit_on_failure("Could not check for alternatives"):
        _, store = _open_store(target)
        plan = job.plan_alternatives(store, repo=target, item_number=item, limit=limit)
    write_stdout(job.render_alternatives_plan(plan) + "\n")
    if not confirm:
        if plan.has_writes:
            print_info(MESSAGES.roadmap.preview_only)
    elif plan.has_writes:
        with _exit_on_failure("Could not write the checks"):
            written = job.apply_alternatives(store, plan)
        print_success(MESSAGES.roadmap.alternatives_applied.format(count=written))
    with _exit_on_failure("The check is incomplete"):
        job.raise_for_failed_checks(plan)


@app.command("stage", help=HELP.roadmap.stage)
def stage_cmd(
    repo: RepoOption = None,
    source: Annotated[Path | None, typer.Option("--source", help=HELP.roadmap.stage_source)] = None,
    item: Annotated[int | None, typer.Option("--item", min=1, help=HELP.roadmap.stage_item)] = None,
    filters: Annotated[
        list[str] | None, typer.Option("--filter", help=HELP.roadmap.stage_filter)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.stage_limit)
    ] = None,
    step_tokens: Annotated[
        int | None, typer.Option("--step-tokens", min=1000, help=HELP.roadmap.stage_step_tokens)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.stage_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.stage_plan)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.stage_confirm)] = False,
    why: Annotated[bool, typer.Option("--why", help=HELP.roadmap.stage_why)] = False,
) -> None:
    """Make Ready items Staged: a branch, an OpenSpec change in budgeted task groups, and a draft."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    from devops_cli.roadmap.stage import (
        apply_stage,
        dry_run_stage,
        emit_stage_results,
        parse_filters,
        plan_stage,
        raise_for_failed,
        render_stage_plan,
    )

    with _exit_on_failure("Could not read the options"):
        parsed = parse_filters(filters or ())
    target = _target(repo)
    if dry_run or is_dry_run():
        planned = dry_run_stage(target, item=item, limit=limit)
        render_dry_run("stage", target, planned.requests, planned.write_requests)
        return
    if not (plan_only or confirm):
        print_info(MESSAGES.roadmap.stage_plain_note)
    from devops_cli.roadmap.run import model_clone

    with _exit_on_failure("Could not plan staging"):
        _, store = _open_store(target)
        clone = source or model_clone(target)
        plan = plan_stage(
            store,
            repo=target,
            source=clone,
            filters=parsed,
            item_number=item,
            limit=limit,
            step_tokens=step_tokens,
            why=why,
        )
    write_stdout(render_stage_plan(plan) + "\n")
    failures = list(plan.failed)
    if confirm:
        with _exit_on_failure("Could not stage"):
            applied = apply_stage(store, plan, source=clone)
        emit_stage_results(plan, applied)
        print_success(
            MESSAGES.roadmap.stage_applied.format(
                staged=len(applied.staged),
                stopped=len(applied.stopped),
                removed=len(applied.removed),
            )
        )
        failures += applied.failed
    else:
        print_info(MESSAGES.roadmap.preview_only)
    with _exit_on_failure("Staging incomplete"):
        raise_for_failed(failures)


def _render_roadmap_run_dry_run(target: str) -> None:
    from devops_cli.roadmap.request_plan import planned_session_read, render_dry_run

    reads = [
        planned_session_read(
            f"/repos/{target}/issues/events",
            "the issue events to judge what jobs are due",
            repeat=MESSAGES.roadmap.plan_repeat_page,
        )
    ]
    render_dry_run("run", target, reads, ())


def _try_open_store(repo: RepoOption) -> RoadmapStore | None:
    try:
        _, store = _open_store(repo)
        return store
    except AssertionError:
        return None


def _show_due_jobs(target: str, store: RoadmapStore) -> None:
    from devops_cli.roadmap.run import run_due_jobs

    due = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=True)
    if due:
        write_stdout(f"Due: {', '.join(due)}\n")
    else:
        write_stdout("Due: (none)\n")


@app.command("run", help=HELP.roadmap.run)
@dry_run_class("request-plan")
def run_cmd(
    repo: RepoOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.run_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.run_confirm)] = False,
) -> None:
    """Run the roadmap jobs that are due, in order: metrics, intake, refinement and the alternatives check."""
    if dry_run or is_dry_run():
        target = _target(repo)
        store = _try_open_store(repo)
        from devops_cli.roadmap.github_store import GitHubRoadmapStore

        if store is not None and not isinstance(store, GitHubRoadmapStore):
            _show_due_jobs(target, store)
        _render_roadmap_run_dry_run(target)
        return

    target, store = _open_store(repo)
    from devops_cli.roadmap.run import run_due_jobs

    if not confirm:
        due = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=True)
        if due:
            write_stdout(f"Due: {', '.join(due)}\n")
        else:
            write_stdout("Due: (none)\n")
        return

    try:
        ran = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=False)
        if ran:
            print_success(f"Roadmap jobs completed: {', '.join(ran)}")
    except RoadmapRunError as exc:
        print_error(str(exc), safe=True)
        raise typer.Exit(1) from exc


def _implement_step(
    repo: str | None,
    source: Path | None,
    item: int | None,
    group: int,
    fmt: str,
    *,
    dry_run: bool,
) -> None:
    """Run one task group of an item's change in a checkout, and commit it or reset it."""
    checkout = source or Path(".")
    target = repo or get_repo_origin_name(checkout)
    if not target or "/" not in target:
        _refuse("Cannot resolve the repository; pass --repo owner/name.")
    if item is None:
        _refuse(MESSAGES.roadmap.implement_step_needs_item)

    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap import implement_step

    task = load_settings().ai.for_task("implement")
    if dry_run or is_dry_run():
        outcome = implement_step.dry_run_step(target, item=item, group=group, model=task.model)
        implement_step.render_outcome(outcome, target, fmt)
        return

    from devops_cli.ai.client.factory import get_task_model

    with _exit_on_failure("Could not run the step"):
        _, store = _open_store(target)
        outcome = implement_step.run_step(
            store,
            item=item,
            group=group,
            source=checkout,
            model=get_task_model("implement"),
            window=task.context_window,
        )
    implement_step.render_outcome(outcome, target, fmt)
    if outcome.status is implement_step.StepStatus.STOPPED:
        raise typer.Exit(1)


def _start_implement_job(
    target: str,
    item: int,
    *,
    source: Path | None,
    filters: list[str] | None,
    limit: int,
    context: str | None,
    wait: bool,
    preview: bool,
) -> None:
    """Outside a runner, start the runner Job for one item with the code of `devops k8s run-job`
    (#2913), or print the Job with `preview`. The repository is checked first, then the item, and a
    refused item starts no Job. The options that need the runner are refused with `--confirm`; a
    preview ignores them, as it did before. The pod makes the full plan."""
    from devops_cli.commands.k8s.cluster_jobs import (
        DEFAULT_JOB_START_TIMEOUT_SECONDS,
        check_repo,
        start_job,
    )
    from devops_cli.k8s.cluster_job import TemplateName
    from devops_cli.roadmap import implement_outside as outside

    check_repo(target)
    options = outside.runner_only_options(source=source, filters=filters, limit=limit)
    if options and not preview:
        _refuse(outside.refusal(target, options=options))
    before: list[PlannedRequest] = []
    if preview:
        before = outside.read_requests(target, item)
    else:
        with _exit_on_failure("Could not start the job"):
            _, store = _open_store(target)
            outside.require_startable(store, item)
    start_job(
        outside.job_args(target, item),
        context=context,
        template=TemplateName.RUNNER,
        repo=target,
        wait=wait,
        start_timeout=DEFAULT_JOB_START_TIMEOUT_SECONDS,
        dry_run=preview,
        before=before,
    )


def _implement_job(
    repo: str | None,
    source: Path | None,
    item: int | None,
    filters: list[str] | None,
    limit: int,
    *,
    dry_run: bool,
    plan_only: bool,
    confirm: bool,
    why: bool,
    context: str | None = None,
    wait: bool = True,
) -> None:
    """Take the Staged and Planned items that the filter names to a ready pull request. Outside a
    runner, `--confirm` and `--dry-run` with `--item` start the runner Job instead (#2913)."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.implement import (
        dry_run_implement,
        parse_implement_filters,
        plan_implement,
        render_implement_plan,
    )
    from devops_cli.roadmap.implement_run import apply_implement, raise_for_failed, require_runner

    with _exit_on_failure("Could not read the options"):
        parsed = parse_implement_filters(filters or ())
    target = _target(repo)
    preview = dry_run or is_dry_run()
    outside = not load_settings().roadmap.implement.in_runner
    if outside and item is not None and (confirm or preview):
        _start_implement_job(
            target,
            item,
            source=source,
            filters=filters,
            limit=limit,
            context=context,
            wait=wait,
            preview=preview,
        )
        return
    if preview:
        planned = dry_run_implement(target, item=item, limit=limit)
        render_dry_run("implement", target, planned.requests, planned.write_requests)
        return
    if confirm and outside:
        from devops_cli.roadmap.implement_outside import refusal, runner_only_options

        options = runner_only_options(source=source, filters=filters, limit=limit)
        _refuse(refusal(target, options=options))
    if confirm:
        with _exit_on_failure("Could not run the job"):
            require_runner(target)
    elif not plan_only:
        print_info(MESSAGES.roadmap.implement_job_plain_note)
    from devops_cli.roadmap.run import model_clone

    with _exit_on_failure("Could not plan the job"):
        _, store = _open_store(target)
        clone = source or model_clone(target)
        plan = plan_implement(
            store,
            repo=target,
            source=clone,
            filters=parsed,
            item_number=item,
            limit=limit,
            why=why,
        )
    write_stdout(render_implement_plan(plan) + "\n")
    if not confirm:
        print_info(MESSAGES.roadmap.preview_only)
        return

    from devops_cli.ai.client.factory import get_task_model

    with _exit_on_failure("Could not run the job"):
        applied = apply_implement(
            store,
            plan,
            source=clone,
            model=get_task_model("implement"),
            window=load_settings().ai.for_task("implement").context_window,
        )
    print_success(
        MESSAGES.roadmap.implement_job_applied.format(
            ready=len(applied.ready), stopped=len(applied.stopped)
        )
    )
    if applied.yielded:
        print_info(
            MESSAGES.roadmap.implement_job_yielded.format(yielded=len(applied.yielded)),
            prefix=False,
        )
    with _exit_on_failure("The job is incomplete"):
        raise_for_failed(applied.failed)


@app.command("implement", help=HELP.roadmap.implement)
def implement_cmd(
    repo: RepoOption = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.implement_source)
    ] = None,
    item: Annotated[
        int | None, typer.Option("--item", min=1, help=HELP.roadmap.implement_item)
    ] = None,
    group: Annotated[int | None, typer.Option("--group", help=HELP.roadmap.implement_group)] = None,
    filters: Annotated[
        list[str] | None, typer.Option("--filter", help=HELP.roadmap.implement_filter)
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", min=1, help=HELP.roadmap.implement_limit)
    ] = DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.implement_dry_run)
    ] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.implement_plan)] = False,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.implement_confirm)
    ] = False,
    why: Annotated[bool, typer.Option("--why", help=HELP.roadmap.implement_why)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    wait: Annotated[
        bool, typer.Option("--wait/--no-wait", help=HELP.roadmap.implement_wait)
    ] = True,
) -> None:
    """Run one task group of a Staged item's change (--group), or the job that implements items."""
    if group is None:
        _implement_job(
            repo,
            source,
            item,
            filters,
            limit,
            dry_run=dry_run,
            plan_only=plan_only,
            confirm=confirm,
            why=why,
            context=context,
            wait=wait,
        )
        return
    if filters or plan_only or confirm or why:
        _refuse(MESSAGES.roadmap.implement_step_job_options)
    from devops_cli.output.serialization import resolve_format

    fmt = resolve_format(output_format, json_output=json_output)
    _implement_step(repo, source, item, group, fmt, dry_run=dry_run)


@app.command("explain", help=HELP.roadmap.explain)
@dry_run_class("request-plan")
def explain_cmd(
    item: Annotated[int, typer.Argument(min=1, help=HELP.roadmap.explain_arg)],
    repo: RepoOption = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.explain_source)
    ] = None,
    filters: Annotated[
        list[str] | None, typer.Option("--filter", help=HELP.roadmap.explain_filter)
    ] = None,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.explain_limit)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.explain_dry_run)] = False,
) -> None:
    """Say whether the stage job and the implement job take an issue, and why not."""
    from devops_cli.roadmap.explain import explain_item, render_explanation
    from devops_cli.roadmap.implement import parse_implement_filters
    from devops_cli.roadmap.request_plan import explain_requests
    from devops_cli.roadmap.run import model_clone
    from devops_cli.roadmap.stage import parse_filters

    target = _target(repo)
    if dry_run or is_dry_run():
        reads, writes = explain_requests(target, item=item)
        render_dry_run("explain", target, reads, writes)
        return
    with _exit_on_failure("Could not read the options"):
        stage_filters = parse_filters(filters or ())
        implement_filters = parse_implement_filters(filters or ())
    with _exit_on_failure("Could not explain the issue"):
        _, store = _open_store(target)
        explained = explain_item(
            store,
            repo=target,
            source=source or model_clone(target),
            number=item,
            stage_filters=stage_filters,
            implement_filters=implement_filters,
            stage_limit=limit,
            implement_limit=limit,
        )
    write_stdout(render_explanation(explained) + "\n")


def _resolve_comment(comment: str, comment_file: Path | None) -> str:
    """Extract comment text from inline option or file, raising if invalid or missing."""
    clean = comment.strip()
    if comment_file is not None:
        if not comment_file.is_file():
            print_error(f"Comment file not found: {comment_file}")
            raise typer.Exit(1)
        clean = comment_file.read_text(encoding="utf-8").strip()
    if not clean:
        print_error("An evidence comment is required (--comment or --comment-file).")
        raise typer.Exit(1)
    return clean


@app.command("return", help=HELP.roadmap.return_item)
@dry_run_class("request-plan")
def return_cmd(
    item: Annotated[int, typer.Argument(help=HELP.roadmap.return_item_arg)],
    comment: Annotated[str, typer.Option("--comment", "-c", help=HELP.roadmap.return_comment)] = "",
    comment_file: Annotated[
        Path | None, typer.Option("--comment-file", help=HELP.roadmap.return_comment_file)
    ] = None,
    repo: RepoOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.return_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.return_confirm)] = False,
) -> None:
    """Return an item to New on the roadmap with an evidence comment."""
    _one_mode(dry_run=dry_run, confirm=confirm)
    clean_comment = _resolve_comment(comment, comment_file)
    target = _target(repo)

    from devops_cli.roadmap.return_item import (
        apply_return,
        dry_run_return,
        plan_return,
        render_return_plan,
    )

    if dry_run or is_dry_run():
        reads, writes = dry_run_return(target, item)
        render_dry_run("return", target, reads, writes)
        return

    with _exit_on_failure("Could not return roadmap item"):
        _, store = _open_store(target)
        plan = plan_return(store, item, clean_comment, target)
        if not confirm:
            write_stdout(render_return_plan(plan) + "\n\nPlan only: pass --confirm to apply.\n")
            return
        apply_return(store, plan)
        print_success(f"Returned item #{item} to New and posted evidence comment.")


def _claim_or_release(
    item: int, claimant: Claimant | None, repo: str | None, *, dry_run: bool, confirm: bool
) -> None:
    """Plan a claim of `item` as `claimant`, or its release when `claimant` is None, and write it
    only with `--confirm`."""
    _one_mode(dry_run=dry_run, confirm=confirm)
    target = _target(repo)
    if dry_run or is_dry_run():
        reads, writes = dry_run_claim(target, item)
        render_dry_run("release" if claimant is None else "claim", target, reads, writes)
        return
    texts = MESSAGES.roadmap
    with _exit_on_failure("Could not claim roadmap item"):
        _, store = _open_store(target)
        plan = plan_claim(store, item, claimant, target)
        if not confirm:
            write_stdout(f"{render_claim_plan(plan)}\n\n{texts.claim_plan_only}\n")
            return
        wrote = apply_claim(store, plan)
    if plan.target is None:
        print_success(
            (texts.claim_released if wrote else texts.claim_release_unchanged).format(number=item)
        )
    else:
        print_success(
            (texts.claim_done if wrote else texts.claim_unchanged).format(
                number=item, owner=plan.target
            )
        )


@app.command("claim", help=HELP.roadmap.claim)
@dry_run_class("request-plan")
def claim_cmd(
    item: Annotated[int, typer.Argument(help=HELP.roadmap.claim_arg)],
    claimant: Annotated[Claimant, typer.Option("--as", help=HELP.roadmap.claim_as)],
    repo: RepoOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.claim_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.claim_confirm)] = False,
) -> None:
    """Claim an item for an agent or a person with an `owner/*` label."""
    _claim_or_release(item, claimant, repo, dry_run=dry_run, confirm=confirm)


@app.command("release", help=HELP.roadmap.release)
@dry_run_class("request-plan")
def release_cmd(
    item: Annotated[int, typer.Argument(help=HELP.roadmap.release_arg)],
    repo: RepoOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.claim_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.release_confirm)] = False,
) -> None:
    """Release an item: remove its `owner/*` label."""
    _claim_or_release(item, None, repo, dry_run=dry_run, confirm=confirm)
