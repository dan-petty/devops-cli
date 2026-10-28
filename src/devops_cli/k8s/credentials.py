"""Kubernetes stack credential discovery and OS keyring synchronization.

`sync_k8s_credentials` copies the Argo CD admin password from the cluster into the keyring, and
keeps an API token for Argo CD and for Grafana. It keeps a stored token that the service accepts,
and mints a new token only when the service refuses the stored one. When the check fails, with
another HTTP status or a request error, the sync keeps the stored token. Every failure reaches
the sync result with its cause (#2156).

Each request dials through the egress factory at the level of its caller. The callers that read
the settings give the configured level: loopback, or private with `ai.allow_private_network`. An
address that the level refuses fails the step with its cause, as a request error does.
"""

from __future__ import annotations

import base64
import binascii
import itertools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import (
    CONST_GRAFANA_ACCOUNT_EXISTS_HTTP_STATUSES,
    CONST_GRAFANA_SERVICE_ACCOUNT_NAME,
    CONST_STACK_TOKEN_REFUSED_HTTP_STATUSES,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_BOOTSTRAP_STACK,
    DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import (
    SecretStorageError,
    _keyring_get,
    _keyring_set,
    get_argocd_password,
    get_argocd_token,
    get_grafana_password,
    get_grafana_token,
    load_settings,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import SSRFBlockedError
from devops_cli.exceptions.k8s import StackCredentialError
from devops_cli.http.egress import EgressLevel, configured_level
from devops_cli.http.urls import service_base_url
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span

if TYPE_CHECKING:
    import subprocess

    import httpx2

    from devops_cli.config.settings import Settings

logger = logging.getLogger(__name__)

_ARGOCD_LABEL = "Argo CD"
_GRAFANA_LABEL = "Grafana"


class SyncState(StrEnum):
    """What a sync did with one credential."""

    SYNCED = "synced"
    MISSING = "missing"
    FAILED = "failed"


@dataclass(frozen=True)
class CredentialSync:
    """The outcome of one credential in a sync; a failed one carries its cause."""

    state: SyncState
    cause: str | None = None


_SYNCED = CredentialSync(SyncState.SYNCED)
_MISSING = CredentialSync(SyncState.MISSING)


def _store_secret(key: str, value: str, metric_service: str) -> None:
    """Store a secret in the OS keyring and count it; raise StackCredentialError when it fails."""
    try:
        _keyring_set(key, value)
    except SecretStorageError as exc:
        raise StackCredentialError(str(exc)) from exc
    GLOBAL_METRICS.increment_counter(
        "k8s_credentials_synced_total", labels={"service": metric_service}
    )


def _request_failure(exc: Exception) -> str:
    """Name a request error with its message, as `ReadTimeout: timed out`."""
    detail = str(exc)
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


def _read_json[Body](resp: httpx2.Response, kind: type[Body], service: str) -> Body:
    """Return the JSON body of `resp` when it is a `kind`; raise StackCredentialError if not."""
    noun = "object" if kind is dict else "array"
    failure = f"{service} sent an answer at {resp.request.url} that is not a JSON {noun}"
    try:
        body = resp.json()
    except ValueError as exc:
        raise StackCredentialError(failure) from exc
    if not isinstance(body, kind):
        raise StackCredentialError(failure)
    return body


def _secret_read_failure(res: subprocess.CompletedProcess[str], namespace: str, ref: str) -> None:
    """Return when kubectl did not find the Secret; raise StackCredentialError for another failure.

    The debug line names the namespace only, as the code before #2156 did: the error that a person
    reads names the whole Secret."""
    stderr = (res.stderr or "").strip()
    if "NotFound" in stderr or "not found" in stderr.lower():
        logger.debug("Kubernetes Secret not found in namespace %s", namespace)
        return
    detail = stderr.splitlines()[0] if stderr else f"kubectl exited with code {res.returncode}"
    raise StackCredentialError(f"kubectl cannot read Secret {ref}: {detail}")


def _secret_data(stdout: str, ref: str) -> dict[str, Any]:
    """Return the `data` map of a Secret that kubectl printed as JSON."""
    failure = f"kubectl sent Secret {ref} as output that is not a JSON object"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise StackCredentialError(failure) from exc
    if not isinstance(payload, dict):
        raise StackCredentialError(failure)
    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise StackCredentialError(failure)
    return data


def _decode_secret_field(raw_b64: str, field: str, ref: str) -> str:
    """Decode one base64 field of a Secret into text."""
    try:
        return base64.b64decode(raw_b64.strip(), validate=True).decode("utf-8").strip()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise StackCredentialError(
            f"Field {field} of Secret {ref} is not base64-encoded UTF-8 text"
        ) from exc


def fetch_secret_data(
    secret_name: str,
    namespace: str,
    context: str | None = None,
) -> dict[str, str]:
    """Fetch and decode all data fields from a Kubernetes Secret in a single call.

    Return an empty dict when the Secret does not exist. Raise StackCredentialError when kubectl
    fails for another reason, or when its output or a field cannot be decoded.
    """
    from devops_cli.core.validation import validate_k8s_name

    validate_k8s_name(secret_name, "secret_name")
    validate_k8s_name(namespace, "namespace", namespace=True)
    if context:
        validate_k8s_name(context, "context")

    cmd = [
        "kubectl",
        "get",
        "secret",
        secret_name,
        "-n",
        namespace,
        "-o=json",
    ]
    if context:
        cmd.extend(["--context", context])

    ref = f"{namespace}/{secret_name}"
    res = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    if res.returncode != 0:
        _secret_read_failure(res, namespace, ref)
        return {}
    return {
        field: _decode_secret_field(raw, field, ref)
        for field, raw in _secret_data(res.stdout, ref).items()
        if isinstance(raw, str)
    }


def fetch_secret_field(
    secret_name: str,
    field: str,
    namespace: str,
    context: str | None = None,
) -> str | None:
    """Fetch and decode a specific field from a Kubernetes Secret."""
    data = fetch_secret_data(secret_name, namespace, context=context)
    val = data.get(field)
    return val if val else None


@trace_span("k8s.credentials.argocd")
def fetch_argocd_password(
    namespace: str = DEFAULT_ARGOCD_NAMESPACE,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch initial ArgoCD admin password from Kubernetes and store in keyring."""
    pw = fetch_secret_field(
        secret_name="argocd-initial-admin-secret",
        field="password",
        namespace=namespace,
        context=context,
    )
    if pw and save_to_keyring:
        _store_secret("argocd_password", pw, "argocd")
    return pw


def _find_grafana_field_in_secret(
    secret_name: str,
    namespace: str,
    candidate_fields: list[str],
    context: str | None,
) -> str | None:
    data = fetch_secret_data(secret_name, namespace, context=context)
    for field in candidate_fields:
        pw = data.get(field)
        if pw:
            return pw
    return None


@trace_span("k8s.credentials.grafana")
def fetch_grafana_password(
    namespaces: list[str] | None = None,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch Grafana admin password from Kubernetes and store in keyring."""
    candidate_namespaces = namespaces or ["monitoring", "grafana", "default"]
    candidate_secrets = ["grafana", "grafana-admin-credentials"]
    candidate_fields = ["admin-password", "admin_password", "password"]

    for ns, secret_name in itertools.product(candidate_namespaces, candidate_secrets):
        pw = _find_grafana_field_in_secret(secret_name, ns, candidate_fields, context)
        if not pw:
            continue
        if save_to_keyring:
            _store_secret("grafana_password", pw, "grafana")
        return pw
    return None


@trace_span("k8s.credentials.argocd.token")
def mint_argocd_token(
    base_url: str,
    password: str,
    *,
    level: EgressLevel,
    save_to_keyring: bool = True,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> str:
    """Open an Argo CD admin session with the admin password, and return its token.

    The request dials at `level`. Raise StackCredentialError with the cause when Argo CD refuses
    the session or sends no token, when the request fails or `level` refuses the address, or
    when the keyring cannot store the token.
    """
    import httpx2

    from devops_cli.http.client import new_http_client

    clean_base = service_base_url(base_url, "argocd.url")
    url = f"{clean_base}/api/v1/session"
    try:
        with new_http_client(level=level, timeout=httpx2.Timeout(timeout)) as client:
            resp = client.post(url, json={"username": "admin", "password": password})
    except (httpx2.RequestError, SSRFBlockedError) as exc:
        raise StackCredentialError(
            f"The {_ARGOCD_LABEL} token mint at {url} failed: {_request_failure(exc)}"
        ) from exc
    if not resp.is_success:
        raise StackCredentialError(
            f"{_ARGOCD_LABEL} refused the admin session at {url} with HTTP {resp.status_code}"
        )
    token = _read_json(resp, dict, _ARGOCD_LABEL).get("token")
    if not isinstance(token, str) or not token:
        raise StackCredentialError(
            f"{_ARGOCD_LABEL} opened the admin session at {url} but sent no token"
        )
    if save_to_keyring:
        _store_secret("argocd_token", token, "argocd_token")
    return token


def _search_grafana_sa(client: httpx2.Client, accounts_url: str) -> int:
    """Find the ID of the devops-cli service account with the search of Grafana."""
    name = CONST_GRAFANA_SERVICE_ACCOUNT_NAME
    resp = client.get(f"{accounts_url}/search", params={"query": name})
    if not resp.is_success:
        raise StackCredentialError(
            f"Grafana refused the search for the {name} service account with HTTP "
            f"{resp.status_code}"
        )
    accounts = _read_json(resp, dict, _GRAFANA_LABEL).get("serviceAccounts")
    for account in accounts if isinstance(accounts, list) else []:
        if isinstance(account, dict) and account.get("name") == name:
            account_id = account.get("id")
            if isinstance(account_id, int):
                return account_id
    raise StackCredentialError(
        f"Grafana has a {name} service account, but the search did not find it"
    )


def _find_or_create_grafana_sa(client: httpx2.Client, base_url: str) -> int:
    """Create the devops-cli service account of Grafana, or find it when it exists."""
    name = CONST_GRAFANA_SERVICE_ACCOUNT_NAME
    accounts_url = f"{base_url}/api/serviceaccounts"
    resp = client.post(accounts_url, json={"name": name, "role": "Admin"})
    if resp.status_code in CONST_GRAFANA_ACCOUNT_EXISTS_HTTP_STATUSES:
        return _search_grafana_sa(client, accounts_url)
    if not resp.is_success:
        raise StackCredentialError(
            f"Grafana refused to create the {name} service account with HTTP {resp.status_code}"
        )
    account_id = _read_json(resp, dict, _GRAFANA_LABEL).get("id")
    if not isinstance(account_id, int):
        raise StackCredentialError(
            f"Grafana created the {name} service account but sent no account ID"
        )
    return account_id


def _list_grafana_sa_token_ids(client: httpx2.Client, base_url: str, account_id: int) -> list[Any]:
    """Return the IDs of the tokens that the devops-cli service account holds now."""
    resp = client.get(f"{base_url}/api/serviceaccounts/{account_id}/tokens")
    if not resp.is_success:
        raise StackCredentialError(
            f"Grafana refused to list the tokens of service account {account_id} with HTTP "
            f"{resp.status_code}"
        )
    tokens = _read_json(resp, list, _GRAFANA_LABEL)
    ids = [token.get("id") if isinstance(token, dict) else None for token in tokens]
    return [token_id for token_id in ids if token_id is not None]


def _revoke_grafana_sa_tokens(
    client: httpx2.Client, base_url: str, account_id: int, token_ids: list[Any]
) -> None:
    """Revoke the tokens `token_ids` of the service account, so that tokens do not accumulate."""
    tokens_url = f"{base_url}/api/serviceaccounts/{account_id}/tokens"
    for token_id in token_ids:
        revoked = client.delete(f"{tokens_url}/{token_id}")
        if not revoked.is_success:
            raise StackCredentialError(
                f"Grafana refused to revoke token {token_id} of service account {account_id} "
                f"with HTTP {revoked.status_code}"
            )


def _create_grafana_sa_token(client: httpx2.Client, base_url: str, account_id: int) -> str:
    """Create a token for the service account and return its key."""
    import time

    tokens_url = f"{base_url}/api/serviceaccounts/{account_id}/tokens"
    token_name = f"{CONST_GRAFANA_SERVICE_ACCOUNT_NAME}-{int(time.time())}"
    resp = client.post(tokens_url, json={"name": token_name})
    if not resp.is_success:
        raise StackCredentialError(
            f"Grafana refused to create a token for service account {account_id} with HTTP "
            f"{resp.status_code}"
        )
    key = _read_json(resp, dict, _GRAFANA_LABEL).get("key")
    if not isinstance(key, str) or not key:
        raise StackCredentialError(
            f"Grafana created a token for service account {account_id} but sent no key"
        )
    return key


@trace_span("k8s.credentials.grafana.token")
def mint_grafana_token(
    base_url: str,
    password: str,
    *,
    level: EgressLevel,
    save_to_keyring: bool = True,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> str:
    """Mint a token for the devops-cli service account of Grafana with the admin password.

    The account keeps one token: the mint lists the older tokens, creates the new token, stores
    it, and only then revokes the older tokens. A failed create or store revokes nothing. A
    refused revoke logs its cause and keeps the new token, and the next mint revokes the old one.
    The requests dial at `level`. Raise StackCredentialError with the cause when a step before
    the revoke fails or `level` refuses the address, or when the keyring cannot store the token.
    """
    import httpx2

    from devops_cli.http.client import new_http_client

    clean_base = service_base_url(base_url, "grafana.url")
    try:
        with new_http_client(level=level, timeout=httpx2.Timeout(timeout)) as client:
            client.auth = httpx2.BasicAuth("admin", password)
            account_id = _find_or_create_grafana_sa(client, clean_base)
            old_token_ids = _list_grafana_sa_token_ids(client, clean_base, account_id)
            token = _create_grafana_sa_token(client, clean_base, account_id)
            if save_to_keyring:
                _store_secret("grafana_token", token, "grafana_token")
            try:
                _revoke_grafana_sa_tokens(client, clean_base, account_id, old_token_ids)
            except StackCredentialError as exc:
                logger.warning("%s; the old token stays until a later mint revokes it", exc)
    except (httpx2.RequestError, SSRFBlockedError) as exc:
        raise StackCredentialError(
            f"The {_GRAFANA_LABEL} token mint at {clean_base} failed: {_request_failure(exc)}"
        ) from exc
    return token


def get_or_mint_argocd_token(settings: Any) -> str | None:
    """Resolve the Argo CD token, and mint one with the admin password when it is missing.

    A failed mint raises StackCredentialError with its cause.
    """
    token = get_argocd_token(settings)
    if token:
        return token

    pw = get_argocd_password(settings)
    argo_url = getattr(getattr(settings, "argocd", None), "url", None)
    if pw and argo_url:
        return mint_argocd_token(
            argo_url,
            pw,
            level=configured_level(settings.ai),
            save_to_keyring=True,
        )
    return None


def get_or_mint_grafana_auth(settings: Any) -> tuple[str | None, str | None]:
    """Resolve Grafana authentication, returning (bearer_token, basic_auth_header).

    When the mint of a token fails, the requests use the admin password, and a warning gives the
    cause.
    """
    token = get_grafana_token(settings)
    if token:
        return token, None

    pw = get_grafana_password(settings)
    if not pw:
        return None, None

    graf_url = getattr(getattr(settings, "grafana", None), "url", None)
    if graf_url:
        try:
            minted = mint_grafana_token(
                graf_url,
                pw,
                level=configured_level(settings.ai),
                save_to_keyring=True,
            )
        except StackCredentialError as exc:
            logger.warning(
                "The Grafana token mint failed, so the requests use the admin password: %s", exc
            )
        else:
            return minted, None

    auth_bytes = f"admin:{pw}".encode()
    return None, f"Basic {base64.b64encode(auth_bytes).decode('utf-8')}"


def _check_token(
    url: str, token: str, service: str, level: EgressLevel, timeout: float
) -> httpx2.Response | None:
    """Send the bearer token to `url`: the answer when accepted, None when the service refused it.

    The request dials at `level`. Raise StackCredentialError when the check fails, with another
    status, a request error or an address that `level` refuses.
    """
    import httpx2

    from devops_cli.http.client import new_http_client

    try:
        with new_http_client(level=level, timeout=httpx2.Timeout(timeout)) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
    except (httpx2.RequestError, SSRFBlockedError) as exc:
        raise StackCredentialError(
            f"The {service} token check at {url} failed: {_request_failure(exc)}"
        ) from exc
    if resp.status_code in CONST_STACK_TOKEN_REFUSED_HTTP_STATUSES:
        return None
    if not resp.is_success:
        raise StackCredentialError(
            f"The {service} token check at {url} failed with HTTP {resp.status_code}"
        )
    return resp


def verify_argocd_token(
    base_url: str,
    token: str,
    *,
    level: EgressLevel,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> bool:
    """Return True when Argo CD accepts the session token, and False when it refuses it.

    Argo CD refuses a token with HTTP 401 or 403, or with `loggedIn: false` from its userinfo,
    which answers every caller with HTTP 200. Raise StackCredentialError when the check fails:
    another status, an answer that is not JSON, a request error, or an address that `level`
    refuses.
    """
    clean_base = service_base_url(base_url, "argocd.url")
    url = f"{clean_base}/api/v1/session/userinfo"
    resp = _check_token(url, token, _ARGOCD_LABEL, level, timeout)
    if resp is None:
        return False
    return _read_json(resp, dict, _ARGOCD_LABEL).get("loggedIn") is True


def verify_grafana_token(
    base_url: str,
    token: str,
    *,
    level: EgressLevel,
    timeout: float = DEFAULT_STACK_AUTH_TIMEOUT_SECONDS,
) -> bool:
    """Return True when Grafana accepts the API or service account token, False when it refuses it.

    Grafana refuses a token with HTTP 401 or 403. Raise StackCredentialError when the check
    fails: another status, a request error, or an address that `level` refuses.
    """
    clean_base = service_base_url(base_url, "grafana.url")
    url = f"{clean_base}/api/org"
    return _check_token(url, token, _GRAFANA_LABEL, level, timeout) is not None


@dataclass(frozen=True)
class _TokenService:
    """How the sync finds, checks and mints the API token of one stack service."""

    label: str
    key: str
    stored_token: Callable[[Settings], str | None]
    verify: Callable[..., bool]
    mint: Callable[..., str]


_ARGOCD_TOKEN = _TokenService(
    _ARGOCD_LABEL, "argocd_token", get_argocd_token, verify_argocd_token, mint_argocd_token
)
_GRAFANA_TOKEN = _TokenService(
    _GRAFANA_LABEL, "grafana_token", get_grafana_token, verify_grafana_token, mint_grafana_token
)


def _failed(exc: StackCredentialError) -> CredentialSync:
    return CredentialSync(SyncState.FAILED, str(exc))


def _keep_accepted_token(
    service: _TokenService, token: str, *, save_to_keyring: bool
) -> CredentialSync:
    """Copy the accepted token into the keyring; it can come from Vault or the environment."""
    if save_to_keyring:
        try:
            _store_secret(service.key, token, service.key)
        except StackCredentialError as exc:
            return _failed(exc)
    return _SYNCED


def _sync_token(
    service: _TokenService,
    url: str,
    settings: Settings,
    password: str | None,
    *,
    save_to_keyring: bool,
) -> CredentialSync | None:
    """Keep the stored token that the service accepts, and mint a new one only after a refusal.

    The check and the mint dial the configured level of `settings`. Return None when there is
    nothing to sync: no stored token and no admin password.
    """
    level = configured_level(settings.ai)
    stored_token = service.stored_token(settings)
    if stored_token:
        try:
            accepted = service.verify(url, stored_token, level=level)
        except StackCredentialError as exc:
            return CredentialSync(SyncState.FAILED, f"{exc}; the stored token stays in the keyring")
        if accepted:
            return _keep_accepted_token(service, stored_token, save_to_keyring=save_to_keyring)
        if not password:
            return CredentialSync(
                SyncState.FAILED,
                f"{service.label} refused the stored token, and no admin password is available "
                "to mint a new one",
            )
    if not password:
        return None
    try:
        service.mint(url, password, level=level, save_to_keyring=save_to_keyring)
    except StackCredentialError as exc:
        return _failed(exc)
    return _SYNCED


def _add_token_sync(
    results: dict[str, CredentialSync],
    service: _TokenService,
    url: str | None,
    settings: Settings,
    password: str | None,
    *,
    save_to_keyring: bool,
) -> None:
    if not url:
        return
    outcome = _sync_token(service, url, settings, password, save_to_keyring=save_to_keyring)
    if outcome is not None:
        results[service.key] = outcome


def _sync_argocd_password(
    context: str | None, *, save_to_keyring: bool
) -> tuple[CredentialSync, str | None]:
    """Copy the admin password from the cluster; return the outcome and the password."""
    try:
        password = fetch_argocd_password(context=context, save_to_keyring=save_to_keyring)
    except StackCredentialError as exc:
        return _failed(exc), None
    return (_SYNCED if password else _MISSING), password


@trace_span("k8s.credentials.sync")
def sync_k8s_credentials(
    context: str | None = None,
    stack: str = DEFAULT_BOOTSTRAP_STACK,
    save_to_keyring: bool = True,
    argocd_url: str | None = None,
    grafana_url: str | None = None,
) -> dict[str, CredentialSync]:
    """Copy the chart-generated Argo CD admin password into the OS keyring, and keep the API
    tokens of Argo CD and Grafana.

    Only `infra` (or `all`) has such credentials. The Secrets `devops k8s push-secrets` writes
    from the keyring are never copied back. Each entry says whether its credential was synced,
    is missing, or failed with a cause. A token has no entry when its service has no URL, or when
    there is no stored token and no admin password.
    """
    results: dict[str, CredentialSync] = {}
    if stack not in ("infra", "all"):
        return results

    settings = load_settings()
    results["argocd"], argocd_password = _sync_argocd_password(
        context, save_to_keyring=save_to_keyring
    )
    _add_token_sync(
        results,
        _ARGOCD_TOKEN,
        argocd_url or settings.argocd.url,
        settings,
        argocd_password,
        save_to_keyring=save_to_keyring,
    )
    grafana_password = _keyring_get("grafana_password")
    results["grafana"] = _SYNCED if grafana_password else _MISSING
    _add_token_sync(
        results,
        _GRAFANA_TOKEN,
        grafana_url or settings.grafana.url,
        settings,
        grafana_password,
        save_to_keyring=save_to_keyring,
    )
    return results
