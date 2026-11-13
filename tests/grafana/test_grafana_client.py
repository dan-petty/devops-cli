"""The Grafana client over the HTTP fake: the reads, the import and the dashboard sync.

`GrafanaClient` builds its httpx2 client through the HTTP entry point, so the `web` fixture answers
each request below it and vets the host at the client's egress level. A test reads the requests
that reached the fake, never a patched client.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx2
import pytest

from devops_cli.exceptions import ServiceRequestError, SSRFBlockedError
from devops_cli.grafana.client import GrafanaClient
from devops_cli.http.egress import EgressLevel
from devops_cli.models.grafana import DashboardSyncOutcome
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake

BASE = "http://grafana.example.com:3000"
HEADERS = {"Authorization": "Bearer glsa-test"}


def _client(base: str = BASE) -> GrafanaClient:
    return GrafanaClient(base, HEADERS, EgressLevel.LOOPBACK)


class StubGrafana:
    """A Grafana that answers each dashboard save by uid and records every request.

    `provisioned` is the `meta.provisioned` a dashboard lookup returns; `None` fails the lookup.
    """

    def __init__(self, post_status: dict[str, int], provisioned: bool | None = False) -> None:
        self.post_status = post_status
        self.provisioned = provisioned
        self.requests: list[tuple[str, str]] = []
        self.saved: list[dict[str, object]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            uid = request.url.path.rsplit("/", 1)[-1]
            self.requests.append(("GET", uid))
            if self.provisioned is None:
                return httpx2.Response(404, json={"message": "Dashboard not found"})
            return httpx2.Response(
                200, json={"dashboard": {"uid": uid}, "meta": {"provisioned": self.provisioned}}
            )
        body = json.loads(request.content)
        self.saved.append(body)
        uid = body["dashboard"]["uid"]
        self.requests.append(("POST", uid))
        status = self.post_status.get(uid, 200)
        return httpx2.Response(status, json={"status": "success" if status == 200 else "error"})


def _dashboard_file(directory: Path, uid: str, title: str | None = None) -> Path:
    path = directory / f"{uid}.json"
    path.write_text(
        json.dumps({"uid": uid, "title": title or f"Dashboard {uid}", "panels": []}),
        encoding="utf-8",
    )
    return path


def test_the_dashboards_are_listed_with_the_type_filter_and_the_token(web: WebFake) -> None:
    """The list is one search for `dash-db`, sent with the headers of the client."""
    found = [{"uid": "a", "title": "A"}]
    web.serve(
        lambda request: (
            httpx2.Response(200, json=found) if request.url.path == "/api/search" else None
        )
    )

    with _client() as grafana:
        listed = grafana.list_dashboards()

    [sent] = web.recorded
    assert (listed, sent.url, sent.headers["authorization"]) == (
        found,
        f"{BASE}/api/search?type=dash-db",
        "Bearer glsa-test",
    )


def test_a_search_sends_its_query_and_an_empty_query_sends_none(web: WebFake) -> None:
    """The `query` parameter is present only when a query is given."""
    web.serve(lambda request: httpx2.Response(200, json=[]))

    with _client() as grafana:
        grafana.search("cluster")
        grafana.search()

    assert [request.url for request in web.sent] == [
        httpx2.URL(f"{BASE}/api/search?query=cluster"),
        httpx2.URL(f"{BASE}/api/search"),
    ]


def test_a_stored_dashboard_is_read_by_its_escaped_uid(web: WebFake) -> None:
    """The uid is one path segment: a slash in it is escaped, not a second segment."""
    web.serve(lambda request: httpx2.Response(200, json={"dashboard": {}, "meta": {}}))

    with _client() as grafana:
        grafana.dashboard("a/b")

    assert web.requested == [f"{BASE}/api/dashboards/uid/a%2Fb"]


def test_an_import_saves_the_dashboard_into_the_folder_and_returns_the_slug(web: WebFake) -> None:
    """The import overwrites a dashboard with the same title in the named folder."""
    web.serve(lambda request: httpx2.Response(200, json={"slug": "imported", "status": "success"}))

    with _client() as grafana:
        saved = grafana.import_dashboard({"title": "T"}, 7)

    [sent] = web.recorded
    assert (saved["slug"], sent.method, sent.url, sent.json) == (
        "imported",
        "POST",
        f"{BASE}/api/dashboards/db",
        {"dashboard": {"title": "T"}, "folderId": 7, "overwrite": True},
    )


def test_the_datasources_and_the_alert_rules_come_from_their_endpoints(web: WebFake) -> None:
    """The datasources and the alert rules are two reads, each from its own path."""
    answers = {"/api/datasources": [{"name": "Prometheus"}], "/api/v1/provisioning/alert-rules": []}
    web.serve(
        lambda request: (
            httpx2.Response(200, json=answers[request.url.path])
            if request.url.path in answers
            else None
        )
    )

    with _client() as grafana:
        read = (grafana.datasources(), grafana.alert_rules())

    assert read == ([{"name": "Prometheus"}], [])


def test_a_failed_status_raises(web: WebFake) -> None:
    """A 403 is a `ServiceRequestError` after one attempt: the caller never takes its body for a
    list, and the line holds the `message` of the reply."""
    web.serve(lambda request: httpx2.Response(403, json={"message": "no"}))

    with pytest.raises(ServiceRequestError) as raised, _client() as grafana:
        grafana.datasources()

    assert (raised.value.status_code, len(web.sent)) == (403, 1)
    assert raised.value.message.startswith("Grafana failed after 1 attempt in 0.0 s: HTTP 403 ")
    assert ": no. " in raised.value.message


def test_a_read_answers_after_a_503(web: WebFake, clock: ClockFake) -> None:
    """Grafana that starts again answers the second attempt of a read (#5532)."""
    answers = iter([httpx2.Response(503)])
    listed = [{"uid": "a", "title": "A", "type": "dash-db"}]
    web.serve(lambda request: next(answers, httpx2.Response(200, json=listed)))

    with _client() as grafana:
        dashboards = grafana.list_dashboards()

    assert (dashboards, len(web.sent), len(clock.waits)) == (listed, 2, 1)


def test_an_import_that_gets_a_503_is_sent_once(web: WebFake, clock: ClockFake) -> None:
    """A POST can have saved the dashboard before it failed, so it is not sent again."""
    web.serve(lambda request: httpx2.Response(503))

    with pytest.raises(ServiceRequestError) as raised, _client() as grafana:
        grafana.import_dashboard({"title": "A"}, 0)

    assert (raised.value.status_code, len(web.sent), clock.waits) == (503, 1, [])


def test_a_client_outside_its_with_block_cannot_send() -> None:
    """The client opens its connection pool in `with`; a call outside it fails at once."""
    with pytest.raises(RuntimeError, match="outside its `with` block"):
        _client().datasources()


def test_a_saved_dashboard_is_synced(web: WebFake, tmp_path: Path) -> None:
    """A 200 on the save is `synced`, with the title read from the file."""
    stub = StubGrafana({})
    web.serve(stub)

    with _client() as grafana:
        result = grafana.sync_dashboard(_dashboard_file(tmp_path, "a", "Alpha"))

    assert (result.outcome, result.title, result.file, result.error, stub.saved) == (
        DashboardSyncOutcome.SYNCED,
        "Alpha",
        "a.json",
        None,
        [{"dashboard": {"uid": "a", "title": "Alpha", "panels": []}, "overwrite": True}],
    )


def test_an_exported_dashboard_file_is_synced_from_its_dashboard_object(
    web: WebFake, tmp_path: Path
) -> None:
    """`dashboards export` writes `{"dashboard": ..., "meta": ...}`: the sync saves the inner
    object and reads the title from it."""
    exported = tmp_path / "exported.json"
    exported.write_text(
        json.dumps({"dashboard": {"uid": "e", "title": "Exported"}, "meta": {"slug": "exported"}}),
        encoding="utf-8",
    )
    stub = StubGrafana({})
    web.serve(stub)

    with _client() as grafana:
        result = grafana.sync_dashboard(exported)

    assert (result.outcome, result.title, stub.saved) == (
        DashboardSyncOutcome.SYNCED,
        "Exported",
        [{"dashboard": {"uid": "e", "title": "Exported"}, "overwrite": True}],
    )


def test_a_file_that_holds_a_list_is_a_failure_that_sends_nothing(
    web: WebFake, tmp_path: Path
) -> None:
    """The top level of a dashboard file is an object; a list is reported, and no request leaves."""
    listed = tmp_path / "list.json"
    listed.write_text(json.dumps([{"uid": "a"}]), encoding="utf-8")

    with _client() as grafana:
        result = grafana.sync_dashboard(listed)

    assert (result.outcome, result.error, web.recorded) == (
        DashboardSyncOutcome.FAILED,
        "The file does not hold a dashboard object",
        [],
    )


def test_a_path_that_cannot_be_read_is_a_failure_that_sends_nothing(
    web: WebFake, tmp_path: Path
) -> None:
    """A directory in place of a file fails the read, and no request leaves."""
    directory = tmp_path / "folder.json"
    directory.mkdir()

    with _client() as grafana:
        result = grafana.sync_dashboard(directory)

    assert (result.outcome, result.error is not None, web.recorded) == (
        DashboardSyncOutcome.FAILED,
        True,
        [],
    )


@pytest.mark.parametrize(
    ("provisioned", "outcome"),
    [
        (True, DashboardSyncOutcome.SKIPPED),
        (False, DashboardSyncOutcome.FAILED),
        (None, DashboardSyncOutcome.FAILED),
    ],
    ids=["provisioned", "not-provisioned", "lookup-fails"],
)
def test_a_refused_save_is_a_skip_only_for_a_provisioned_dashboard(
    provisioned: bool | None, outcome: DashboardSyncOutcome, web: WebFake, tmp_path: Path
) -> None:
    """A 400 on a dashboard that Grafana holds as provisioned is a skip, read from
    `meta.provisioned`. A 400 on any other dashboard, or one whose lookup fails, is a failure."""
    stub = StubGrafana({"b": 400}, provisioned=provisioned)
    web.serve(stub)

    with _client() as grafana:
        result = grafana.sync_dashboard(_dashboard_file(tmp_path, "b"))

    assert (result.outcome, stub.requests) == (outcome, [("POST", "b"), ("GET", "b")])


def test_a_refusal_that_is_not_a_400_is_a_failure_without_a_lookup(
    web: WebFake, tmp_path: Path
) -> None:
    """A 500 is not the refusal of a provisioned dashboard, so Grafana is not asked about it."""
    stub = StubGrafana({"b": 500})
    web.serve(stub)

    with _client() as grafana:
        result = grafana.sync_dashboard(_dashboard_file(tmp_path, "b"))

    assert (result.outcome, "500" in (result.error or ""), stub.requests) == (
        DashboardSyncOutcome.FAILED,
        True,
        [("POST", "b")],
    )


def test_a_file_that_is_not_json_is_a_failure_that_sends_nothing(
    web: WebFake, tmp_path: Path
) -> None:
    """A broken file is reported with its cause, and no request leaves."""
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")

    with _client() as grafana:
        result = grafana.sync_dashboard(broken)

    assert (result.outcome, result.title, result.error is not None, web.recorded) == (
        DashboardSyncOutcome.FAILED,
        "broken",
        True,
        [],
    )


def test_a_dashboard_without_a_uid_is_not_looked_up(web: WebFake, tmp_path: Path) -> None:
    """A refused save of a dashboard with no uid is a failure: there is nothing to look up."""
    path = tmp_path / "nouid.json"
    path.write_text(json.dumps({"title": "No uid", "panels": []}), encoding="utf-8")
    web.serve(lambda request: httpx2.Response(400, json={"status": "error"}))

    with _client() as grafana:
        result = grafana.sync_dashboard(path)

    assert (result.outcome, [request.method for request in web.sent]) == (
        DashboardSyncOutcome.FAILED,
        ["POST"],
    )


def test_a_refused_address_stops_the_sync_instead_of_failing_the_file(
    web: WebFake, tmp_path: Path
) -> None:
    """The refusal applies to each file, so it is raised, and no request is recorded."""
    grafana = _client("http://10.0.0.1:3000")

    with pytest.raises(SSRFBlockedError, match="egress level refuses"), grafana:
        grafana.sync_dashboard(_dashboard_file(tmp_path, "a"))

    assert web.recorded == []
