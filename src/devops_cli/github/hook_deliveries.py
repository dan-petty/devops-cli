"""The deliveries of the webhooks of a repository that got no 2xx answer, as GitHub records them
(#5017).

A refusal at the Cloudflare edge, such as an Access application that does not let a GitHub
address through, answers before Traefik and the webhook route. So the deliveries counter of the
route, `devops_cli_service_webhook_deliveries_total`, cannot show it, and GitHub does not send a
failed delivery again. GitHub records the status code of each delivery. The metrics row of the
Service reads the active hooks of its repository and the newest page of deliveries of each one,
and sets the gauge `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to the
deliveries of the last `DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES` minutes whose code is not
2xx.

The reads go through `gh api`, so the request budget of the Service counts each one: one for the
hooks and one for each active hook. The installation token reads them with the permission
`repository_hooks: read` (ADR 0015). A code that the last read of the repository set and this read
does not find is set to 0, because the metrics hold no call that removes a series. A read that
fails raises, so the row fails, and the gauge keeps the value of the last read.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta
from http import HTTPStatus

from pydantic import BaseModel, TypeAdapter

from devops_cli.config.constants import CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES
from devops_cli.config.defaults import (
    DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE,
    DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES,
)
from devops_cli.github.client import GhCliClient
from devops_cli.github.repo_ref import RepoRef
from devops_cli.telemetry.metrics import GLOBAL_METRICS


class Hook(BaseModel):
    """A webhook of a repository, as `GET /repos/{owner}/{repo}/hooks` lists it."""

    id: int
    active: bool


class HookDelivery(BaseModel):
    """One delivery of a webhook, as `GET /repos/{owner}/{repo}/hooks/{id}/deliveries` lists it."""

    delivered_at: datetime
    status_code: int


_HOOKS: TypeAdapter[list[Hook]] = TypeAdapter(list[Hook])
_DELIVERIES: TypeAdapter[list[HookDelivery]] = TypeAdapter(list[HookDelivery])

_set_codes: dict[str, set[str]] = {}
"""The codes that the last read of each repository set above 0 in this process, by the key of the
repository."""


def reset_set_codes() -> None:
    """Forget the codes set, as a new process has set none."""
    _set_codes.clear()


def failed_deliveries(deliveries: Iterable[HookDelivery], since: datetime) -> Counter[str]:
    """The deliveries at `since` or later whose status code is not 2xx, counted by the code."""
    return Counter(
        str(delivery.status_code)
        for delivery in deliveries
        if delivery.delivered_at >= since
        and not HTTPStatus.OK <= delivery.status_code < HTTPStatus.MULTIPLE_CHOICES
    )


def read_delivery_failures(repo: RepoRef, since: datetime) -> Counter[str]:
    """The failed deliveries of each active hook of `repo` at `since` or later, by code, from the
    newest page of deliveries of each hook. A failed read raises `GitHubOperationError`, and an
    answer that is not a list of hooks or deliveries raises `pydantic.ValidationError`."""
    client = GhCliClient()
    hooks = _HOOKS.validate_json(client.api(f"repos/{repo.display}/hooks"))
    failed: Counter[str] = Counter()
    for hook in hooks:
        if not hook.active:
            continue
        page = client.api(
            f"repos/{repo.display}/hooks/{hook.id}/deliveries"
            f"?per_page={DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE}"
        )
        failed.update(failed_deliveries(_DELIVERIES.validate_json(page), since))
    return failed


def report_delivery_failures(repo: str, now: datetime) -> Counter[str]:
    """Read the failed deliveries of the hooks of `repo` in the window before `now`, set the gauge
    of each code, set the codes of the last read that this read does not find to 0, and return
    the counts by code."""
    ref = RepoRef(repo)
    since = now - timedelta(minutes=DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES)
    failed = read_delivery_failures(ref, since)
    gone = _set_codes.get(ref.key, set()) - failed.keys()
    for code in sorted(gone):
        _set_gauge(ref, code, 0.0)
    for code, count in sorted(failed.items()):
        _set_gauge(ref, code, float(count))
    _set_codes[ref.key] = set(failed)
    return failed


def _set_gauge(repo: RepoRef, code: str, value: float) -> None:
    GLOBAL_METRICS.set_gauge(
        CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
        value,
        labels={"repo": repo.key, "code": code},
    )


__all__ = [
    "Hook",
    "HookDelivery",
    "failed_deliveries",
    "read_delivery_failures",
    "report_delivery_failures",
    "reset_set_codes",
]
