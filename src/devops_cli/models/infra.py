"""Pydantic models of `devops infra`: the commit that a command read (#5162) and the onboarding
report of an infra repo (#5121)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OnboardState(StrEnum):
    """The state of one onboarding check."""

    PRESENT = "present"
    MISSING = "missing"
    NOT_READABLE = "not readable"
    # The check found items that a person reads, such as the tasks that run for real in check
    # mode. They do not stop the onboarding.
    LISTED = "listed"


class ReadCommit(BaseModel):
    """The commit of an infra repo that a command read, and where the checkout is."""

    model_config = ConfigDict(frozen=True)

    ref: str = Field(description="The default branch at origin, as origin/<branch>")
    commit: str = Field(description="The commit of the default branch that the command read")
    checkout_branch: str | None = Field(
        description="The branch of the checkout; none when HEAD is detached or has no commit"
    )
    checkout_commit: str | None = Field(
        description="The commit of the checkout; none when the checkout has no commit"
    )

    @property
    def checkout_differs(self) -> bool:
        """Whether the checkout is at another commit than the one that the command read."""
        return self.checkout_commit != self.commit


class OnboardRow(BaseModel):
    """One check of the onboarding of an infra repo: what it checks, its state and the next step."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(description="The number of the row in the report, from 1")
    check: str = Field(description="What the row checks")
    state: OnboardState = Field(description="How the check ended")
    reason: str | None = Field(default=None, description="Why the row has its state")
    step: str | None = Field(default=None, description="What a person does to fix a gap")
    items: tuple[str, ...] = Field(
        default=(), description="The things that the check found, such as hosts or files"
    )


class OnboardReport(BaseModel):
    """The onboarding report of one infra repo, and the settings entry that `--confirm` writes."""

    model_config = ConfigDict(frozen=True)

    repo: str = Field(description="The GitHub repository of the infra repo, as owner/name")
    path: str = Field(description="The folder of the checkout")
    read: ReadCommit = Field(description="The commit that the report reads")
    rows: tuple[OnboardRow, ...] = Field(description="One row for each check, in order")
    entry: dict[str, Any] = Field(description="The entry of `infra.repos` for the repository")
    written_to: str | None = Field(
        default=None, description="The config file that `--confirm` wrote the entry to"
    )

    @property
    def has_missing(self) -> bool:
        """Whether a row is missing."""
        return any(row.state is OnboardState.MISSING for row in self.rows)


__all__ = ["OnboardReport", "OnboardRow", "OnboardState", "ReadCommit"]
