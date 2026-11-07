"""The Grafana HTTP API behind one client: dashboards, datasources, alert rules and the sync.

`GrafanaClient` dials only what its egress level allows: the HTTP entry point checks each address
at the connect (`devops_cli.http.entry`). A command resolves the base URL and the headers, then
prints what the client returns. This module raises and prints nothing.

`sync_dashboard` holds the rule that a dashboard Grafana holds as provisioned is skipped, not
failed: Grafana refuses an API save over it with a 400, and `meta.provisioned` of the stored
dashboard tells the refusal apart from any other 400.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx2

from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import http_client
from devops_cli.models.grafana import DashboardSyncOutcome, GrafanaDashboardDetail


@dataclass(frozen=True)
class DashboardSyncResult:
    """What the sync did with one dashboard file, and why it failed when it did."""

    outcome: DashboardSyncOutcome
    title: str
    file: str
    error: str | None = None


class GrafanaClient:
    """A client of one Grafana server, open for the length of a `with` block."""

    def __init__(self, base_url: str, headers: dict[str, str], level: EgressLevel) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = headers
        self._level = level
        self._http: httpx2.Client | None = None

    def __enter__(self) -> Self:
        self._http = http_client(self._level)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._http is not None:
            self._http.close()
            self._http = None

    def list_dashboards(self) -> list[dict[str, Any]]:
        """Return every dashboard (`dash-db`) the server holds."""
        return list(self._get("/api/search", {"type": "dash-db"}))

    def search(self, query: str = "") -> list[dict[str, Any]]:
        """Return the dashboards and folders that match `query`; an empty query matches all."""
        return list(self._get("/api/search", {"query": query} if query else None))

    def dashboard(self, uid: str) -> Any:
        """Return the stored dashboard `uid`, with its metadata."""
        return self._get(f"/api/dashboards/uid/{quote(uid, safe='')}")

    def import_dashboard(self, dashboard: Any, folder_id: int) -> dict[str, Any]:
        """Save `dashboard` into a folder, replacing one with the same title, and return the answer."""
        response = self._send(
            "POST",
            "/api/dashboards/db",
            body={"dashboard": dashboard, "folderId": folder_id, "overwrite": True},
        )
        return dict(response.json())

    def datasources(self) -> list[dict[str, Any]]:
        """Return the configured datasources."""
        return list(self._get("/api/datasources"))

    def alert_rules(self) -> list[dict[str, Any]]:
        """Return the alert rules of unified alerting (Grafana 9 and later)."""
        return list(self._get("/api/v1/provisioning/alert-rules"))

    def is_provisioned(self, uid: str) -> bool:
        """Report whether Grafana holds the dashboard `uid` as provisioned.

        Read from `meta.provisioned`, not from the wording of a refusal. A failed lookup counts as
        not provisioned, so the refused save is reported as the failure it was.
        """
        if not uid:
            return False
        try:
            return GrafanaDashboardDetail.model_validate(self.dashboard(uid)).meta.provisioned
        except httpx2.HTTPError, ValueError:
            return False

    def sync_dashboard(self, dash_file: Path) -> DashboardSyncResult:
        """Save one dashboard file; report a failure without raising.

        Grafana refusing a provisioned dashboard is a skip. A file that cannot be read, a body that
        is not a dashboard, and a failed request are failures. A refused address
        (`SSRFBlockedError`) is raised: it applies to each file, so the caller stops the run.
        """
        title = dash_file.stem
        try:
            raw = json.loads(dash_file.read_text(encoding="utf-8"))
            dashboard = raw.get("dashboard", raw) if isinstance(raw, dict) else None
            if not isinstance(dashboard, dict):
                raise ValueError("The file does not hold a dashboard object")
            title = dashboard.get("title", dash_file.stem)
            try:
                self._send(
                    "POST", "/api/dashboards/db", body={"dashboard": dashboard, "overwrite": True}
                )
            except httpx2.HTTPStatusError as exc:
                uid = str(dashboard.get("uid") or "")
                if exc.response.status_code != HTTPStatus.BAD_REQUEST or not self.is_provisioned(
                    uid
                ):
                    raise
                return DashboardSyncResult(DashboardSyncOutcome.SKIPPED, title, dash_file.name)
        except SSRFBlockedError:
            raise
        except (OSError, ValueError, httpx2.HTTPError, httpx2.InvalidURL) as exc:
            return DashboardSyncResult(
                DashboardSyncOutcome.FAILED, title, dash_file.name, error=str(exc)
            )
        return DashboardSyncResult(DashboardSyncOutcome.SYNCED, title, dash_file.name)

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        return self._send("GET", path, params=params).json()

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: Any = None,
    ) -> httpx2.Response:
        """Send one request with the headers of the client; raise on a failed status."""
        if self._http is None:
            raise RuntimeError("GrafanaClient is used outside its `with` block")
        response = self._http.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers,
            params=params,
            json=body,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response
