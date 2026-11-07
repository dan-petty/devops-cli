"""The answers that api.osv.dev gave on 2026-11-07 for the three packages of the recorded
repository, `tests/fixtures/research/advisories/repo`, and the osv-scanner 2.6.0 run on its lock."""

from __future__ import annotations

import json

from devops_cli.security.vulnerability_lookup import OSVClient
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.http import WebFake
from tests.support.paths import FIXTURES

RECORDED = FIXTURES / "research" / "advisories"
RECORDED_REPO = RECORDED / "repo"
RECORD_URL = "https://api.osv.dev/v1/vulns/{}"


def serve_recorded_osv(web: WebFake) -> dict[str, object]:
    """Serve the batch query and each record it names. Return the request that was recorded."""
    recording = json.loads((RECORDED / "osv" / "querybatch.json").read_text(encoding="utf-8"))
    web.respond("POST", OSVClient.BATCH_URL, 200, recording["response"])
    for path in (RECORDED / "osv" / "vulns").glob("*.json"):
        web.respond("GET", RECORD_URL.format(path.stem), 200, json.loads(path.read_text("utf-8")))
    request: dict[str, object] = recording["request"]
    return request


def serve_recorded_osv_on_github(api: GitHubApiFake) -> None:
    """Serve the same answers on the GitHub API fake, for a test that needs GitHub's API and OSV
    through one transport: `web` and `github_api` cannot both be installed."""
    recording = json.loads((RECORDED / "osv" / "querybatch.json").read_text(encoding="utf-8"))
    api.route("POST", OSVClient.BATCH_URL, github_json(recording["response"]))
    for path in (RECORDED / "osv" / "vulns").glob("*.json"):
        record = json.loads(path.read_text("utf-8"))
        api.route("GET", RECORD_URL.format(path.stem), github_json(record))
