"""The checks of the live Gitea stack that `devops k8s doctor --stack gitea` runs (#2187).

kubectl reads the Argo CD Applications, the claim and its volume, the namespace and the Ingress.
The HTTP checks go to the host of the live Ingress, never to the host in git, through the
Cloudflare tunnel, as a workstation reaches Gitea. The clone-URL check signs in as the admin with
the password that the settings layer reads from the keyring, makes one private repository with a
random name, reads its URLs, and deletes it again, also when the check fails. The password goes
only into the Authorization header of those two requests: never into an argument list, a log
line, the output or an error. A probe in the pod shows that it reaches no address outside the
cluster.

Each check gives its result and its reason, and a failed check does not stop the next one.
"""

from __future__ import annotations

import json
import secrets
import shlex
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial
from http import HTTPStatus
from typing import Any
from urllib.parse import urlsplit
from urllib.request import parse_http_list, parse_keqv_list

import httpx2
from pydantic import ValidationError as SettingsValidationError

from devops_cli.config.commands import build_kubectl_cmd
from devops_cli.config.constants import (
    CONST_ARGOCD_HEALTH_STATUS_HEALTHY,
    CONST_ARGOCD_SYNC_STATUS_SYNCED,
    CONST_CURL_NO_CONNECTION_EXIT_CODES,
    CONST_GITEA_ANONYMOUS_REFUSALS,
    CONST_GITEA_CREATE_REPO_PATH,
    CONST_GITEA_LOGIN_PATH,
    CONST_GITEA_REGISTRY_PATH,
    CONST_GITEA_REPO_PATH_TEMPLATE,
    CONST_GITEA_REPO_SEARCH_PATH,
    CONST_GITEA_TEMPORARY_REPO_DESCRIPTION,
    CONST_GITEA_TEMPORARY_REPO_PREFIX,
    CONST_HTTP_BEARER_SCHEME,
    CONST_K8S_ARGOCD_APPLICATION_RESOURCE,
    CONST_K8S_DOCTOR_CHECK_ANONYMOUS_READ,
    CONST_K8S_DOCTOR_CHECK_APPLICATION_PREFIX,
    CONST_K8S_DOCTOR_CHECK_CLONE_URL,
    CONST_K8S_DOCTOR_CHECK_INGRESS_HOST,
    CONST_K8S_DOCTOR_CHECK_NO_EGRESS,
    CONST_K8S_DOCTOR_CHECK_POD_SECURITY,
    CONST_K8S_DOCTOR_CHECK_REGISTRY_TOKEN,
    CONST_K8S_DOCTOR_CHECK_REPOSITORY_DELETED,
    CONST_K8S_DOCTOR_CHECK_TUNNEL_HOST,
    CONST_K8S_DOCTOR_CHECK_VOLUME_RETAINED,
    CONST_K8S_GITEA_ADMIN_USER,
    CONST_K8S_GITEA_APPLICATIONS,
    CONST_K8S_GITEA_CLAIM,
    CONST_K8S_GITEA_CONTAINER,
    CONST_K8S_GITEA_DEPLOYMENT,
    CONST_K8S_GITEA_EGRESS_PROBE_URL,
    CONST_K8S_GITEA_INGRESS,
    CONST_K8S_GITEA_NAMESPACE,
    CONST_K8S_GITEA_PLACEHOLDER_HOST,
    CONST_K8S_POD_SECURITY_ENFORCE_LABEL,
    CONST_K8S_POD_SECURITY_RESTRICTED,
    CONST_K8S_PVC_PHASE_BOUND,
    CONST_K8S_RECLAIM_POLICY_RETAIN,
    CONST_URL_SCHEME_SSH,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_K8S_DOCTOR_EGRESS_PROBE_SECONDS,
    DEFAULT_K8S_DOCTOR_HTTP_TIMEOUT_SECONDS,
    DEFAULT_K8S_DOCTOR_KUBECTL_TIMEOUT_SECONDS,
)
from devops_cli.config.env import credential
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions import ConfigurationError, SSRFBlockedError
from devops_cli.exceptions.k8s import DoctorCheckError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.models.k8s import DoctorCheck
from devops_cli.security.sanitizer import mask_secrets

_INGRESS_REF = f"{CONST_K8S_GITEA_NAMESPACE}/{CONST_K8S_GITEA_INGRESS}"
_PLANNED_HOST = f"<host of Ingress {_INGRESS_REF}>"
"""How a dry run names the host of the HTTP requests, which only a real run reads."""
_KEYRING_KEY = credential("gitea.admin_password").keyring_name
_CREATE_RESOURCE = f"POST {CONST_GITEA_CREATE_REPO_PATH}"


# ── kubectl arguments, shared by the run and its dry-run plan ───────────────


def _application_args(name: str) -> list[str]:
    return [
        "get",
        CONST_K8S_ARGOCD_APPLICATION_RESOURCE,
        name,
        "-n",
        DEFAULT_ARGOCD_NAMESPACE,
        "-o",
        "json",
    ]


def _claim_args() -> list[str]:
    return [
        "get",
        "persistentvolumeclaim",
        CONST_K8S_GITEA_CLAIM,
        "-n",
        CONST_K8S_GITEA_NAMESPACE,
        "-o",
        "json",
    ]


def _volume_args(volume: str) -> list[str]:
    return ["get", "persistentvolume", volume, "-o", "json"]


def _namespace_args() -> list[str]:
    return ["get", "namespace", CONST_K8S_GITEA_NAMESPACE, "-o", "json"]


def _ingress_args() -> list[str]:
    return [
        "get",
        "ingress",
        CONST_K8S_GITEA_INGRESS,
        "-n",
        CONST_K8S_GITEA_NAMESPACE,
        "-o",
        "json",
    ]


def _probe_args() -> list[str]:
    """curl in the Gitea container, to an address outside the cluster that it must not reach."""
    return [
        "exec",
        "-n",
        CONST_K8S_GITEA_NAMESPACE,
        f"deploy/{CONST_K8S_GITEA_DEPLOYMENT}",
        "-c",
        CONST_K8S_GITEA_CONTAINER,
        "--",
        "curl",
        "-sS",
        "-m",
        str(DEFAULT_K8S_DOCTOR_EGRESS_PROBE_SECONDS),
        "-o",
        "/dev/null",
        CONST_K8S_GITEA_EGRESS_PROBE_URL,
    ]


def _create_body(name: str) -> dict[str, Any]:
    """The body of the create: a private, empty repository that says what made it."""
    return {
        "name": name,
        "private": True,
        "auto_init": False,
        "description": CONST_GITEA_TEMPORARY_REPO_DESCRIPTION,
    }


def _repository_path(name: str) -> str:
    return CONST_GITEA_REPO_PATH_TEMPLATE.format(owner=CONST_K8S_GITEA_ADMIN_USER, name=name)


def plan_gitea_requests(context: str | None) -> list[PlannedRequest]:
    """The requests of the Gitea checks, in order, for a dry run that makes none of them."""

    def kubectl(args: Sequence[str], condition: str = "") -> PlannedRequest:
        argv = tuple(build_kubectl_cmd(args, context))
        return PlannedRequest(method="kubectl", target=args[0], argv=argv, condition=condition)

    as_admin = f" as {CONST_K8S_GITEA_ADMIN_USER} with <keyring {_KEYRING_KEY}>"

    def http(
        method: str, path: str, condition: str, *, signed_in: bool = False, stdin: str | None = None
    ) -> PlannedRequest:
        target = f"{path} on {_PLANNED_HOST} over HTTPS{as_admin if signed_in else ''}"
        return PlannedRequest(method, target, stdin=stdin, condition=condition)

    has_host = "the Ingress has a host"
    name = f"{CONST_GITEA_TEMPORARY_REPO_PREFIX}<random>"
    return [
        *(kubectl(_application_args(app)) for app in CONST_K8S_GITEA_APPLICATIONS),
        kubectl(_claim_args()),
        kubectl(
            _volume_args(f"<volume of claim {CONST_K8S_GITEA_CLAIM}>"),
            condition="the claim is bound",
        ),
        kubectl(_namespace_args()),
        kubectl(_ingress_args()),
        http("GET", CONST_GITEA_LOGIN_PATH, has_host),
        http("GET", CONST_GITEA_REPO_SEARCH_PATH, has_host),
        http("GET", CONST_GITEA_REGISTRY_PATH, has_host),
        http(
            "POST",
            CONST_GITEA_CREATE_REPO_PATH,
            both(has_host, f"the keyring holds {_KEYRING_KEY}"),
            signed_in=True,
            stdin=json.dumps(_create_body(name)),
        ),
        http(
            "DELETE",
            _repository_path(name),
            "the create made the repository or got no answer",
            signed_in=True,
        ),
        kubectl(_probe_args()),
    ]


# ── Results ────────────────────────────────────────────────────────────────


def _result(name: str, resource: str, *, passed: bool, reason: str) -> DoctorCheck:
    """A check's result. The reason can quote kubectl or Gitea, so it is masked."""
    return DoctorCheck(name=name, resource=resource, passed=passed, reason=mask_secrets(reason))


def _check(name: str, resource: str, run: Callable[[], str]) -> DoctorCheck:
    """Run one check: it passes with the reason that `run` returns, or fails with its error."""
    try:
        return _result(name, resource, passed=True, reason=run())
    except DoctorCheckError as exc:
        return _result(name, resource, passed=False, reason=str(exc))


def _text(data: Any, *path: str) -> str:
    """The text at `path` in a decoded JSON object, or "" when a key is absent."""
    for key in path:
        data = data.get(key) if isinstance(data, dict) else None
    return "" if data is None else str(data)


# ── The cluster ────────────────────────────────────────────────────────────


def _kubectl(args: Sequence[str], context: str | None) -> subprocess.CompletedProcess[str]:
    try:
        return run_subprocess(
            build_kubectl_cmd(args, context),
            quiet=True,
            timeout=DEFAULT_K8S_DOCTOR_KUBECTL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise DoctorCheckError(f"kubectl {args[0]} took more than {exc.timeout:g} s") from exc


def _kubectl_json(args: Sequence[str], context: str | None) -> dict[str, Any]:
    """The object that kubectl reads, or a failure with kubectl's own error."""
    result = _kubectl(args, context)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise DoctorCheckError(detail or f"kubectl {args[0]} exited {result.returncode}")
    try:
        data = json.loads(result.stdout or "")
    except json.JSONDecodeError as exc:
        raise DoctorCheckError(f"kubectl {shlex.join(args[:3])} gave no JSON: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _application(name: str, context: str | None) -> str:
    app = _kubectl_json(_application_args(name), context)
    sync = _text(app, "status", "sync", "status") or "Unknown"
    health = _text(app, "status", "health", "status") or "Unknown"
    state = f"{sync} and {health}"
    if (sync, health) != (CONST_ARGOCD_SYNC_STATUS_SYNCED, CONST_ARGOCD_HEALTH_STATUS_HEALTHY):
        raise DoctorCheckError(f"Application {name} is {state}")
    return state


def _volume_retained(context: str | None) -> str:
    claim = _kubectl_json(_claim_args(), context)
    phase = _text(claim, "status", "phase") or "Unknown"
    volume = _text(claim, "spec", "volumeName")
    if phase != CONST_K8S_PVC_PHASE_BOUND or not volume:
        raise DoctorCheckError(f"claim {CONST_K8S_GITEA_CLAIM} is {phase}, with no bound volume")
    policy = _text(
        _kubectl_json(_volume_args(volume), context), "spec", "persistentVolumeReclaimPolicy"
    )
    if policy != CONST_K8S_RECLAIM_POLICY_RETAIN:
        raise DoctorCheckError(
            f"volume {volume} has reclaim policy {policy or 'Unknown'}: local-path deletes the "
            "data with a deleted claim; set Retain (k8s/README.md, Gitea, Rollout)"
        )
    return f"volume {volume} has reclaim policy {policy}"


def _pod_security(context: str | None) -> str:
    namespace = _kubectl_json(_namespace_args(), context)
    level = _text(namespace, "metadata", "labels", CONST_K8S_POD_SECURITY_ENFORCE_LABEL)
    if level != CONST_K8S_POD_SECURITY_RESTRICTED:
        raise DoctorCheckError(
            f"Pod Security enforce is {level or 'unset'}, not {CONST_K8S_POD_SECURITY_RESTRICTED}"
        )
    return f"Pod Security enforce is {level}"


def _ingress_host(context: str | None) -> str:
    ingress = _kubectl_json(_ingress_args(), context)
    spec = ingress.get("spec")
    rules = spec.get("rules") if isinstance(spec, dict) else None
    hosts = [_text(rule, "host") for rule in (rules if isinstance(rules, list) else [])]
    host = next((name for name in hosts if name), "")
    if not host:
        raise DoctorCheckError(f"Ingress {_INGRESS_REF} has no host")
    if host == CONST_K8S_GITEA_PLACEHOLDER_HOST:
        raise DoctorCheckError(
            f"the host is {host}, the placeholder from git: run "
            "`devops k8s deploy-stack --stack gitea`"
        )
    return host


def _ingress_check(context: str | None) -> tuple[DoctorCheck, str | None]:
    """The Ingress check, and the host that the HTTP checks go to, or None when it has none."""
    resource = f"Ingress/{_INGRESS_REF}"
    try:
        host = _ingress_host(context)
    except DoctorCheckError as exc:
        return _result(
            CONST_K8S_DOCTOR_CHECK_INGRESS_HOST, resource, passed=False, reason=str(exc)
        ), None
    reason = f"the host is {host}"
    return _result(CONST_K8S_DOCTOR_CHECK_INGRESS_HOST, resource, passed=True, reason=reason), host


def _no_egress(context: str | None) -> str:
    result = _kubectl(_probe_args(), context)
    lines = (result.stderr or "").strip().splitlines()
    detail = lines[0] if lines else ""
    if result.returncode in CONST_CURL_NO_CONNECTION_EXIT_CODES:
        return f"curl exited {result.returncode}: {detail}"
    if result.returncode == 0:
        raise DoctorCheckError(f"the pod reached {CONST_K8S_GITEA_EGRESS_PROBE_URL}")
    raise DoctorCheckError(
        f"the probe exited {result.returncode}, not with a refused connect: {detail}"
    )


# ── Gitea through the tunnel host ──────────────────────────────────────────


@dataclass(frozen=True)
class _Tunnel:
    """Gitea at the host of the live Ingress, as a workstation reaches it."""

    client: httpx2.Client
    host: str

    def send(self, method: str, path: str, **options: Any) -> httpx2.Response:
        try:
            url = httpx2.URL(scheme="https", host=self.host, path=path)
            return self.client.request(method, url, **options)
        except (httpx2.HTTPError, SSRFBlockedError) as exc:
            raise DoctorCheckError(f"{method} {path} failed: {type(exc).__name__}: {exc}") from exc

    def is_under(self, url: str) -> bool:
        """Whether `url` is an HTTPS URL on the tunnel host."""
        parts = urlsplit(url)
        return parts.scheme == "https" and parts.netloc == self.host


def _message(response: httpx2.Response) -> str:
    """Gitea's error message, or else the reason phrase of the status."""
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    message = body.get("message") if isinstance(body, dict) else None
    return str(message) if message else response.reason_phrase


def _json(response: httpx2.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:
        request = response.request
        raise DoctorCheckError(
            f"{request.method} {request.url.path} answers {response.status_code} with no JSON"
        ) from exc


def _sign_in_page(tunnel: _Tunnel) -> str:
    response = tunnel.send("GET", CONST_GITEA_LOGIN_PATH)
    status = response.status_code
    if status == HTTPStatus.OK:
        return f"the sign-in page answers {status}"
    if response.is_redirect:
        location = response.headers.get("location", "")
        raise DoctorCheckError(f"the sign-in page answers {status}, a redirect to {location}")
    raise DoctorCheckError(f"the sign-in page answers {status}")


def _anonymous_read(tunnel: _Tunnel) -> str:
    status = tunnel.send("GET", CONST_GITEA_REPO_SEARCH_PATH).status_code
    if status in CONST_GITEA_ANONYMOUS_REFUSALS:
        return f"an anonymous read gets {status}"
    raise DoctorCheckError(f"an anonymous read gets {status}, not 401 or 403")


def _bearer_realm(challenge: str) -> str:
    """The realm of a Bearer challenge (RFC 6750), or "" for another scheme."""
    scheme, _, params = challenge.strip().partition(" ")
    if scheme.lower() != CONST_HTTP_BEARER_SCHEME:
        return ""
    try:
        return parse_keqv_list(parse_http_list(params)).get("realm", "")
    except ValueError:
        return ""


def _registry_token(tunnel: _Tunnel) -> str:
    response = tunnel.send("GET", CONST_GITEA_REGISTRY_PATH)
    if response.status_code != HTTPStatus.UNAUTHORIZED:
        raise DoctorCheckError(
            f"GET {CONST_GITEA_REGISTRY_PATH} answers {response.status_code}, not 401 with a "
            "token challenge"
        )
    challenges = response.headers.get_list("www-authenticate")
    realm = next((realm for value in challenges if (realm := _bearer_realm(value))), "")
    if not realm:
        raise DoctorCheckError("401 with no Bearer challenge")
    if not tunnel.is_under(realm):
        raise DoctorCheckError(f"the token realm {realm} is not under https://{tunnel.host}/")
    return f"401 with the token realm {realm}"


def _ssh_host(ssh_url: str) -> str:
    """The host of an SSH clone URL: an `ssh` URL, or git's scp-like `user@host:path`, whose part
    before the first `/` git reads as the user, the host and the path (git-clone(1), GIT URLS).
    The scp-like form parses as a network-path reference (RFC 3986, section 4.2)."""
    parts = urlsplit(ssh_url)
    if parts.scheme == CONST_URL_SCHEME_SSH:
        return parts.hostname or ""
    return urlsplit(f"//{ssh_url}").hostname or ""


@dataclass
class _TemporaryRepository:
    """The repository that the clone-URL check makes. `auth` never reaches a repr."""

    name: str
    auth: httpx2.BasicAuth | None = field(default=None, repr=False)
    # Whether Gitea can hold the repository, so that the delete must go out: from the send of the
    # create on, until Gitea refuses the create.
    maybe_made: bool = False


def _first_settings_error(exc: SettingsValidationError) -> str:
    """Where and why the settings refuse the configuration, without the value at fault."""
    first = exc.errors(include_url=False, include_context=False, include_input=False)[0]
    where = ".".join(str(part) for part in first["loc"])
    return f"{where}: {first['msg']}"


def _admin_auth() -> httpx2.BasicAuth:
    """The admin's credential, from the keyring through the settings layer."""
    from devops_cli.config.settings import get_gitea_admin_password, load_settings

    try:
        settings = load_settings()
    except (SettingsValidationError, ConfigurationError) as exc:
        # The settings give an unknown key as a ConfigurationError that names its file, its line
        # and the command that removes it (#2201).
        reason = exc.message if isinstance(exc, ConfigurationError) else _first_settings_error(exc)
        raise DoctorCheckError(
            f"the configuration does not load, so the password is not read: {reason}"
        ) from exc
    password = get_gitea_admin_password(settings)
    if not password:
        raise DoctorCheckError(
            "gitea.admin_password has no value: store it with "
            "`devops config set gitea.admin_password`"
        )
    return httpx2.BasicAuth(CONST_K8S_GITEA_ADMIN_USER, password)


def _clone_urls(tunnel: _Tunnel, repository: _TemporaryRepository) -> str:
    repository.auth = _admin_auth()
    repository.maybe_made = True
    path = CONST_GITEA_CREATE_REPO_PATH
    created = tunnel.send("POST", path, json=_create_body(repository.name), auth=repository.auth)
    repository.maybe_made = created.status_code == HTTPStatus.CREATED
    if not repository.maybe_made:
        raise DoctorCheckError(f"POST {path} answers {created.status_code}: {_message(created)}")
    urls = _json(created)
    clone_url = _text(urls, "clone_url")
    ssh_url = _text(urls, "ssh_url")
    if not tunnel.is_under(clone_url):
        raise DoctorCheckError(
            f"clone_url {clone_url or '(none)'} is not under https://{tunnel.host}/"
        )
    if _ssh_host(ssh_url) == tunnel.host:
        raise DoctorCheckError(f"ssh_url {ssh_url} names the tunnel host, which carries no SSH")
    return (
        f"clone_url {clone_url} is under https://{tunnel.host}/, and ssh_url "
        f"{ssh_url or '(none)'} does not name the tunnel host"
    )


def _delete(tunnel: _Tunnel, repository: _TemporaryRepository) -> str:
    path = _repository_path(repository.name)
    status = tunnel.send("DELETE", path, auth=repository.auth).status_code
    if status == HTTPStatus.NO_CONTENT:
        return "Gitea deleted the repository"
    if status == HTTPStatus.NOT_FOUND:
        return "Gitea holds no such repository"
    raise DoctorCheckError(
        f"the delete answers {status}: delete repository "
        f"{CONST_K8S_GITEA_ADMIN_USER}/{repository.name} by hand"
    )


def _repository_checks(tunnel: _Tunnel) -> list[DoctorCheck]:
    """The clone-URL check, and the delete of its repository whenever Gitea can hold it."""
    repository = _TemporaryRepository(name=CONST_GITEA_TEMPORARY_REPO_PREFIX + secrets.token_hex(4))
    deleted: list[DoctorCheck] = []
    try:
        clone = _check(
            CONST_K8S_DOCTOR_CHECK_CLONE_URL,
            _CREATE_RESOURCE,
            partial(_clone_urls, tunnel, repository),
        )
    finally:
        if repository.maybe_made:
            deleted.append(
                _check(
                    CONST_K8S_DOCTOR_CHECK_REPOSITORY_DELETED,
                    f"DELETE {_repository_path(repository.name)}",
                    partial(_delete, tunnel, repository),
                )
            )
    return [clone, *deleted]


def _tunnel_checks(host: str | None, why: str) -> list[DoctorCheck]:
    """The checks through the tunnel host; without a host, each fails and sends nothing."""
    reads: tuple[tuple[str, str, Callable[[_Tunnel], str]], ...] = (
        (CONST_K8S_DOCTOR_CHECK_TUNNEL_HOST, f"GET {CONST_GITEA_LOGIN_PATH}", _sign_in_page),
        (
            CONST_K8S_DOCTOR_CHECK_ANONYMOUS_READ,
            f"GET {CONST_GITEA_REPO_SEARCH_PATH}",
            _anonymous_read,
        ),
        (
            CONST_K8S_DOCTOR_CHECK_REGISTRY_TOKEN,
            f"GET {CONST_GITEA_REGISTRY_PATH}",
            _registry_token,
        ),
    )
    if host is None:
        not_run = [(name, resource) for name, resource, _ in reads]
        not_run.append((CONST_K8S_DOCTOR_CHECK_CLONE_URL, _CREATE_RESOURCE))
        return [
            _result(name, resource, passed=False, reason=f"not run: {why}")
            for name, resource in not_run
        ]
    with new_http_client(
        level=EgressLevel.PUBLIC,
        timeout=DEFAULT_K8S_DOCTOR_HTTP_TIMEOUT_SECONDS,
        follow_redirects=False,
    ) as client:
        tunnel = _Tunnel(client, host)
        checks = [_check(name, resource, partial(read, tunnel)) for name, resource, read in reads]
        return [*checks, *_repository_checks(tunnel)]


def run_gitea_checks(context: str | None) -> list[DoctorCheck]:
    """Run every check of the live Gitea stack, in order, and return each result."""
    checks = [
        _check(
            f"{CONST_K8S_DOCTOR_CHECK_APPLICATION_PREFIX}{name}",
            f"Application/{DEFAULT_ARGOCD_NAMESPACE}/{name}",
            partial(_application, name, context),
        )
        for name in CONST_K8S_GITEA_APPLICATIONS
    ]
    checks.append(
        _check(
            CONST_K8S_DOCTOR_CHECK_VOLUME_RETAINED,
            f"PersistentVolumeClaim/{CONST_K8S_GITEA_NAMESPACE}/{CONST_K8S_GITEA_CLAIM}",
            partial(_volume_retained, context),
        )
    )
    checks.append(
        _check(
            CONST_K8S_DOCTOR_CHECK_POD_SECURITY,
            f"Namespace/{CONST_K8S_GITEA_NAMESPACE}",
            partial(_pod_security, context),
        )
    )
    ingress, host = _ingress_check(context)
    checks.append(ingress)
    checks.extend(_tunnel_checks(host, ingress.reason))
    checks.append(
        _check(
            CONST_K8S_DOCTOR_CHECK_NO_EGRESS,
            f"Deployment/{CONST_K8S_GITEA_NAMESPACE}/{CONST_K8S_GITEA_DEPLOYMENT}",
            partial(_no_egress, context),
        )
    )
    return checks


__all__ = ["plan_gitea_requests", "run_gitea_checks"]
