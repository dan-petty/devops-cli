"""The deliveries of the webhooks of a repository that got no 2xx answer, as GitHub records them
(#5017).

A refusal at the Cloudflare edge, such as an Access application that does not let a GitHub
address through, answers before Traefik and the webhook route. So the deliveries counter of the
route, `devops_cli_service_webhook_deliveries_total`, cannot show it, and GitHub does not send a
failed delivery again. GitHub records the status code of each delivery. The metrics row of the
Service reads the active hooks of its repository and the failed deliveries of each one, newest
first, and sets the gauge `devops_cli_service_webhook_delivery_failures` by `repo` and `code` to
the deliveries whose code is not 2xx since the start of the read.

The row runs when a trigger comes after its interval, so the time between two reads is the
interval and the wait for the next trigger, and one page can hold less than that time (#6012). So
a read starts at the last good read of the repository in this process, or
`DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES` before the read when that is earlier, and follows
the `Link` of each page until a delivery is older than its start. GitHub lists only the failed
deliveries (`status=failure`), so one page holds a longer time. A failed read leaves the start of
the next read where it was, and the first read of a process starts at the window. A read reads at
most `DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES` pages of one hook and then logs a warning that
names the hook, so a long stop of the row costs a bounded number of requests.

The reads go through `gh api`, so the request budget of the Service counts each one: one for the
hooks and one for each page of each active hook. gh prints the headers of a page of deliveries
(`--include`), and the stdlib header parser and httpx read its `Link`. The installation token
reads them with the permission `repository_hooks: read` (ADR 0015). A code that the last read of
the repository set and this read does not find is set to 0, because the metrics hold no call that
removes a series. A read that fails raises, so the row fails, and the gauge keeps the value of the
last read.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterator
from datetime import datetime, timedelta
from email.parser import HeaderParser
from http import HTTPStatus

import httpx2
from pydantic import BaseModel, TypeAdapter

from devops_cli.config.constants import (
    CONST_SERVICE_METRIC_WEBHOOK_DELIVERY_FAILURES,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import (
    DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES,
    DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE,
    DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.client import GhCliClient
from devops_cli.github.repo_ref import RepoRef
from devops_cli.telemetry.metrics import GLOBAL_METRICS

logger = logging.getLogger(__name__)

_API_ORIGIN = httpx2.URL(CONST_URL_GITHUB_API_BASE).origin


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

_read_at: dict[str, datetime] = {}
"""The time of the last good read of each repository in this process, by the key of the
repository: where its next read starts (#6012)."""


def reset_set_codes() -> None:
    """Forget the codes set and the time of each read, as a new process has made no read."""
    _set_codes.clear()
    _read_at.clear()


def _next_endpoint(headers: str, repo: RepoRef) -> str | None:
    """The endpoint of the page that the `Link` of `headers` names as next, or None on the last
    page. A next page on another origin raises, so the token goes to GitHub's API only."""
    fields = HeaderParser().parsestr(headers)
    link = httpx2.Response(HTTPStatus.OK, headers=[("link", v) for v in fields.get_all("link", [])])
    target = link.links.get("next", {}).get("url")
    if target is None:
        return None
    url = httpx2.URL(target)
    if url.origin != _API_ORIGIN:
        raise GitHubOperationError(
            f"GitHub linked the next page of the deliveries of {repo.display} to another origin.",
            operation="gh_api",
            details={"repo": repo.display[:256], "origin": str(url.origin)[:256]},
        )
    return url.raw_path.decode().lstrip("/")


def _pages(client: GhCliClient, repo: RepoRef, hook: int) -> Iterator[list[HookDelivery]]:
    """The pages of the failed deliveries of `hook`, newest first, each read when it is asked
    for, at most `DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES`."""
    endpoint: str | None = (
        f"repos/{repo.display}/hooks/{hook}/deliveries"
        f"?per_page={DEFAULT_SERVICE_HOOK_DELIVERY_PAGE_SIZE}&status=failure"
    )
    for _ in range(DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES):
        if endpoint is None:
            return
        answer = client.api(endpoint, include=True).replace("\r\n", "\n")
        head, _, body = answer.partition("\n\n")
        yield _DELIVERIES.validate_json(body)
        endpoint = _next_endpoint(head.partition("\n")[2], repo)
    if endpoint is not None:
        logger.warning(
            "The read of the failed deliveries of hook %d of %s stopped after %d pages: older "
            "failed deliveries are not counted.",
            hook,
            repo.display,
            DEFAULT_SERVICE_HOOK_DELIVERY_MAX_PAGES,
        )


def _hook_failures(client: GhCliClient, repo: RepoRef, hook: int, since: datetime) -> Counter[str]:
    """The failed deliveries of `hook` at `since` or later, by code: the pages until a delivery
    is older than `since`."""
    failed: Counter[str] = Counter()
    for page in _pages(client, repo, hook):
        for delivery in page:
            if delivery.delivered_at < since:
                return failed
            if not HTTPStatus.OK <= delivery.status_code < HTTPStatus.MULTIPLE_CHOICES:
                failed[str(delivery.status_code)] += 1
    return failed


def read_delivery_failures(repo: RepoRef, since: datetime) -> Counter[str]:
    """The failed deliveries of each active hook of `repo` at `since` or later, by code. A failed
    read raises `GitHubOperationError`, and an answer that is not a list of hooks or deliveries
    raises `pydantic.ValidationError`."""
    client = GhCliClient()
    hooks = _HOOKS.validate_json(client.api(f"repos/{repo.display}/hooks"))
    failed: Counter[str] = Counter()
    for hook in hooks:
        if hook.active:
            failed.update(_hook_failures(client, repo, hook.id, since))
    return failed


def report_delivery_failures(repo: str, now: datetime) -> Counter[str]:
    """Read the failed deliveries of the hooks of `repo` since the last good read, or in the
    window before `now` when that is earlier, set the gauge of each code, set the codes of the
    last read that this read does not find to 0, keep `now` as the start of the next read, and
    return the counts by code."""
    ref = RepoRef(repo)
    since = now - timedelta(minutes=DEFAULT_SERVICE_HOOK_DELIVERY_WINDOW_MINUTES)
    last = _read_at.get(ref.key)
    failed = read_delivery_failures(ref, since if last is None else min(since, last))
    gone = _set_codes.get(ref.key, set()) - failed.keys()
    for code in sorted(gone):
        _set_gauge(ref, code, 0.0)
    for code, count in sorted(failed.items()):
        _set_gauge(ref, code, float(count))
    _set_codes[ref.key] = set(failed)
    _read_at[ref.key] = now
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
    "read_delivery_failures",
    "report_delivery_failures",
    "reset_set_codes",
]
