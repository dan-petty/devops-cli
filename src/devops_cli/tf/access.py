"""Agent access level, core budget floor, and reader App credentials for `tf/github` stacks (#5320)."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Final

from devops_cli.config.constants import (
    CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS,
    CONST_TF_GITHUB_READER_SLUG,
)
from devops_cli.config.defaults import DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR
from devops_cli.core.caller import is_agent_caller
from devops_cli.exceptions import ConfigurationError
from devops_cli.exceptions.tf import TFAccessRefusedError, TFBudgetError
from devops_cli.lang import ERRORS

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings

TF_AGENT_ACCESS_KEY: Final[str] = "tf.stacks[].agent_access"
TF_GITHUB_READER_APP_ID_KEY: Final[str] = "tf.github_reader.app_id"
TF_GITHUB_READER_INSTALLATION_ID_KEY: Final[str] = "tf.github_reader.installation_id"
TF_GITHUB_READER_PRIVATE_KEY_KEY: Final[str] = "tf.github_reader.private_key"
_AGENT_WRITE_ACTIONS: Final[frozenset[str]] = frozenset({"apply", "destroy"})


class TFAccessLevel(StrEnum):
    """What an agent may do on a configured OpenTofu stack. A person may do everything."""

    PLAN = "plan"
    APPLY = "apply"


def normalize_stack_path(path: Path | str) -> str:
    """Normalize stack path separators and leading/trailing markers for deterministic comparisons."""
    parts = [part for part in str(path).replace("\\", "/").split("/") if part and part != "."]
    return "/".join(parts)


def is_github_stack_path(path: Path | str) -> bool:
    """Whether `path` points inside a `tf/github` directory tree."""
    parts = Path(str(path).replace("\\", "/")).parts
    return any((first, second) == ("tf", "github") for first, second in itertools.pairwise(parts))


def _stack_matches_target(target: Path, configured_path: str) -> bool:
    norm = normalize_stack_path(configured_path)
    if not norm:
        return False
    entry_parts = tuple(norm.split("/"))
    resolved_target = target.resolve()
    target_parts = resolved_target.parts
    if len(target_parts) >= len(entry_parts) and target_parts[-len(entry_parts) :] == entry_parts:
        return True
    return Path(configured_path).resolve() == resolved_target


def stack_agent_access(target: Path, settings: Settings | None = None) -> TFAccessLevel | None:
    """Resolve `agent_access` for `target`, defaulting `tf/github` stacks to `plan`."""
    from devops_cli.config.settings import load_settings

    active = settings or load_settings()
    for entry in active.tf.stacks:
        if _stack_matches_target(target, entry.path):
            if entry.agent_access is not None:
                return entry.agent_access
            return TFAccessLevel.PLAN if is_github_stack_path(target) else None
    return TFAccessLevel.PLAN if is_github_stack_path(target) else None


def require_agent_access(target: Path, *, action: str, settings: Settings | None = None) -> None:
    """Refuse `apply` or `destroy` when an agent targets a stack whose level is below `apply`."""
    if action not in _AGENT_WRITE_ACTIONS or not is_agent_caller():
        return
    level = stack_agent_access(target, settings)
    if level is None or level is TFAccessLevel.APPLY:
        return
    raise TFAccessRefusedError(
        ERRORS.tf.agent_access_refused.format(
            action=action,
            stack=str(target),
            level=level.value,
            needed=TFAccessLevel.APPLY.value,
            key=TF_AGENT_ACCESS_KEY,
        ),
        key=TF_AGENT_ACCESS_KEY,
    )


def check_github_core_budget(*, floor: int = DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR) -> None:
    """Refuse a `tf/github` plan when the shared `run_gh` core ledger is below `floor`."""
    from devops_cli.github.rate_limiter import get_github_rate_limiter

    quota = get_github_rate_limiter().get_quota("core")
    if not quota.is_valid():
        return
    remaining = quota.remaining or 0
    if remaining >= floor:
        return
    reset_at = (
        datetime.fromtimestamp(quota.reset_epoch, UTC).isoformat()
        if quota.reset_epoch is not None
        else "unknown"
    )
    raise TFBudgetError(
        ERRORS.tf.core_budget_below_floor.format(remaining=remaining, floor=floor, reset=reset_at),
        remaining=remaining,
        floor=floor,
    )


def reader_github_env(settings: Settings | None = None) -> dict[str, str]:
    """Mint a read-only installation token for `devops-settings-reader` on agent plans."""
    if not is_agent_caller():
        return {}
    from devops_cli.config.settings import get_tf_github_reader_private_key, load_settings
    from devops_cli.github.app_installation import GitHubApp, mint_installation_token

    active = settings or load_settings()
    reader = active.tf.github_reader
    private_key = (get_tf_github_reader_private_key(active) or "").strip()
    if reader.app_id is None or reader.installation_id is None or not private_key:
        raise ConfigurationError(
            ERRORS.tf.reader_credentials_missing.format(
                app_id_key=TF_GITHUB_READER_APP_ID_KEY,
                installation_id_key=TF_GITHUB_READER_INSTALLATION_ID_KEY,
                private_key_key=TF_GITHUB_READER_PRIVATE_KEY_KEY,
            ),
            key=TF_GITHUB_READER_PRIVATE_KEY_KEY,
        )

    app = GitHubApp(
        app_id=reader.app_id,
        installation_id=reader.installation_id,
        slug=CONST_TF_GITHUB_READER_SLUG,
        private_key=private_key,
        permissions=CONST_GITHUB_APP_READ_TOKEN_PERMISSIONS,
        key_source=TF_GITHUB_READER_PRIVATE_KEY_KEY,
    )
    token, reason, _expires_at = mint_installation_token(app)
    if not token:
        raise TFAccessRefusedError(
            ERRORS.tf.reader_token_failed.format(reason=reason),
            key=TF_GITHUB_READER_PRIVATE_KEY_KEY,
        )
    return {"GITHUB_TOKEN": token}


def prepare_tf_stack_run(
    target: Path,
    *,
    action: str,
    dry_run: bool = False,
    settings: Settings | None = None,
) -> dict[str, str] | None:
    """Enforce agent access, core budget floor, and reader App token before running `tofu`."""
    from devops_cli.config.settings import load_settings

    active = settings or load_settings()
    require_agent_access(target, action=action, settings=active)
    if not is_github_stack_path(target) or action != "plan":
        return None
    check_github_core_budget()
    if dry_run or not is_agent_caller():
        return None
    return reader_github_env(active)


__all__ = [
    "TF_AGENT_ACCESS_KEY",
    "TF_GITHUB_READER_APP_ID_KEY",
    "TF_GITHUB_READER_INSTALLATION_ID_KEY",
    "TF_GITHUB_READER_PRIVATE_KEY_KEY",
    "TFAccessLevel",
    "check_github_core_budget",
    "is_github_stack_path",
    "normalize_stack_path",
    "prepare_tf_stack_run",
    "reader_github_env",
    "require_agent_access",
    "stack_agent_access",
]
