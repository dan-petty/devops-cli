"""Tests of the Argo CD and Grafana credential sync (#2156).

The sync reaches three edges, and each test fakes them where they leave the process: kubectl
through `process_fake`, the two services over HTTP through `stub_web`, and the keyring through
`mock_keyring`. No test patches a devops-cli name.

A verify tells three outcomes apart: the service accepted the token, the service refused it, or
the check failed. The sync mints a new token only when the service refused the stored one; a
failed check keeps the stored token and reports its cause.
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable, Mapping
from typing import Any

import httpx2
import pytest

from devops_cli.config.settings import Settings
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.k8s import KubernetesError
from devops_cli.k8s.credentials import (
    fetch_argocd_password,
    fetch_grafana_password,
    get_or_mint_argocd_token,
    get_or_mint_grafana_auth,
    mint_argocd_token,
    mint_grafana_token,
    sync_k8s_credentials,
)
from tests.cluster_secret_fakes import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.web_fakes import StubWeb

ARGOCD = "https://argocd.example.com"
GRAFANA = "https://grafana.example.com"
ARGOCD_USERINFO = f"{ARGOCD}/api/v1/session/userinfo"
ARGOCD_SESSION = f"{ARGOCD}/api/v1/session"
GRAFANA_ORG = f"{GRAFANA}/api/org"
GRAFANA_ACCOUNTS = f"{GRAFANA}/api/serviceaccounts"
GRAFANA_SEARCH = f"{GRAFANA_ACCOUNTS}/search?query=devops-cli"
GRAFANA_TOKENS = f"{GRAFANA_ACCOUNTS}/7/tokens"
ARGOCD_SECRET_READ = ("kubectl", "get", "secret", "argocd-initial-admin-secret")
NOT_FOUND = 'Error from server (NotFound): secrets "argocd-initial-admin-secret" not found'
KEPT = "; the stored token stays in the keyring"

pytestmark = pytest.mark.usefixtures("mock_keyring", "public_dns")

Outcomes = dict[str, tuple[str, str | None]]


def _encoded(value: str | bytes) -> str:
    raw = value.encode() if isinstance(value, str) else value
    return base64.b64encode(raw).decode()


def _cluster_secret(process_fake: ProcessFake, data: Mapping[str, str] | None) -> None:
    """Answer the read of argocd-initial-admin-secret with `data`, or with NotFound for None."""
    if data is None:
        answer = ProcessAnswer(returncode=1, stderr=NOT_FOUND)
    else:
        answer = ProcessAnswer(stdout=json.dumps({"data": dict(data)}))
    process_fake.answer(ARGOCD_SECRET_READ, answer)


def _cluster_password(process_fake: ProcessFake, password: str | None) -> None:
    _cluster_secret(process_fake, None if password is None else {"password": _encoded(password)})


def _outcomes(results: Mapping[str, Any]) -> Outcomes:
    """Each credential of a sync result as its (state, cause) pair."""
    return {name: (outcome.state, outcome.cause) for name, outcome in results.items()}


def _requests(stub_web: StubWeb) -> list[tuple[str, str]]:
    return [(request.method, str(request.url)) for request in stub_web.sent]


def _sync() -> Outcomes:
    return _outcomes(sync_k8s_credentials(stack="infra", argocd_url=ARGOCD, grafana_url=GRAFANA))


def _serve_grafana_mint(stub_web: StubWeb, old_tokens: list[dict[str, Any]]) -> None:
    """Serve the devops-cli service account 7, its `old_tokens` and a new token."""
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 201, {"id": 7, "name": "devops-cli"})
    stub_web.respond("GET", GRAFANA_TOKENS, 200, old_tokens)
    for token in old_tokens:
        stub_web.respond("DELETE", f"{GRAFANA_TOKENS}/{token['id']}", 200, {"message": "deleted"})
    stub_web.respond("POST", GRAFANA_TOKENS, 200, {"id": 9, "key": "new-grafana-token"})


GRAFANA_MINT_REQUESTS = [
    ("POST", GRAFANA_ACCOUNTS),
    ("GET", GRAFANA_TOKENS),
    ("POST", GRAFANA_TOKENS),
    ("DELETE", f"{GRAFANA_TOKENS}/3"),
]

FailedCheck = Callable[[StubWeb, str], None]


def _answer_502(stub_web: StubWeb, url: str) -> None:
    stub_web.respond("GET", url, 502, {"message": "bad gateway"})


def _time_out(stub_web: StubWeb, url: str) -> None:
    stub_web.fail(url, httpx2.ReadTimeout("timed out"))


FAILED_CHECKS = pytest.mark.parametrize(
    ("failed_check", "cause"),
    [
        (_answer_502, "failed with HTTP 502"),
        (_time_out, "failed: ReadTimeout: timed out"),
    ],
    ids=["502", "timeout"],
)


# --- Grafana: the check, and the mint that only a refusal starts ---------------------------------


@FAILED_CHECKS
def test_a_failed_grafana_check_keeps_the_stored_token_and_sends_no_revoke_or_create(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    failed_check: FailedCheck,
    cause: str,
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})
    failed_check(stub_web, GRAFANA_ORG)
    _serve_grafana_mint(stub_web, [{"id": 3}])

    outcomes = _sync()

    assert (outcomes["grafana_token"], _requests(stub_web), mock_keyring.values) == (
        ("failed", f"The Grafana token check at {GRAFANA_ORG} {cause}{KEPT}"),
        [("GET", GRAFANA_ORG)],
        {"grafana_token": "stored-token", "grafana_password": "admin-pw"},
    )


@pytest.mark.parametrize("status", [401, 403])
def test_a_refused_grafana_token_is_replaced_by_a_new_one(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring, status: int
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})
    stub_web.respond("GET", GRAFANA_ORG, status, {"message": "Invalid API key"})
    _serve_grafana_mint(stub_web, [{"id": 3}])

    outcomes = _sync()

    assert (
        outcomes["grafana_token"],
        _requests(stub_web),
        stub_web.sent[0].headers["authorization"],
        stub_web.sent[1].headers["authorization"],
        mock_keyring.values["grafana_token"],
    ) == (
        ("synced", None),
        [("GET", GRAFANA_ORG), *GRAFANA_MINT_REQUESTS],
        "Bearer stored-token",
        f"Basic {_encoded('admin:admin-pw')}",
        "new-grafana-token",
    )


def test_an_accepted_grafana_token_is_kept(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})
    stub_web.respond("GET", GRAFANA_ORG, 200, {"id": 1, "name": "Main Org."})
    _serve_grafana_mint(stub_web, [{"id": 3}])

    outcomes = _sync()

    assert (outcomes, _requests(stub_web), mock_keyring.values["grafana_token"]) == (
        {
            "argocd": ("missing", None),
            "grafana": ("synced", None),
            "grafana_token": ("synced", None),
        },
        [("GET", GRAFANA_ORG)],
        "stored-token",
    )


def test_a_refused_grafana_token_with_no_admin_password_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_token"] = "stored-token"
    stub_web.respond("GET", GRAFANA_ORG, 401, {"message": "Invalid API key"})

    outcomes = _sync()

    assert (outcomes["grafana_token"], _requests(stub_web)) == (
        (
            "failed",
            "Grafana refused the stored token, and no admin password is available to mint a "
            "new one",
        ),
        [("GET", GRAFANA_ORG)],
    )


# --- Argo CD: the check, and the mint that only a refusal starts ---------------------------------


@FAILED_CHECKS
def test_a_failed_argocd_check_keeps_the_stored_token_and_opens_no_session(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    failed_check: FailedCheck,
    cause: str,
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.values["argocd_token"] = "stored-token"
    failed_check(stub_web, ARGOCD_USERINFO)
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": "new-argocd-token"})

    outcomes = _sync()

    assert (outcomes["argocd_token"], _requests(stub_web), mock_keyring.values["argocd_token"]) == (
        ("failed", f"The Argo CD token check at {ARGOCD_USERINFO} {cause}{KEPT}"),
        [("GET", ARGOCD_USERINFO)],
        "stored-token",
    )


@pytest.mark.parametrize(
    ("status", "body"),
    [(401, {"error": "unauthorized"}), (403, None), (200, {"loggedIn": False})],
    ids=["401", "403", "logged-out"],
)
def test_a_refused_argocd_token_is_replaced_by_a_new_one(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    status: int,
    body: object,
) -> None:
    """Argo CD answers its userinfo with HTTP 200 and `loggedIn: false` for a token it refuses."""
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.values["argocd_token"] = "stored-token"
    stub_web.respond("GET", ARGOCD_USERINFO, status, body)
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": "new-argocd-token"})

    outcomes = _sync()

    assert (
        outcomes["argocd_token"],
        _requests(stub_web),
        json.loads(stub_web.sent[1].content),
        mock_keyring.values["argocd_token"],
    ) == (
        ("synced", None),
        [("GET", ARGOCD_USERINFO), ("POST", ARGOCD_SESSION)],
        {"username": "admin", "password": "argo-admin-pw"},
        "new-argocd-token",
    )


def test_an_accepted_argocd_token_is_kept(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.values["argocd_token"] = "stored-token"
    stub_web.respond("GET", ARGOCD_USERINFO, 200, {"loggedIn": True, "username": "admin"})
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": "new-argocd-token"})

    outcomes = _sync()

    assert (outcomes, _requests(stub_web), mock_keyring.values) == (
        {
            "argocd": ("synced", None),
            "argocd_token": ("synced", None),
            "grafana": ("missing", None),
        },
        [("GET", ARGOCD_USERINFO)],
        {"argocd_token": "stored-token", "argocd_password": "argo-admin-pw"},
    )


def test_an_argocd_check_answer_that_is_not_json_is_a_failed_check(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.values["argocd_token"] = "stored-token"
    stub_web.page(ARGOCD_USERINFO, "<html>sign in</html>")

    outcomes = _sync()

    assert (outcomes["argocd_token"], _requests(stub_web)) == (
        ("failed", f"Argo CD sent an answer at {ARGOCD_USERINFO} that is not a JSON object{KEPT}"),
        [("GET", ARGOCD_USERINFO)],
    )


# --- Failures of the mint, the account lookup, the revoke and the secret read --------------------


def test_a_refused_admin_session_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "wrong-pw")
    stub_web.respond("POST", ARGOCD_SESSION, 401, {"error": "Invalid username or password"})

    outcomes = _sync()

    assert (outcomes["argocd_token"], "argocd_token" in mock_keyring.values) == (
        ("failed", f"Argo CD refused the admin session at {ARGOCD_SESSION} with HTTP 401"),
        False,
    )


def test_an_admin_session_with_no_token_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": ""})

    assert _sync()["argocd_token"] == (
        "failed",
        f"Argo CD opened the admin session at {ARGOCD_SESSION} but sent no token",
    )


def test_a_lost_connection_during_the_mint_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    stub_web.fail(ARGOCD_SESSION, httpx2.ConnectError("connection refused"))

    assert _sync()["argocd_token"] == (
        "failed",
        f"The Argo CD token mint at {ARGOCD_SESSION} failed: ConnectError: connection refused",
    )


def _account_not_created(stub_web: StubWeb) -> None:
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 500, {"message": "internal error"})


def _account_not_found(stub_web: StubWeb) -> None:
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 400, {"message": "service account already exists"})
    stub_web.respond("GET", GRAFANA_SEARCH, 200, {"serviceAccounts": [{"id": 2, "name": "other"}]})


def _search_refused(stub_web: StubWeb) -> None:
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 409, {"message": "service account already exists"})
    stub_web.respond("GET", GRAFANA_SEARCH, 403, {"message": "forbidden"})


def _account_with_no_id(stub_web: StubWeb) -> None:
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 201, {"name": "devops-cli"})


@pytest.mark.parametrize(
    ("lookup", "cause"),
    [
        (
            _account_not_created,
            "Grafana refused to create the devops-cli service account with HTTP 500",
        ),
        (
            _account_not_found,
            "Grafana has a devops-cli service account, but the search did not find it",
        ),
        (
            _search_refused,
            "Grafana refused the search for the devops-cli service account with HTTP 403",
        ),
        (
            _account_with_no_id,
            "Grafana created the devops-cli service account but sent no account ID",
        ),
    ],
    ids=["create-refused", "not-found", "search-refused", "no-id"],
)
def test_a_failed_account_lookup_reports_the_cause_and_creates_no_token(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    lookup: Callable[[StubWeb], None],
    cause: str,
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    lookup(stub_web)

    outcomes = _sync()

    assert (outcomes["grafana_token"], ("POST", GRAFANA_TOKENS) in _requests(stub_web)) == (
        ("failed", cause),
        False,
    )


def test_an_existing_account_found_by_the_search_gets_the_new_token(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [])
    stub_web.respond("POST", GRAFANA_ACCOUNTS, 409, {"message": "service account already exists"})
    stub_web.respond(
        "GET", GRAFANA_SEARCH, 200, {"serviceAccounts": [{"id": 7, "name": "devops-cli"}]}
    )

    outcomes = _sync()

    assert (
        outcomes["grafana_token"],
        _requests(stub_web),
        mock_keyring.values["grafana_token"],
    ) == (
        ("synced", None),
        [
            ("POST", GRAFANA_ACCOUNTS),
            ("GET", GRAFANA_SEARCH),
            ("GET", GRAFANA_TOKENS),
            ("POST", GRAFANA_TOKENS),
        ],
        "new-grafana-token",
    )


def _revoke_refused(stub_web: StubWeb) -> None:
    stub_web.respond("DELETE", f"{GRAFANA_TOKENS}/3", 500, {"message": "internal error"})


def _list_refused(stub_web: StubWeb) -> None:
    stub_web.respond("GET", GRAFANA_TOKENS, 403, {"message": "forbidden"})


def _list_not_an_array(stub_web: StubWeb) -> None:
    stub_web.respond("GET", GRAFANA_TOKENS, 200, {"tokens": []})


def test_a_listed_token_with_no_id_is_not_revoked(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [{"id": 3}])
    stub_web.respond("GET", GRAFANA_TOKENS, 200, [{"name": "no-id"}, {"id": 3}])

    outcomes = _sync()

    assert (outcomes["grafana_token"], _requests(stub_web)) == (
        ("synced", None),
        GRAFANA_MINT_REQUESTS,
    )


def test_a_lost_connection_during_the_grafana_mint_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    stub_web.fail(GRAFANA_ACCOUNTS, httpx2.ReadTimeout("timed out"))

    assert _sync()["grafana_token"] == (
        "failed",
        f"The Grafana token mint at {GRAFANA} failed: ReadTimeout: timed out",
    )


@pytest.mark.parametrize(
    ("list_failure", "cause"),
    [
        (
            _list_refused,
            "Grafana refused to list the tokens of service account 7 with HTTP 403",
        ),
        (
            _list_not_an_array,
            f"Grafana sent an answer at {GRAFANA_TOKENS} that is not a JSON array",
        ),
    ],
    ids=["list-refused", "list-not-an-array"],
)
def test_a_failed_token_list_reports_the_cause_and_changes_nothing(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    list_failure: Callable[[StubWeb], None],
    cause: str,
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [{"id": 3}])
    list_failure(stub_web)

    outcomes = _sync()

    assert (outcomes["grafana_token"], _requests(stub_web), mock_keyring.writes) == (
        ("failed", cause),
        [("POST", GRAFANA_ACCOUNTS), ("GET", GRAFANA_TOKENS)],
        {},
    )


def test_a_failed_create_sends_no_revoke_and_keeps_the_stored_token(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})
    stub_web.respond("GET", GRAFANA_ORG, 401, {"message": "Invalid API key"})
    _serve_grafana_mint(stub_web, [{"id": 3}])
    stub_web.respond("POST", GRAFANA_TOKENS, 500, {"message": "internal error"})

    outcomes = _sync()

    assert (
        outcomes["grafana_token"],
        [request for request in _requests(stub_web) if request[0] == "DELETE"],
        mock_keyring.values["grafana_token"],
    ) == (
        (
            "failed",
            "Grafana refused to create a token for service account 7 with HTTP 500",
        ),
        [],
        "stored-token",
    )


def test_the_mint_creates_stores_then_revokes(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    events: list[str] = []
    mock_keyring.events = events
    stub_web.serve(
        lambda request: events.append(f"{request.method} {request.url.path}")  # type: ignore[func-returns-value]
    )
    _serve_grafana_mint(stub_web, [{"id": 3}])

    outcomes = _sync()

    assert (outcomes["grafana_token"], events[-3:]) == (
        ("synced", None),
        [
            "POST /api/serviceaccounts/7/tokens",
            "keyring-write grafana_token",
            "DELETE /api/serviceaccounts/7/tokens/3",
        ],
    )


def test_a_refused_revoke_keeps_the_new_token_and_logs_the_cause(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [{"id": 3}])
    _revoke_refused(stub_web)

    with caplog.at_level(logging.WARNING, logger="devops_cli.k8s.credentials"):
        outcomes = _sync()

    assert (
        outcomes["grafana_token"],
        mock_keyring.values["grafana_token"],
        [record.getMessage() for record in caplog.records],
    ) == (
        ("synced", None),
        "new-grafana-token",
        [
            "Grafana refused to revoke token 3 of service account 7 with HTTP 500; "
            "the old token stays until a later mint revokes it"
        ],
    )


@pytest.mark.parametrize(
    ("answer", "cause"),
    [
        (
            {"id": 9},
            "Grafana created a token for service account 7 but sent no key",
        ),
        (None, "Grafana refused to create a token for service account 7 with HTTP 500"),
    ],
    ids=["no-key", "refused"],
)
def test_a_failed_token_create_reports_the_cause(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    answer: object,
    cause: str,
) -> None:
    _cluster_password(process_fake, None)
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [])
    stub_web.respond("POST", GRAFANA_TOKENS, 500 if answer is None else 200, answer)

    assert _sync()["grafana_token"] == ("failed", cause)


@pytest.mark.parametrize(
    "raw",
    ["%%not-base64%%", _encoded(b"\xff\xfe")],
    ids=["not-base64", "not-utf-8"],
)
def test_an_undecodable_secret_field_reports_the_cause_and_mints_nothing(
    process_fake: ProcessFake, stub_web: StubWeb, raw: str
) -> None:
    _cluster_secret(process_fake, {"password": raw})

    outcomes = _sync()

    assert (outcomes["argocd"], "argocd_token" in outcomes, stub_web.sent) == (
        (
            "failed",
            "Field password of Secret argocd/argocd-initial-admin-secret is not base64-encoded "
            "UTF-8 text",
        ),
        False,
        [],
    )


def test_a_failed_secret_read_reports_the_kubectl_error(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    forbidden = 'Error from server (Forbidden): secrets "argocd-initial-admin-secret" is forbidden'
    process_fake.answer(ARGOCD_SECRET_READ, ProcessAnswer(returncode=1, stderr=f"{forbidden}\n"))

    assert _sync()["argocd"] == (
        "failed",
        f"kubectl cannot read Secret argocd/argocd-initial-admin-secret: {forbidden}",
    )


@pytest.mark.parametrize("stdout", ["not json", "[]", '{"data": ["password"]}'])
def test_a_secret_read_that_is_not_json_reports_the_cause(
    process_fake: ProcessFake, stdout: str
) -> None:
    process_fake.answer(ARGOCD_SECRET_READ, ProcessAnswer(stdout=stdout))

    assert _sync()["argocd"] == (
        "failed",
        "kubectl sent Secret argocd/argocd-initial-admin-secret as output that is not a JSON "
        "object",
    )


def test_a_locked_keyring_reports_the_cause(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.locked = True

    state, cause = _sync()["argocd"]

    assert (state, (cause or "").startswith("Cannot store argocd_password:"), stub_web.sent) == (
        "failed",
        True,
        [],
    )


def test_an_accepted_token_that_the_keyring_cannot_store_reports_the_cause(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token from the environment is copied into the keyring; a locked keyring refuses it."""
    monkeypatch.setenv("DEVOPS_CLI_ARGOCD_TOKEN", "environment-token")
    _cluster_password(process_fake, None)
    stub_web.respond("GET", ARGOCD_USERINFO, 200, {"loggedIn": True})
    mock_keyring.locked = True

    state, cause = _sync()["argocd_token"]

    assert (state, (cause or "").startswith("Cannot store argocd_token:"), _requests(stub_web)) == (
        "failed",
        True,
        [("GET", ARGOCD_USERINFO)],
    )


def test_a_service_with_no_url_gets_no_token_step(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})

    assert (_outcomes(sync_k8s_credentials(stack="infra")), stub_web.sent) == (
        {"argocd": ("synced", None), "grafana": ("synced", None)},
        [],
    )


def test_no_stored_token_and_no_admin_password_send_no_request(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    _cluster_password(process_fake, None)

    assert (_sync(), stub_web.sent) == (
        {"argocd": ("missing", None), "grafana": ("missing", None)},
        [],
    )


def test_the_service_urls_come_from_the_settings(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    config: Callable[..., Any],
) -> None:
    config(argocd={"url": ARGOCD}, grafana={"url": GRAFANA})
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"argocd_token": "argo-token", "grafana_token": "grafana-token"})
    stub_web.respond("GET", ARGOCD_USERINFO, 200, {"loggedIn": True})
    stub_web.respond("GET", GRAFANA_ORG, 200, {"id": 1})

    outcomes = _outcomes(sync_k8s_credentials(stack="infra"))

    assert (outcomes, _requests(stub_web)) == (
        {
            "argocd": ("missing", None),
            "argocd_token": ("synced", None),
            "grafana": ("missing", None),
            "grafana_token": ("synced", None),
        },
        [("GET", ARGOCD_USERINFO), ("GET", GRAFANA_ORG)],
    )


# --- The mint and the on-demand token of the other commands --------------------------------------


@pytest.mark.usefixtures("mock_keyring")
def test_a_failed_mint_raises_its_cause(stub_web: StubWeb) -> None:
    stub_web.respond("POST", ARGOCD_SESSION, 401, {"error": "Invalid username or password"})

    with pytest.raises(KubernetesError) as caught:
        mint_argocd_token(ARGOCD, "wrong-pw")

    assert str(caught.value) == (
        f"Argo CD refused the admin session at {ARGOCD_SESSION} with HTTP 401"
    )


def test_mint_tokens_refuse_a_url_with_no_scheme(stub_web: StubWeb) -> None:
    with pytest.raises(ConfigurationError) as argocd_error:
        mint_argocd_token("argocd.example.com", "admin-pw")
    with pytest.raises(ConfigurationError) as grafana_error:
        mint_grafana_token("grafana.example.com", "admin-pw")

    assert (
        "argocd.url" in str(argocd_error.value),
        "grafana.url" in str(grafana_error.value),
        stub_web.sent,
    ) == (True, True, [])


def test_mint_tokens_use_a_lowercase_scheme(stub_web: StubWeb, mock_keyring: FakeKeyring) -> None:
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": "new-argocd-token"})
    _serve_grafana_mint(stub_web, [])

    tokens = (
        mint_argocd_token("HTTPS://argocd.example.com", "admin-pw", save_to_keyring=False),
        mint_grafana_token("HTTPS://grafana.example.com/", "admin-pw", save_to_keyring=False),
    )

    assert (tokens, _requests(stub_web), mock_keyring.writes) == (
        ("new-argocd-token", "new-grafana-token"),
        [
            ("POST", ARGOCD_SESSION),
            ("POST", GRAFANA_ACCOUNTS),
            ("GET", GRAFANA_TOKENS),
            ("POST", GRAFANA_TOKENS),
        ],
        {},
    )


def test_get_or_mint_argocd_token_returns_the_stored_token(
    stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    mock_keyring.values.update({"argocd_token": "stored-token", "argocd_password": "admin-pw"})
    settings = Settings()
    settings.argocd.url = ARGOCD

    assert (get_or_mint_argocd_token(settings), stub_web.sent) == ("stored-token", [])


def test_get_or_mint_returns_nothing_with_no_token_and_no_admin_password(
    stub_web: StubWeb,
) -> None:
    settings = Settings()
    settings.argocd.url = ARGOCD
    settings.grafana.url = GRAFANA

    assert (
        get_or_mint_argocd_token(settings),
        get_or_mint_grafana_auth(settings),
        stub_web.sent,
    ) == (None, (None, None), [])


def test_get_or_mint_argocd_token_mints_a_missing_token(
    stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    mock_keyring.values["argocd_password"] = "admin-pw"
    stub_web.respond("POST", ARGOCD_SESSION, 200, {"token": "new-argocd-token"})
    settings = Settings()
    settings.argocd.url = ARGOCD

    assert (get_or_mint_argocd_token(settings), mock_keyring.values["argocd_token"]) == (
        "new-argocd-token",
        "new-argocd-token",
    )


def test_get_or_mint_grafana_auth_prefers_a_stored_then_a_minted_token(
    stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    settings = Settings()
    settings.grafana.url = GRAFANA
    mock_keyring.values["grafana_password"] = "admin-pw"
    _serve_grafana_mint(stub_web, [])

    minted = get_or_mint_grafana_auth(settings)
    stored = get_or_mint_grafana_auth(settings)

    assert (minted, stored, len(stub_web.sent)) == (
        ("new-grafana-token", None),
        ("new-grafana-token", None),
        3,
    )


def test_get_or_mint_grafana_auth_falls_back_to_basic_auth_and_logs_the_cause(
    stub_web: StubWeb, mock_keyring: FakeKeyring, caplog: pytest.LogCaptureFixture
) -> None:
    settings = Settings()
    settings.grafana.url = GRAFANA
    mock_keyring.values["grafana_password"] = "admin-pw"
    _account_not_created(stub_web)

    with caplog.at_level(logging.WARNING, logger="devops_cli.k8s.credentials"):
        auth = get_or_mint_grafana_auth(settings)

    assert (auth, [record.getMessage() for record in caplog.records]) == (
        (None, f"Basic {_encoded('admin:admin-pw')}"),
        [
            "The Grafana token mint failed, so the requests use the admin password: Grafana "
            "refused to create the devops-cli service account with HTTP 500"
        ],
    )


# --- The admin passwords in the cluster ----------------------------------------------------------


def test_fetch_argocd_password_stores_the_cluster_password(
    process_fake: ProcessFake, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, "argo-admin-pw")

    password = fetch_argocd_password(namespace="argocd", context="example-cluster")

    assert (password, mock_keyring.values, process_fake.calls[0].argv) == (
        "argo-admin-pw",
        {"argocd_password": "argo-admin-pw"},
        (*ARGOCD_SECRET_READ, "-n", "argocd", "-o=json", "--context", "example-cluster"),
    )


def test_fetch_argocd_password_returns_none_when_the_secret_is_gone(
    process_fake: ProcessFake, mock_keyring: FakeKeyring
) -> None:
    _cluster_password(process_fake, None)

    assert (fetch_argocd_password(), mock_keyring.values) == (None, {})


def test_fetch_grafana_password_reads_only_the_grafana_secrets(
    process_fake: ProcessFake, mock_keyring: FakeKeyring
) -> None:
    process_fake.answer(
        ("kubectl", "get", "secret"), ProcessAnswer(returncode=1, stderr="Error (NotFound)")
    )
    process_fake.answer(
        ("kubectl", "get", "secret", "grafana-admin-credentials"),
        ProcessAnswer(stdout=json.dumps({"data": {"admin-password": _encoded("grafana-pw")}})),
    )

    password = fetch_grafana_password(namespaces=["monitoring"])

    assert (
        password,
        [call.argv[3] for call in process_fake.calls],
        mock_keyring.values,
    ) == (
        "grafana-pw",
        ["grafana", "grafana-admin-credentials"],
        {"grafana_password": "grafana-pw"},
    )


def test_fetch_grafana_password_returns_none_when_no_secret_holds_one(
    process_fake: ProcessFake, mock_keyring: FakeKeyring
) -> None:
    process_fake.answer(
        ("kubectl", "get", "secret"), ProcessAnswer(stdout=json.dumps({"data": {}}))
    )

    assert (fetch_grafana_password(namespaces=["monitoring"]), mock_keyring.values) == (None, {})


# --- The command ---------------------------------------------------------------------------------


@pytest.mark.usefixtures("process_fake")
def test_sync_secrets_dry_run_makes_no_request(
    cli: Callable[..., Any], stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    result = cli("k8s", "sync-secrets", "--dry-run")

    assert (result.exit_code, "sync_stack_secrets" in result.output, stub_web.sent) == (
        0,
        True,
        [],
    )


def test_sync_secrets_shows_each_failure_with_its_cause_and_exits_1(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
) -> None:
    config(argocd={"url": ARGOCD}, grafana={"url": GRAFANA})
    _cluster_password(process_fake, None)
    mock_keyring.values.update({"grafana_token": "stored-token", "grafana_password": "admin-pw"})
    _answer_502(stub_web, GRAFANA_ORG)

    result = cli("k8s", "sync-secrets")

    assert (
        result.exit_code,
        "Grafana credentials securely stored in OS Keyring." in result.output,
        "Argocd secret not found in active cluster." in result.output,
        f"Grafana Token: The Grafana token check at {GRAFANA_ORG} failed with HTTP 502{KEPT}"
        in result.output,
    ) == (1, True, True, True), result.output


def test_sync_secrets_names_the_keyring_entry_and_the_commands_for_a_missing_grafana_password(
    cli: Callable[..., Any],
    config: Callable[..., Any],
    process_fake: ProcessFake,
    stub_web: StubWeb,
) -> None:
    config(argocd={"url": ARGOCD}, grafana={"url": GRAFANA})
    _cluster_password(process_fake, "argocd-pw")

    result = cli("k8s", "sync-secrets")
    output = " ".join(result.output.split())

    assert (
        "The Grafana admin password is not in the keyring (grafana_password). Store it with "
        "'devops config set grafana.password', or adopt it from the cluster with "
        "'devops k8s push-secrets'." in output,
        "Grafana secret not found in active cluster" in output,
    ) == (True, False), result.output
