"""`devops k8s push-secrets`: write the cluster Secret table from the workstation keyring.

The direction is workstation keyring → cluster, the reverse of `devops k8s sync-secrets`.
`devops k8s deploy-stack` runs the same push (`push_for_stacks`) before its manifests.
`--dry-run` makes no request and prints the requests a push would make; `--plan` reads the
keyring and the cluster to print each key's state, and writes nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated

import typer

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.commands.k8s.networking import VALID_STACKS
from devops_cli.config.settings import SecretStorageError, require_persistent_keyring
from devops_cli.dry_run import is_dry_run, render_request_plan
from devops_cli.exceptions.k8s import ClusterSecretPushError, ClusterSecretWriteError
from devops_cli.k8s.cluster_secrets import (
    BASE_STACK,
    CLUSTER_SECRETS,
    DETACHED_STACKS,
    ClusterSecret,
    secret_names,
    secrets_by_ref,
    secrets_for_stacks,
    table_stacks,
)
from devops_cli.k8s.secret_push import (
    EntryState,
    PushMode,
    PushOptions,
    PushPlan,
    PushResult,
    describe_problems,
    dry_run_push,
    execute_push,
    plan_push,
    preview_restarts,
    reads_github,
    secret_line,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_warning

ALL_STACKS = "all"


def _push_stacks() -> tuple[str, ...]:
    """The stacks `--stack` accepts: the table's, deploy-stack's and `all`."""
    return tuple(dict.fromkeys((BASE_STACK, *VALID_STACKS, *DETACHED_STACKS, *table_stacks())))


def _select(stack: str, only: Sequence[str]) -> tuple[ClusterSecret, ...]:
    """The rows `--only` names, else the rows of `--stack`; an unknown name exits 2."""
    if only:
        selected, unknown = secrets_by_ref(only)
        if unknown:
            print_error(
                MESSAGES.k8s.push_unknown_secret.format(
                    names=", ".join(unknown), known=", ".join(secret_names())
                ),
                prefix=False,
                safe=True,
            )
            raise typer.Exit(2)
        return selected
    if stack not in _push_stacks():
        print_error(
            MESSAGES.k8s.push_unknown_stack.format(stack=stack, known=", ".join(_push_stacks())),
            prefix=False,
            safe=True,
        )
        raise typer.Exit(2)
    return CLUSTER_SECRETS if stack == ALL_STACKS else secrets_for_stacks([stack])


def _render(plan: PushPlan, options: PushOptions, *, preview: bool) -> None:
    """One line per Secret, then warnings, restart commands and notes. Never a value."""
    for skipped in plan.skipped_namespaces:
        print_warning(
            MESSAGES.k8s.push_namespace_missing.format(
                namespace=skipped.namespace, secret=skipped.ref
            ),
            prefix=False,
            safe=True,
        )
    for secret_plan in plan.secrets:
        print_info(secret_line(secret_plan, preview=preview), prefix=False, safe=True)
        for entry in secret_plan.entries:
            if entry.state is EntryState.SKIPPED:
                print_warning(entry.problem, prefix=False, safe=True)
        for command in secret_plan.restart_commands:
            print_info(
                MESSAGES.k8s.push_restart_command.format(command=command), prefix=False, safe=True
            )
        if secret_plan.secret.change_note and secret_plan.changed():
            print_warning(secret_plan.secret.change_note, prefix=False, safe=True)


def _fail(message: str) -> typer.Exit:
    """Print a push failure; nothing was written."""
    print_error(MESSAGES.k8s.push_failed.format(reason=message), prefix=False, safe=True)
    return typer.Exit(1)


def _fail_while_writing(exc: ClusterSecretWriteError) -> typer.Exit:
    """Print a failure part-way through writing, naming what was already written."""
    print_error(
        MESSAGES.k8s.push_write_failed.format(
            completed="; ".join(exc.completed) or "nothing", reason=str(exc)
        ),
        prefix=False,
        safe=True,
    )
    return typer.Exit(1)


def require_keyring_for_push() -> None:
    """Exit 1 unless the keyring is persistent and unlocked, before anything is read or applied."""
    try:
        require_persistent_keyring()
    except SecretStorageError as exc:
        raise _fail(str(exc)) from exc


def _render_dry_run(result: PushResult) -> None:
    """The requests a push would make, in order, then what the placeholders and order mean."""
    render_request_plan(
        MESSAGES.k8s.push_dry_run_heading,
        result.requests,
        (MESSAGES.k8s.push_dry_run_writes, MESSAGES.dry_run.placeholders_note),
    )


def run_push(
    selected: Sequence[ClusterSecret], options: PushOptions, *, mode: PushMode
) -> PushResult:
    """Push, plan (`--plan`: reads only) or dry-run (no request at all), and return the result.

    A planning failure exits 1 before any write; a failure while writing exits 1 naming what
    was already written.
    """
    if mode is PushMode.DRY_RUN:
        result = dry_run_push(selected, options)
        _render_dry_run(result)
        return result
    plan_only = mode is PushMode.PLAN
    try:
        plan = plan_push(selected, options)
        if plan_only:
            preview_restarts(plan, options)
    except (SecretStorageError, ClusterSecretPushError) as exc:
        raise _fail(str(exc)) from exc
    if plan_only:
        context = f" (context {options.context})" if options.context else ""
        sources = (
            MESSAGES.k8s.push_plan_sources_github
            if reads_github(plan)
            else MESSAGES.k8s.push_plan_sources
        )
        print_info(
            MESSAGES.k8s.push_plan_read.format(sources=sources, context=context),
            prefix=False,
            safe=True,
        )
        _render(plan, options, preview=True)
    if plan.problems():
        raise _fail(describe_problems(plan))
    if plan_only:
        return PushResult(mode, plan)
    try:
        execute_push(plan, options)
    except ClusterSecretWriteError as exc:
        raise _fail_while_writing(exc) from exc
    _render(plan, options, preview=False)
    return PushResult(mode, plan)


def push_for_stacks(stacks: Sequence[str], context: str | None) -> None:
    """deploy-stack's push: its stacks' rows with `--stack` semantics, no rotation, restarts on."""
    run_push(secrets_for_stacks(stacks), PushOptions(context=context), mode=PushMode.PUSH)


def push_secrets(
    stack: Annotated[str, typer.Option("--stack", "-s", help=HELP.k8s.push_stack)] = ALL_STACKS,
    only: Annotated[
        list[str] | None, typer.Option("--only", help=HELP.k8s.push_only, metavar="NS/NAME")
    ] = None,
    github_account: Annotated[
        str | None,
        typer.Option("--github-account", help=HELP.k8s.push_github_account, metavar="LOGIN"),
    ] = None,
    rotate: Annotated[bool, typer.Option("--rotate", help=HELP.k8s.push_rotate)] = False,
    restart: Annotated[
        bool, typer.Option("--restart/--no-restart", help=HELP.k8s.push_restart)
    ] = True,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    plan: Annotated[bool, typer.Option("--plan", help=HELP.k8s.push_plan)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.push_dry_run)] = False,
) -> None:
    """Write the cluster's Secrets from the OS keyring: workstation keyring → cluster.

    The reverse of `sync-secrets`. Values never reach argv, a file, an annotation or the output.
    `--dry-run` makes no request, and wins over `--plan`, which reads but writes nothing.
    """
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")
    selected = _select(stack, only or [])
    options = PushOptions(
        context=effective_context,
        github_account=github_account,
        rotate=rotate,
        restart=restart,
        strict_namespaces=bool(only),
    )
    if dry_run or is_dry_run():
        mode = PushMode.DRY_RUN
    else:
        mode = PushMode.PLAN if plan else PushMode.PUSH
    run_push(selected, options, mode=mode)
