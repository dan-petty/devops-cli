"""The answers that api.github.com and www.cisa.gov gave on 2026-11-07, and a repository to read.

`github_repo` pins `tj-actions/changed-files` at `v45.0.0` and `v46.0.1`, `actions/checkout` at the
major tag `v4`, and the chart `qdrant` 1.19.1, which `.devops/research-watch.toml` maps to the
repository `qdrant/qdrant`.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2

from devops_cli.research.kev import KevClient
from tests.support.fakes.http import WebFake
from tests.support.paths import FIXTURES

GITHUB = FIXTURES / "research" / "advisories" / "github"
GITHUB_REPO = FIXTURES / "research" / "advisories" / "github_repo"
ACTIONS_URL = "https://api.github.com/advisories"
QDRANT_URL = "https://api.github.com/repos/qdrant/qdrant/security-advisories"


def recorded(name: str) -> Any:
    """The `response` of the recording `name`."""
    return json.loads((GITHUB / name).read_text(encoding="utf-8"))["response"]


def serve_recorded_github(web: WebFake) -> None:
    """Serve the advisories of `tj-actions/changed-files` and of `qdrant/qdrant`, and an empty list
    for any other package or repository."""
    actions = recorded("advisories_actions.json")
    qdrant = recorded("qdrant_security_advisories.json")

    def server(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.host != "api.github.com":
            return None
        if request.url.path == "/advisories":
            named = "tj-actions/changed-files" in request.url.params["affects"]
            return httpx2.Response(200, json=actions if named else [])
        if request.url.path == "/repos/qdrant/qdrant/security-advisories":
            return httpx2.Response(200, json=qdrant)
        return httpx2.Response(200, json=[])

    web.serve(server)


def serve_recorded_kev(web: WebFake) -> None:
    """Serve the KEV list, trimmed to the entries for CVE-2025-30066 and CVE-2026-19868."""
    web.respond("GET", KevClient.URL, 200, recorded("known_exploited_vulnerabilities.json"))
