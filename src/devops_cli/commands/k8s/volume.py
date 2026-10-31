"""Kubernetes volume commands: move a local-path claim to another node, reclaim orphaned volumes."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from devops_cli.config.constants import (
    CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX,
    CONST_K8S_VOLUME_MOVE_SAVE_DIR,
    CONST_K8S_VOLUME_RECLAIM_HEADING,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.exceptions.k8s import (
    VolumeMoveError,
    VolumeMoveRefusedError,
    VolumeMoveStrandedError,
)
from devops_cli.k8s.volume import (
    get_k8s_client,
    plan_volume_reclaim_requests,
    reclaim_volume,
    verify_volume_orphaned,
)
from devops_cli.k8s.volume_move import (
    POINT_OF_NO_RETURN_INDEX,
    VolumeMovePlan,
    VolumeMoveResult,
    delete_old_volume_command,
    describe_volume_move,
    dry_run_volume_move,
    parse_claim_ref,
    plan_volume_move,
    run_volume_move,
)
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    format_bytes,
    print_error,
    print_info,
    print_step,
    print_success,
    print_warning,
)

app = new_typer(help=HELP.k8s.volume_app, no_args_is_help=True)


def _is_interactive() -> bool:
    """Check if the session has an interactive TTY standard input."""
    return getattr(sys.stdin, "isatty", lambda: False)()


@app.command(name="reclaim", help=HELP.k8s.volume_reclaim)
@dry_run_class("request-plan")
def volume_reclaim_cmd(
    name: Annotated[str, typer.Argument(help=HELP.k8s.volume_reclaim_name)],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.k8s.volume_reclaim_dry_run)
    ] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help=HELP.k8s.volume_reclaim_yes)] = False,
    patch: Annotated[bool, typer.Option("--patch", help=HELP.k8s.volume_reclaim_patch)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.k8s.context_target)
    ] = None,
) -> None:
    """Safely reclaim a named PersistentVolume if verified to be genuinely orphaned."""
    if dry_run or is_dry_run():
        requests = plan_volume_reclaim_requests(name=name, patch=patch)
        render_request_plan(CONST_K8S_VOLUME_RECLAIM_HEADING, requests)
        return

    core = get_k8s_client(context=context)
    try:
        pv = core.read_persistent_volume(name=name)
    except Exception as exc:
        print_error(ERRORS.k8s.volume_not_found.format(name=name))
        raise typer.Exit(1) from exc

    is_orphaned, reason = verify_volume_orphaned(core, pv)
    if not is_orphaned:
        print_error(f"Cannot reclaim PersistentVolume '{name}': {reason}")
        raise typer.Exit(1)

    if not yes:
        if not _is_interactive():
            print_error(ERRORS.k8s.volume_reclaim_non_interactive)
            raise typer.Exit(1)
        prompt = f"Are you sure you want to reclaim PersistentVolume '{name}'?"
        if not typer.confirm(prompt, default=False):
            print_info(MESSAGES.k8s.volume_reclaim_aborted.format(name=name))
            return

    action = reclaim_volume(core, name=name, patch=patch)
    print_success(MESSAGES.k8s.volume_reclaimed.format(name=name, action=action))


def _say(message: str) -> None:
    print_info(message, prefix=False, safe=True)


def _print_plan(plan: VolumeMovePlan) -> None:
    """The plan: what the reads found, then each step with the real names."""
    m = MESSAGES.k8s
    _say(m.volume_move_plan_heading.format(namespace=plan.namespace, claim=plan.claim))
    _say(
        m.volume_move_plan_claim.format(
            volume=plan.old_volume,
            size=plan.size,
            storage_class=plan.storage_class,
            node=plan.source_node,
            policy=plan.old_reclaim_policy,
        )
    )
    _say(
        m.volume_move_plan_target.format(
            node=plan.target_node, free=format_bytes(plan.target_free_bytes)
        )
    )
    workloads = ", ".join(f"{w.ref} (replicas: {w.replicas})" for w in plan.workloads)
    _say(m.volume_move_plan_workloads.format(workloads=workloads, pods=", ".join(plan.pods)))
    if plan.applications:
        _say(
            m.volume_move_plan_argocd.format(
                applications=", ".join(plan.applications), paused=", ".join(plan.paused)
            )
        )
    else:
        _say(m.volume_move_plan_no_argocd)
    _say(m.volume_move_plan_steps)
    for number, text in enumerate(describe_volume_move(plan), start=1):
        _say(f"{number:>3}. {text}")
    _say(m.volume_move_plan_point_of_no_return.format(number=POINT_OF_NO_RETURN_INDEX + 1))


def _print_summary(result: VolumeMoveResult, context: str | None) -> None:
    m = MESSAGES.k8s
    plan = result.plan
    print_success(
        m.volume_move_done.format(
            namespace=plan.namespace, claim=plan.claim, node=plan.target_node
        ),
        prefix=False,
        safe=True,
    )
    _say(
        m.volume_move_done_new_volume.format(
            volume=result.new_volume, namespace=plan.namespace, claim=plan.claim
        )
    )
    _say(
        m.volume_move_done_old_volume.format(
            volume=plan.old_volume,
            node=plan.source_node,
            command=delete_old_volume_command(plan, context),
        )
    )
    _say(m.volume_move_done_saved.format(path=result.saved_claim))


def _print_undone(exc: VolumeMoveError) -> None:
    m = MESSAGES.k8s
    print_error(str(exc), prefix=False, safe=True)
    if exc.undone:
        _say(m.volume_move_undone_steps.format(steps="; ".join(exc.undone)))
    else:
        _say(m.volume_move_undone_nothing)
    if exc.undo_failures:
        print_error(
            m.volume_move_undo_failed.format(failures="; ".join(exc.undo_failures)),
            prefix=False,
            safe=True,
        )


def _print_stranded(exc: VolumeMoveStrandedError, plan: VolumeMovePlan) -> None:
    m = MESSAGES.k8s
    print_error(str(exc), prefix=False, safe=True)
    if exc.paused:
        print_warning(
            m.volume_move_stranded_paused.format(
                applications=", ".join(exc.paused), namespace=plan.namespace, claim=plan.claim
            ),
            prefix=False,
            safe=True,
        )
    _say(m.volume_move_done_saved.format(path=exc.saved_claim))
    _say(
        m.volume_move_stranded_volumes.format(old_volume=exc.old_volume, new_volume=exc.new_volume)
    )
    _say(m.volume_move_stranded_remaining)
    first = len(describe_volume_move(plan)) - len(exc.remaining) + 1
    for number, text in enumerate(exc.remaining, start=first):
        _say(f"{number:>3}. {text}")


def _plan_or_exit(
    namespace: str, claim: str, to_node: str | None, context: str | None
) -> VolumeMovePlan:
    """The plan, or exit 1 naming each problem: the plan only reads, so nothing changed."""
    try:
        return plan_volume_move(namespace, claim, to_node=to_node, context=context)
    except VolumeMoveRefusedError as exc:
        print_error(str(exc), prefix=False, safe=True)
        for problem in exc.problems:
            print_error(f"- {problem}", prefix=False, safe=True)
        raise typer.Exit(1) from exc
    except VolumeMoveError as exc:
        print_error(
            MESSAGES.k8s.volume_move_read_failed.format(
                namespace=namespace, claim=claim, reason=exc
            ),
            prefix=False,
            safe=True,
        )
        raise typer.Exit(1) from exc


def _run_or_exit(plan: VolumeMovePlan, context: str | None) -> VolumeMoveResult:
    """Run the move, or exit 1 naming what it undid, or the state it left after the old claim."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    save_dir = resolve_data_path(load_settings().data.dir) / CONST_K8S_VOLUME_MOVE_SAVE_DIR
    _say(
        MESSAGES.k8s.volume_move_start.format(
            namespace=plan.namespace, claim=plan.claim, node=plan.target_node
        )
    )
    try:
        return run_volume_move(plan, context=context, save_dir=save_dir, progress=print_step)
    except VolumeMoveStrandedError as exc:
        _print_stranded(exc, plan)
        raise typer.Exit(1) from exc
    except VolumeMoveError as exc:
        _print_undone(exc)
        raise typer.Exit(1) from exc


@app.command(name="move", help=HELP.k8s.volume_move)
@dry_run_class("request-plan")
def volume_move_cmd(
    claim: Annotated[str, typer.Argument(metavar="NAMESPACE/CLAIM", help=HELP.k8s.volume_move_ref)],
    to_node: Annotated[
        str | None, typer.Option("--to-node", metavar="NODE", help=HELP.k8s.volume_move_to_node)
    ] = None,
    plan: Annotated[bool, typer.Option("--plan", help=HELP.k8s.volume_move_plan)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.volume_move_dry_run)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Move a local-path claim to a volume on another node, and bind the claim to it."""
    from devops_cli.commands.k8s.cluster_runtime import resolve_effective_context
    from devops_cli.core.validation import validate_k8s_context_name

    effective_context = resolve_effective_context(context)
    if effective_context:
        validate_k8s_context_name(effective_context, "context")
    try:
        namespace, name = parse_claim_ref(claim)
    except VolumeMoveRefusedError as exc:
        print_error(str(exc), prefix=False, safe=True)
        raise typer.Exit(2) from exc
    if dry_run or is_dry_run():
        render_request_plan(
            MESSAGES.k8s.volume_move_dry_run_heading,
            dry_run_volume_move(namespace, name, to_node=to_node, context=effective_context),
            (
                MESSAGES.k8s.volume_move_dry_run_undo.format(
                    claim=f"{name}{CONST_K8S_VOLUME_MOVE_CLAIM_SUFFIX}"
                ),
                MESSAGES.dry_run.placeholders_note,
            ),
        )
        return
    move_plan = _plan_or_exit(namespace, name, to_node, effective_context)
    _print_plan(move_plan)
    if plan:
        return
    _print_summary(_run_or_exit(move_plan, effective_context), effective_context)


__all__ = [
    "_is_interactive",
    "app",
    "volume_move_cmd",
    "volume_reclaim_cmd",
]
