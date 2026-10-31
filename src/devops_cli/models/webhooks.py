"""Typed webhook payloads: the fields the Service reads, validated after the delivery's signature."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WebhookRepository(BaseModel):
    """The repository a GitHub event is about."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    full_name: str


class WebhookSender(BaseModel):
    """The account whose action caused a GitHub event."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    login: str


class WebhookIssue(BaseModel):
    """The issue an issue event is about."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    number: int | None = None


class GitHubWebhookPayload(BaseModel):
    """What every GitHub event carries that the Service reads. The rest of a payload differs by
    event and is ignored. An event has no `action` when GitHub gives it none (a `ping`, a `push`),
    and no `sender` when GitHub names no account."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    action: str | None = None
    repository: WebhookRepository
    sender: WebhookSender | None = None
    issue: WebhookIssue | None = None
