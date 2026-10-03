"""A repository's roadmap configuration: `.github/roadmap.toml`, read through the roadmap store.

Every runner, from a terminal now and the service later, reads the file through the contents
API at one ref, so all of them read the same file whatever the local checkout holds. A failed
read, a missing `board` or a key the model doesn't know stops the command.
"""

from __future__ import annotations

import tomllib

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as InvalidConfigError

from devops_cli.config.constants import CONST_ROADMAP_CONFIG_PATH
from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_DISCOVERY_THRESHOLD,
    DEFAULT_ROADMAP_PLANNING_HORIZON,
    DEFAULT_ROADMAP_RELEASE_CAP,
    DEFAULT_ROADMAP_STALL_DAYS,
)
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.roadmap.store import RoadmapStore


class RoadmapConfig(BaseModel):
    """The board and the numbers the roadmap jobs work to. `board` has no default."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    board: int = Field(ge=1)
    release_cap: int = Field(default=DEFAULT_ROADMAP_RELEASE_CAP, ge=1)
    discovery_threshold: int = Field(default=DEFAULT_ROADMAP_DISCOVERY_THRESHOLD, ge=0)
    planning_horizon: int = Field(default=DEFAULT_ROADMAP_PLANNING_HORIZON, ge=0)
    stall_days: int = Field(default=DEFAULT_ROADMAP_STALL_DAYS, ge=1)


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


__all__ = ["RoadmapConfig", "parse_roadmap_config", "read_roadmap_config"]
