"""A repository's roadmap configuration: `.github/roadmap.toml`, read through the roadmap store.

Every runner, from a terminal now and the service later, reads the file through the contents
API at one ref, so all of them read the same file whatever the local checkout holds. A failed
read, a missing `board` or a key the model doesn't know stops the command.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as InvalidConfigError

from devops_cli.config.constants import CONST_ROADMAP_CONFIG_PATH
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_DISCOVERY_THRESHOLD,
    DEFAULT_ROADMAP_OPEN_ISSUE_LIMIT,
    DEFAULT_ROADMAP_OVERAGE_STEP_FRACTION,
    DEFAULT_ROADMAP_PLANNING_HORIZON,
    DEFAULT_ROADMAP_RELEASE_CAP,
    DEFAULT_ROADMAP_RELEASE_CREDIT_BASE,
    DEFAULT_ROADMAP_RELEASE_CREDIT_PER_DELIVERED_ITEM,
    DEFAULT_ROADMAP_RELEASE_ITEM_TARGET,
    DEFAULT_ROADMAP_RELEASE_SLOTS,
    DEFAULT_ROADMAP_STALL_DAYS,
    DEFAULT_ROADMAP_THROTTLE_START_FRACTION,
)
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.store import RoadmapStore

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner


class RoadmapConfig(BaseModel):
    """The board and the numbers the roadmap jobs work to. `board` has no default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    board: int = Field(ge=1)
    release_cap: int = Field(default=DEFAULT_ROADMAP_RELEASE_CAP, ge=1)
    release_slots: int = Field(default=DEFAULT_ROADMAP_RELEASE_SLOTS, ge=0)
    discovery_threshold: int = Field(default=DEFAULT_ROADMAP_DISCOVERY_THRESHOLD, ge=0)
    planning_horizon: int = Field(default=DEFAULT_ROADMAP_PLANNING_HORIZON, ge=0)
    stall_days: int = Field(default=DEFAULT_ROADMAP_STALL_DAYS, ge=1)
    open_issue_limit: int = Field(default=DEFAULT_ROADMAP_OPEN_ISSUE_LIMIT, ge=1)
    throttle_start_fraction: float = Field(
        default=DEFAULT_ROADMAP_THROTTLE_START_FRACTION, gt=0.0, lt=1.0
    )
    overage_step_fraction: float = Field(
        default=DEFAULT_ROADMAP_OVERAGE_STEP_FRACTION, gt=0.0, lt=1.0
    )
    release_credit_base: int = Field(default=DEFAULT_ROADMAP_RELEASE_CREDIT_BASE, ge=0)
    release_credit_per_delivered_item: int = Field(
        default=DEFAULT_ROADMAP_RELEASE_CREDIT_PER_DELIVERED_ITEM, ge=0
    )
    release_item_target: int = Field(default=DEFAULT_ROADMAP_RELEASE_ITEM_TARGET, ge=1)

    @property
    def release_limit(self) -> int:
        """The most items a release holds before a start trims it or a joining critical fix
        descopes one: its cap plus its slots."""
        return self.release_cap + self.release_slots


def parse_roadmap_config(text: str) -> RoadmapConfig:
    """Parse `.github/roadmap.toml`, naming the key at fault when it is invalid."""
    try:
        return RoadmapConfig.model_validate(tomllib.loads(text))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigurationError(
            f"{CONST_ROADMAP_CONFIG_PATH} is not valid TOML: {exc}",
            details={"path": CONST_ROADMAP_CONFIG_PATH},
        ) from exc
    except InvalidConfigError as exc:
        first = exc.errors()[0]
        key = ".".join(str(part) for part in first["loc"]) or "(root)"
        raise ConfigurationError(
            f"{CONST_ROADMAP_CONFIG_PATH}: {key}: {first['msg']}",
            key=key[:256],
            details={"path": CONST_ROADMAP_CONFIG_PATH},
        ) from exc


def read_roadmap_config(store: RoadmapStore, *, ref: str | None) -> RoadmapConfig:
    """Read and parse the repository's roadmap configuration on `ref` through `store`."""
    return parse_roadmap_config(store.repository_file(CONST_ROADMAP_CONFIG_PATH, ref=ref))


def open_roadmap(
    repo: str, *, ref: str | None, runner: GhRunner | None = None, board_filter: str = ""
) -> tuple[RoadmapConfig, RoadmapStore]:
    """`repo`'s roadmap configuration on `ref`, and the roadmap store on the board it names,
    whose board reads pass the job's Projects filter `board_filter`; both stores run their `gh`
    commands through `runner` when one is given."""
    config = read_roadmap_config(roadmap_store.get_roadmap_store(repo, runner=runner), ref=ref)
    owner = repo.split("/")[0]
    board = roadmap_store.get_roadmap_store(
        repo,
        board_owner=owner,
        board_number=config.board,
        runner=runner,
        board_filter=board_filter,
    )
    return config, board


__all__ = ["RoadmapConfig", "open_roadmap", "parse_roadmap_config", "read_roadmap_config"]
