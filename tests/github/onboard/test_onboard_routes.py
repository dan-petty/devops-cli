"""The routes of `devops repos onboard`: each write has one route, and no route writes a setting
of another owner (#6773, ADR 0035)."""

from __future__ import annotations

import re
from urllib.parse import unquote

import pytest

from devops_cli.config.settings import load_settings
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.github.onboard.model import OnboardOptions
from devops_cli.github.onboard.routes import ROUTES, RouteOwner, RouteWriter
from devops_cli.github.onboard.run import onboard_repository
from devops_cli.github.repo_ref import RepoRef
from devops_cli.github.session import get_github_session
from tests.support.github_repository import REPO, OnboardHarness

# The writes of the other owners: the organization and transfer checks of OpenTofu, the App
# installations, the labels and comments that the Service writes on items, a direct write of a file
# or of the default branch, which only the template pull request makes, and a repository secret,
# which any branch can read (D2).
_OTHER_OWNERS = {
    "OpenTofu": (r"^/orgs/", r"/transfer$"),
    "App installations": (r"/installations?(/|$)",),
    "the Service": (r"/issues", r"/labels/", r"/comments"),
    "the template": (r"/contents/", r"/git/refs/heads/main$"),
    "a repository secret": (r"/actions/secrets",),
}


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.key)
def test_no_route_writes_a_setting_of_another_owner(route: object) -> None:
    path = getattr(route, "path")
    taken = [
        owner
        for owner, patterns in _OTHER_OWNERS.items()
        if any(re.search(pattern, path) for pattern in patterns)
    ]

    assert taken == []
    assert getattr(route, "owner") in set(RouteOwner)


def test_each_write_of_a_confirmed_run_is_a_route(onboard_github: OnboardHarness) -> None:
    options = OnboardOptions(repo=RepoRef(REPO), confirm=True, workdir=onboard_github.workdir)

    onboard_repository(options, session=get_github_session(), settings=load_settings())

    writes = [
        (request.method, unquote(request.url.path))
        for request in onboard_github.api.sent
        if request.method != "GET"
    ]
    writes += [
        ("PUT", f"/{call.argv[4]}")
        for call in onboard_github.processes.calls
        if call.argv[:4] == ("gh", "api", "-X", "PUT")
    ]
    assert writes
    assert [write for write in writes if not any(route.matches(*write) for route in ROUTES)] == []


def test_the_writer_refuses_a_write_outside_its_route(onboard_github: OnboardHarness) -> None:
    writer = RouteWriter(get_github_session(), confirm=True)

    with pytest.raises(DevOpsCLIError) as outside:
        writer.rest("label", f"/repos/{REPO}/labels/scope%2Fci", {"color": "000000"})
    with pytest.raises(DevOpsCLIError) as unknown:
        writer.rest("contents", f"/repos/{REPO}/contents/README.md", {})

    assert {outside.value.error_code, unknown.value.error_code} == {"ONBOARD_ROUTE_REFUSED"}
    assert onboard_github.api.sent == []
