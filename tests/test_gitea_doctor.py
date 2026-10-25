"""The checks of the live Gitea stack that `devops k8s doctor --stack gitea` runs (#2187).

kubectl goes to the process fake and Gitea's HTTP answers to the stub web, so no test starts a
program or reaches a network. `GiteaServer` answers as Gitea 1.27.3 answers through the tunnel
host: it makes a repository under the name in the body of the create, so it serves the delete of
a name that only the run knows.
"""

from __future__ import annotations

import base64
import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest

from devops_cli.k8s.gitea_doctor import run_gitea_checks
from devops_cli.models.k8s import DoctorCheck
from tests.cluster_secret_fakes import FakeKeyring
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.web_fakes import StubWeb

HOST = "example.com"
PASSWORD = "gitea-admin-password-0001"
IN_CLUSTER_HOST = "gitea-http.gitea.svc.cluster.local"
VOLUME = "pvc-0001"
EGRESS_PROBE = (
    "kubectl",
    "exec",
    "-n",
    "gitea",
    "deploy/gitea",
    "-c",
    "gitea",
    "--",
    "curl",
    "-sS",
    "-m",
    "5",
    "-o",
    "/dev/null",
    "https://github.com",
)
REFUSED_CONNECT = "curl: (7) Failed to connect to github.com port 443: Could not connect to server"

pytestmark = pytest.mark.usefixtures("public_dns")


def _application(sync: str = "Synced", health: str = "Healthy") -> str:
    return json.dumps({"status": {"sync": {"status": sync}, "health": {"status": health}}})


@dataclass
class Cluster:
    """What kubectl answers about the Gitea stack; each field breaks one check."""

    gitea: str = field(default_factory=_application)
    manifests: str = field(default_factory=_application)
    claim: dict[str, Any] = field(
        default_factory=lambda: {"spec": {"volumeName": VOLUME}, "status": {"phase": "Bound"}}
    )
    reclaim_policy: str = "Retain"
    enforce: str = "restricted"
    ingress_rules: list[dict[str, Any]] = field(default_factory=lambda: [{"host": HOST}])
    egress_exit: int = 7
    egress_stderr: str = REFUSED_CONNECT

    def install(self, fake: ProcessFake, context: str | None = None) -> None:
        kubectl = ("kubectl", *(("--context", context) if context else ()))
        get = (*kubectl, "get")
        fake.answer(
            (*get, "applications.argoproj.io", "gitea", "-n", "argocd"),
            ProcessAnswer(stdout=self.gitea),
        )
        fake.answer(
            (*get, "applications.argoproj.io", "gitea-manifests", "-n", "argocd"),
            ProcessAnswer(stdout=self.manifests),
        )
        fake.answer(
            (*get, "persistentvolumeclaim", "gitea-shared-storage", "-n", "gitea"),
            ProcessAnswer(stdout=json.dumps(self.claim)),
        )
        fake.answer(
            (*get, "persistentvolume", VOLUME),
            ProcessAnswer(
                stdout=json.dumps({"spec": {"persistentVolumeReclaimPolicy": self.reclaim_policy}})
            ),
        )
        labels = {"pod-security.kubernetes.io/enforce": self.enforce}
        fake.answer(
            (*get, "namespace", "gitea"),
            ProcessAnswer(stdout=json.dumps({"metadata": {"labels": labels}})),
        )
        fake.answer(
            (*get, "ingress", "gitea-ingress", "-n", "gitea"),
            ProcessAnswer(stdout=json.dumps({"spec": {"rules": self.ingress_rules}})),
        )
        fake.answer(
            (*kubectl, *EGRESS_PROBE[1:]),
            ProcessAnswer(returncode=self.egress_exit, stderr=self.egress_stderr),
        )


def _bearer(host: str) -> str:
    return f'Bearer realm="https://{host}/v2/token",service="container_registry",scope="*"'


@dataclass
class GiteaServer:
    """Gitea's answers through the tunnel host; each field breaks one check."""

    login: httpx2.Response = field(default_factory=lambda: httpx2.Response(200))
    search: httpx2.Response = field(
        default_factory=lambda: httpx2.Response(
            403, json={"message": "Only signed in user is allowed to call APIs."}
        )
    )
    registry_status: int = 401
    challenges: tuple[str, ...] = (_bearer(HOST), 'Basic realm="Gitea Container Registry"')
    create_status: int = 201
    # A page in place of Gitea's JSON, as a proxy in front of Gitea can answer.
    create_page: str | None = None
    create_error: httpx2.HTTPError | None = None
    # Whether a create that gets no answer made the repository all the same.
    made_before_error: bool = True
    clone_host: str = HOST
    ssh_host: str = IN_CLUSTER_HOST
    # Gitea's scp-like form for SSH port 22; `ssh://<user>@<host>:<port>/...` for another port.
    ssh_form: str = "git@{host}:gitea_admin/{name}.git"
    delete_status: int = 204
    repositories: set[str] = field(default_factory=set)

    def __call__(self, request: httpx2.Request) -> httpx2.Response | None:
        if request.url.host != HOST:
            return None
        match request.method, request.url.path:
            case "GET", "/user/login":
                return self.login
            case "GET", "/api/v1/repos/search":
                return self.search
            case "GET", "/v2/":
                headers = [("www-authenticate", challenge) for challenge in self.challenges]
                return httpx2.Response(self.registry_status, headers=headers)
            case "POST", "/api/v1/user/repos":
                return self._create(request)
            case "DELETE", path:
                return self._delete(path.removeprefix("/api/v1/repos/gitea_admin/"))
        return None

    def _create(self, request: httpx2.Request) -> httpx2.Response:
        if request.headers.get("authorization") != _basic_auth():
            return httpx2.Response(401, json={"message": "user does not exist"})
        name = json.loads(request.content)["name"]
        if self.create_error is not None:
            if self.made_before_error:
                self.repositories.add(name)
            raise self.create_error
        if self.create_status != 201:
            if self.create_page is not None:
                return httpx2.Response(self.create_status, text=self.create_page)
            return httpx2.Response(self.create_status, json={"message": "refused"})
        self.repositories.add(name)
        if self.create_page is not None:
            return httpx2.Response(201, text=self.create_page)
        ssh_url = self.ssh_form.format(host=self.ssh_host, name=name) if self.ssh_host else ""
        return httpx2.Response(
            201,
            json={
                "full_name": f"gitea_admin/{name}",
                "private": True,
                "clone_url": f"https://{self.clone_host}/gitea_admin/{name}.git",
                "ssh_url": ssh_url,
            },
        )

    def _delete(self, name: str) -> httpx2.Response:
        if name not in self.repositories:
            return httpx2.Response(404, json={"message": "repository not found"})
        if self.delete_status == 204:
            self.repositories.discard(name)
        return httpx2.Response(self.delete_status)


def _basic_auth() -> str:
    token = base64.b64encode(f"gitea_admin:{PASSWORD}".encode()).decode()
    return f"Basic {token}"


@pytest.fixture
def keyring_with_password(mock_keyring: FakeKeyring) -> FakeKeyring:
    """The keyring that holds the Gitea admin password, as `devops config set` stores it."""
    mock_keyring.values["gitea_admin_password"] = PASSWORD
    return mock_keyring


def _run(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    cluster: Cluster | None = None,
    server: GiteaServer | None = None,
) -> tuple[list[DoctorCheck], GiteaServer]:
    gitea = server or GiteaServer()
    (cluster or Cluster()).install(process_fake)
    stub_web.serve(gitea)
    return run_gitea_checks(context=None), gitea


def _repository(stub_web: StubWeb) -> str:
    """The name of the temporary repository, read from the body of the create."""
    creates = [r for r in stub_web.sent if r.method == "POST"]
    return str(json.loads(creates[0].content)["name"])


def _failures(checks: list[DoctorCheck]) -> dict[str, str]:
    return {check.name: check.reason for check in checks if not check.passed}


def _passed(name: str, resource: str, reason: str) -> DoctorCheck:
    return DoctorCheck(name=name, resource=resource, passed=True, reason=reason)


@pytest.mark.usefixtures("keyring_with_password")
def test_a_healthy_gitea_stack_passes_every_check(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """Every check passes, with its reason, and the temporary repository is gone at the end."""
    checks, gitea = _run(process_fake, stub_web)
    name = _repository(stub_web)

    assert checks == [
        _passed("application-gitea", "Application/argocd/gitea", "Synced and Healthy"),
        _passed(
            "application-gitea-manifests",
            "Application/argocd/gitea-manifests",
            "Synced and Healthy",
        ),
        _passed(
            "volume-retained",
            "PersistentVolumeClaim/gitea/gitea-shared-storage",
            f"volume {VOLUME} has reclaim policy Retain",
        ),
        _passed("pod-security-restricted", "Namespace/gitea", "Pod Security enforce is restricted"),
        _passed("ingress-host", "Ingress/gitea/gitea-ingress", f"the host is {HOST}"),
        _passed("tunnel-host", "GET /user/login", "the sign-in page answers 200"),
        _passed(
            "anonymous-read-refused",
            "GET /api/v1/repos/search",
            "an anonymous read gets 403",
        ),
        _passed(
            "registry-token",
            "GET /v2/",
            f"401 with the token realm https://{HOST}/v2/token",
        ),
        _passed(
            "clone-url",
            "POST /api/v1/user/repos",
            f"clone_url https://{HOST}/gitea_admin/{name}.git is under https://{HOST}/, and "
            f"ssh_url git@{IN_CLUSTER_HOST}:gitea_admin/{name}.git does not name the tunnel host",
        ),
        _passed(
            "temporary-repository-deleted",
            f"DELETE /api/v1/repos/gitea_admin/{name}",
            "Gitea deleted the repository",
        ),
        _passed("no-egress", "Deployment/gitea/gitea", f"curl exited 7: {REFUSED_CONNECT}"),
    ]
    assert gitea.repositories == set()
    assert name.startswith("devops-doctor-")


@pytest.mark.usefixtures("keyring_with_password")
def test_the_checks_read_the_cluster_with_kubectl_and_reach_only_the_ingress_host(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """kubectl reads each object once, and every request goes to the host of the live Ingress."""
    _run(process_fake, stub_web)
    name = _repository(stub_web)

    get = ["kubectl", "get"]
    assert [list(call.argv) for call in process_fake.calls] == [
        [*get, "applications.argoproj.io", "gitea", "-n", "argocd", "-o", "json"],
        [*get, "applications.argoproj.io", "gitea-manifests", "-n", "argocd", "-o", "json"],
        [*get, "persistentvolumeclaim", "gitea-shared-storage", "-n", "gitea", "-o", "json"],
        [*get, "persistentvolume", VOLUME, "-o", "json"],
        [*get, "namespace", "gitea", "-o", "json"],
        [*get, "ingress", "gitea-ingress", "-n", "gitea", "-o", "json"],
        list(EGRESS_PROBE),
    ]
    assert [(r.method, str(r.url)) for r in stub_web.sent] == [
        ("GET", f"https://{HOST}/user/login"),
        ("GET", f"https://{HOST}/api/v1/repos/search"),
        ("GET", f"https://{HOST}/v2/"),
        ("POST", f"https://{HOST}/api/v1/user/repos"),
        ("DELETE", f"https://{HOST}/api/v1/repos/gitea_admin/{name}"),
    ]
    create = json.loads(stub_web.sent[3].content)
    assert create == {
        "name": name,
        "private": True,
        "auto_init": False,
        "description": "A temporary repository of devops k8s doctor. The doctor deletes it.",
    }


def _no_host(reason: str) -> dict[str, str]:
    """The failures when the Ingress gives no host: no request goes to Gitea."""
    not_run = f"not run: {reason}"
    return {
        "ingress-host": reason,
        "tunnel-host": not_run,
        "anonymous-read-refused": not_run,
        "registry-token": not_run,
        "clone-url": not_run,
    }


@pytest.mark.usefixtures("keyring_with_password")
@pytest.mark.parametrize(
    ("cluster", "expected"),
    [
        pytest.param(
            Cluster(gitea=_application("OutOfSync", "Degraded")),
            {"application-gitea": "Application gitea is OutOfSync and Degraded"},
            id="application-out-of-sync",
        ),
        pytest.param(
            Cluster(manifests=_application("Synced", "")),
            {"application-gitea-manifests": "Application gitea-manifests is Synced and Unknown"},
            id="application-health-unknown",
        ),
        pytest.param(
            Cluster(claim={"spec": {}, "status": {"phase": "Pending"}}),
            {"volume-retained": ("claim gitea-shared-storage is Pending, with no bound volume")},
            id="claim-not-bound",
        ),
        pytest.param(
            Cluster(reclaim_policy="Delete"),
            {
                "volume-retained": (
                    f"volume {VOLUME} has reclaim policy Delete: local-path deletes the data "
                    "with a deleted claim; set Retain (k8s/README.md, Gitea, Rollout)"
                )
            },
            id="volume-deleted-with-its-claim",
        ),
        pytest.param(
            Cluster(enforce="baseline"),
            {"pod-security-restricted": "Pod Security enforce is baseline, not restricted"},
            id="pod-security-baseline",
        ),
        pytest.param(
            Cluster(ingress_rules=[{"http": {}}]),
            _no_host("Ingress gitea/gitea-ingress has no host"),
            id="ingress-without-host",
        ),
        pytest.param(
            Cluster(ingress_rules=[{"host": "git.example.com"}]),
            _no_host(
                "the host is git.example.com, the placeholder from git: run "
                "`devops k8s deploy-stack --stack gitea`"
            ),
            id="ingress-with-the-placeholder-host",
        ),
        pytest.param(
            Cluster(egress_exit=0, egress_stderr=""),
            {"no-egress": "the pod reached https://github.com"},
            id="pod-reaches-the-internet",
        ),
        pytest.param(
            Cluster(egress_exit=127, egress_stderr='exec: "curl": executable file not found'),
            {
                "no-egress": (
                    'the probe exited 127, not with a refused connect: exec: "curl": '
                    "executable file not found"
                )
            },
            id="probe-cannot-run",
        ),
    ],
)
def test_a_broken_cluster_object_fails_its_check(
    process_fake: ProcessFake, stub_web: StubWeb, cluster: Cluster, expected: dict[str, str]
) -> None:
    """One broken object fails its own check, with the reason, and the others still pass."""
    checks, gitea = _run(process_fake, stub_web, cluster=cluster)

    assert _failures(checks) == expected
    assert gitea.repositories == set()


@pytest.mark.usefixtures("keyring_with_password")
def test_a_kubectl_failure_fails_its_check_with_kubectl_s_error(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A missing object fails its check with kubectl's own words; the next checks still run."""
    Cluster().install(process_fake)
    stub_web.serve(GiteaServer())
    not_found = 'Error from server (NotFound): applications.argoproj.io "gitea-manifests" not found'
    process_fake.answer(
        ("kubectl", "get", "applications.argoproj.io", "gitea-manifests"),
        ProcessAnswer(returncode=1, stderr=not_found),
    )

    checks = run_gitea_checks(context=None)

    assert _failures(checks) == {"application-gitea-manifests": not_found}


@pytest.mark.usefixtures("keyring_with_password")
@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        pytest.param(
            ProcessAnswer(stdout="claim gitea-shared-storage"),
            "kubectl get persistentvolumeclaim gitea-shared-storage gave no JSON: Expecting "
            "value: line 1 column 1 (char 0)",
            id="output-that-is-not-json",
        ),
        pytest.param(
            ProcessAnswer(side_effect=subprocess.TimeoutExpired(["kubectl"], 30)),
            "kubectl get took more than 30 s",
            id="kubectl-times-out",
        ),
    ],
)
def test_a_kubectl_read_with_no_object_fails_its_check(
    process_fake: ProcessFake, stub_web: StubWeb, answer: ProcessAnswer, expected: str
) -> None:
    """A read that gives no object fails its own check with what went wrong."""
    Cluster().install(process_fake)
    stub_web.serve(GiteaServer())
    process_fake.answer(("kubectl", "get", "persistentvolumeclaim"), answer)

    checks = run_gitea_checks(context=None)

    assert _failures(checks) == {"volume-retained": expected}


@pytest.mark.usefixtures("keyring_with_password")
@pytest.mark.parametrize(
    ("server", "expected"),
    [
        pytest.param(
            GiteaServer(
                login=httpx2.Response(
                    302, headers={"location": "https://example.org/cdn-cgi/access/login"}
                )
            ),
            {
                "tunnel-host": (
                    "the sign-in page answers 302, a redirect to "
                    "https://example.org/cdn-cgi/access/login"
                )
            },
            id="access-login-redirect",
        ),
        pytest.param(
            GiteaServer(login=httpx2.Response(502)),
            {"tunnel-host": "the sign-in page answers 502"},
            id="tunnel-bad-gateway",
        ),
        pytest.param(
            GiteaServer(search=httpx2.Response(200, json={"ok": True, "data": []})),
            {"anonymous-read-refused": "an anonymous read gets 200, not 401 or 403"},
            id="anonymous-read-admitted",
        ),
        pytest.param(
            GiteaServer(registry_status=404),
            {"registry-token": "GET /v2/ answers 404, not 401 with a token challenge"},
            id="registry-off",
        ),
        pytest.param(
            GiteaServer(challenges=('Basic realm="Gitea Container Registry"',)),
            {"registry-token": "401 with no Bearer challenge"},
            id="registry-without-token-challenge",
        ),
        pytest.param(
            GiteaServer(challenges=("Bearer realm",)),
            {"registry-token": "401 with no Bearer challenge"},
            id="registry-with-a-broken-challenge",
        ),
        pytest.param(
            GiteaServer(challenges=(_bearer(f"{IN_CLUSTER_HOST}:3000"),)),
            {
                "registry-token": (
                    f"the token realm https://{IN_CLUSTER_HOST}:3000/v2/token is not under "
                    f"https://{HOST}/"
                )
            },
            id="registry-realm-in-the-cluster",
        ),
    ],
)
def test_a_wrong_answer_through_the_tunnel_fails_its_check(
    process_fake: ProcessFake, stub_web: StubWeb, server: GiteaServer, expected: dict[str, str]
) -> None:
    """One wrong answer of Gitea fails its own check, with the reason."""
    checks, gitea = _run(process_fake, stub_web, server=server)

    assert _failures(checks) == expected
    assert gitea.repositories == set()


@pytest.mark.usefixtures("keyring_with_password")
@pytest.mark.parametrize(
    ("server", "expected"),
    [
        pytest.param(
            GiteaServer(clone_host=f"{IN_CLUSTER_HOST}:3000"),
            "clone_url https://{in_cluster}:3000/gitea_admin/{name}.git is not under "
            "https://{host}/",
            id="clone-url-in-the-cluster",
        ),
        pytest.param(
            GiteaServer(ssh_host=HOST),
            "ssh_url git@{host}:gitea_admin/{name}.git names the tunnel host, which carries no SSH",
            id="ssh-url-names-the-tunnel-host",
        ),
        pytest.param(
            GiteaServer(ssh_host=HOST, ssh_form="ssh://git@{host}:2222/gitea_admin/{name}.git"),
            "ssh_url ssh://git@{host}:2222/gitea_admin/{name}.git names the tunnel host, which "
            "carries no SSH",
            id="ssh-url-form-names-the-tunnel-host",
        ),
    ],
)
def test_the_temporary_repository_is_deleted_when_the_clone_url_check_fails(
    process_fake: ProcessFake, stub_web: StubWeb, server: GiteaServer, expected: str
) -> None:
    """A wrong clone URL fails the check, and the repository is deleted all the same."""
    checks, gitea = _run(process_fake, stub_web, server=server)
    name = _repository(stub_web)

    assert _failures(checks) == {
        "clone-url": expected.format(in_cluster=IN_CLUSTER_HOST, host=HOST, name=name)
    }
    assert [c for c in checks if c.name == "temporary-repository-deleted"] == [
        _passed(
            "temporary-repository-deleted",
            f"DELETE /api/v1/repos/gitea_admin/{name}",
            "Gitea deleted the repository",
        )
    ]
    assert gitea.repositories == set()


@pytest.mark.usefixtures("keyring_with_password")
def test_the_temporary_repository_is_deleted_when_the_create_gets_no_answer(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A create whose answer is lost may have made the repository, so the delete is sent."""
    server = GiteaServer(create_error=httpx2.ReadTimeout("The read operation timed out"))
    checks, gitea = _run(process_fake, stub_web, server=server)
    name = _repository(stub_web)

    assert _failures(checks) == {
        "clone-url": "POST /api/v1/user/repos failed: ReadTimeout: The read operation timed out"
    }
    assert [(r.method, r.url.path) for r in stub_web.sent][-1] == (
        "DELETE",
        f"/api/v1/repos/gitea_admin/{name}",
    )
    assert gitea.repositories == set()


@pytest.mark.usefixtures("keyring_with_password")
def test_a_failed_delete_fails_its_check_and_names_the_repository(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A repository that Gitea does not delete is named, so that a person can delete it."""
    checks, _ = _run(process_fake, stub_web, server=GiteaServer(delete_status=500))
    name = _repository(stub_web)

    assert _failures(checks) == {
        "temporary-repository-deleted": (
            f"the delete answers 500: delete repository gitea_admin/{name} by hand"
        )
    }


@pytest.mark.usefixtures("keyring_with_password")
def test_a_refused_create_makes_no_repository_and_sends_no_delete(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A create that Gitea refuses made nothing, so no delete goes to a name it did not make."""
    checks, _ = _run(process_fake, stub_web, server=GiteaServer(create_status=422))

    assert _failures(checks) == {"clone-url": "POST /api/v1/user/repos answers 422: refused"}
    assert [r.method for r in stub_web.sent] == ["GET", "GET", "GET", "POST"]
    assert "temporary-repository-deleted" not in {c.name for c in checks}


@pytest.mark.usefixtures("keyring_with_password")
def test_an_error_page_for_the_create_names_its_status(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A create that gets an error page in place of Gitea's JSON fails with the status."""
    server = GiteaServer(create_status=500, create_page="<html>Internal Server Error</html>")
    checks, _ = _run(process_fake, stub_web, server=server)

    assert _failures(checks) == {
        "clone-url": "POST /api/v1/user/repos answers 500: Internal Server Error"
    }
    assert [r.method for r in stub_web.sent] == ["GET", "GET", "GET", "POST"]


@pytest.mark.usefixtures("keyring_with_password")
def test_a_made_repository_with_no_json_answer_is_deleted(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A 201 with no JSON fails the clone-URL check, and the repository is deleted."""
    checks, gitea = _run(process_fake, stub_web, server=GiteaServer(create_page="made"))

    assert _failures(checks) == {"clone-url": "POST /api/v1/user/repos answers 201 with no JSON"}
    assert gitea.repositories == set()


@pytest.mark.usefixtures("keyring_with_password")
def test_a_delete_after_a_lost_create_passes_when_gitea_made_nothing(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A delete after a lost create finds no repository, and nothing is left behind."""
    server = GiteaServer(
        create_error=httpx2.ConnectError("Connection reset by peer"), made_before_error=False
    )
    checks, _ = _run(process_fake, stub_web, server=server)
    name = _repository(stub_web)

    assert [c for c in checks if c.name == "temporary-repository-deleted"] == [
        _passed(
            "temporary-repository-deleted",
            f"DELETE /api/v1/repos/gitea_admin/{name}",
            "Gitea holds no such repository",
        )
    ]


@pytest.mark.usefixtures("keyring_with_password")
def test_an_empty_ssh_url_passes_the_clone_url_check(
    process_fake: ProcessFake, stub_web: StubWeb
) -> None:
    """A repository with no SSH URL passes: nothing names the tunnel host for SSH."""
    checks, _ = _run(process_fake, stub_web, server=GiteaServer(ssh_host=""))
    name = _repository(stub_web)

    assert [c.reason for c in checks if c.name == "clone-url"] == [
        f"clone_url https://{HOST}/gitea_admin/{name}.git is under https://{HOST}/, and "
        "ssh_url (none) does not name the tunnel host"
    ]


def test_without_the_admin_password_no_repository_is_made(
    process_fake: ProcessFake, stub_web: StubWeb, mock_keyring: FakeKeyring
) -> None:
    """An empty keyring fails the clone-URL check, names the setting, and sends no create."""
    checks, _ = _run(process_fake, stub_web)

    assert _failures(checks) == {
        "clone-url": (
            "gitea.admin_password has no value: store it with "
            "`devops config set gitea.admin_password`"
        )
    }
    assert [r.method for r in stub_web.sent] == ["GET", "GET", "GET"]
    assert "gitea_admin_password" in mock_keyring.reads


@pytest.mark.usefixtures("keyring_with_password")
def test_an_unknown_key_fails_only_the_clone_url_check(
    process_fake: ProcessFake, stub_web: StubWeb, config: Callable[..., Any]
) -> None:
    """An unknown key fails the clone-URL check with its file, its line and the command that
    removes it, sends no create, and leaves the other checks to report."""
    path = config(ai={"vllm_url": "http://example.com"})
    line = path.read_text(encoding="utf-8").splitlines().index("  vllm_url: http://example.com")

    checks, _ = _run(process_fake, stub_web)

    assert _failures(checks) == {
        "clone-url": (
            "the configuration does not load, so the password is not read: Unknown configuration "
            f"key 'ai.vllm_url' at {path}:{line + 1}. Release 0.2.34 removed it. Remove it with: "
            "devops config unset ai.vllm_url"
        )
    }
    assert [r.method for r in stub_web.sent] == ["GET", "GET", "GET"]


@pytest.mark.usefixtures("keyring_with_password")
def test_a_refused_value_fails_only_the_clone_url_check(
    process_fake: ProcessFake, stub_web: StubWeb, config: Callable[..., Any]
) -> None:
    """A value that the settings refuse fails the clone-URL check with the key at fault and not
    the value, sends no create, and leaves the other checks to report."""
    config(ai={"context_window": 0})

    checks, _ = _run(process_fake, stub_web)

    assert _failures(checks) == {
        "clone-url": (
            "the configuration does not load, so the password is not read: ai.context_window: "
            "Input should be greater than 0"
        )
    }
    assert [r.method for r in stub_web.sent] == ["GET", "GET", "GET"]


@pytest.mark.usefixtures("keyring_with_password")
def test_the_password_goes_only_into_the_authorization_header(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    cli: Callable[..., Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No argument list, log line, output or printed request holds the password."""
    Cluster().install(process_fake, context="lab")
    stub_web.serve(GiteaServer(ssh_host=HOST))
    caplog.set_level(logging.DEBUG)

    result = cli("k8s", "doctor", "--stack", "gitea", "--context", "lab", "--format", "json")

    token = _basic_auth().removeprefix("Basic ")
    printed = [
        f"{request!r} {request.headers!r} {request.url} {request.content!r}"
        for request in stub_web.sent
    ]
    argv = [" ".join(call.argv) for call in process_fake.calls]
    seen = [result.stdout, result.stderr, caplog.text, *printed, *argv]
    assert [text for text in seen if PASSWORD in text or token in text] == []
    assert [r.headers.get("authorization") for r in stub_web.sent if r.method != "GET"] == [
        _basic_auth(),
        _basic_auth(),
    ]


@pytest.mark.usefixtures("keyring_with_password")
def test_the_command_reports_every_check_and_exits_0_when_all_pass(
    process_fake: ProcessFake, stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """`--stack gitea` reports each check as JSON and exits 0 when every check passes."""
    Cluster().install(process_fake, context="lab")
    stub_web.serve(GiteaServer())

    result = cli("k8s", "doctor", "--stack", "gitea", "--context", "lab", "--format", "json")
    report = json.loads(result.stdout)

    assert result.exit_code == 0
    assert (report["counts"], report["findings"]) == ({"checks": 11, "failed": 0}, [])
    assert [(c["name"], c["passed"]) for c in report["checks"]][:2] == [
        ("application-gitea", True),
        ("application-gitea-manifests", True),
    ]


@pytest.mark.usefixtures("keyring_with_password")
def test_the_command_prints_a_table_and_exits_2_when_a_check_fails(
    process_fake: ProcessFake, stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """A failed check is a row marked FAIL, with its reason, and the command exits 2."""
    Cluster(enforce="baseline").install(process_fake, context="lab")
    stub_web.serve(GiteaServer())

    result = cli("k8s", "doctor", "--stack", "gitea", "--context", "lab")
    rows = [line for line in result.stdout.splitlines() if "pod-security-restricted" in line]

    assert result.exit_code == 2
    assert len(rows) == 1
    assert ("FAIL" in rows[0], "baseline, not restricted" in rows[0]) == (True, True)
    assert "Gitea Stack Checks" in result.stdout


def test_the_dry_run_lists_the_requests_and_makes_none(
    process_fake: ProcessFake,
    stub_web: StubWeb,
    mock_keyring: FakeKeyring,
    cli: Callable[..., Any],
) -> None:
    """The dry run lists every kubectl call and HTTP request, and reads no keyring entry."""
    result = cli("k8s", "doctor", "--stack", "gitea", "--dry-run", "--context", "lab")

    assert result.exit_code == 0
    assert (process_fake.calls, stub_web.sent, mock_keyring.secret_reads()) == ([], [], set())
    get = "kubectl --context lab get"
    assert result.stdout.splitlines() == [
        "Planned Gitea Stack Checks:",
        f"  1. {get} applications.argoproj.io gitea -n argocd -o json",
        f"  2. {get} applications.argoproj.io gitea-manifests -n argocd -o json",
        f"  3. {get} persistentvolumeclaim gitea-shared-storage -n gitea -o json",
        f"  4. {get} persistentvolume '<volume of claim gitea-shared-storage>' -o json"
        "  [only if the claim is bound]",
        f"  5. {get} namespace gitea -o json",
        f"  6. {get} ingress gitea-ingress -n gitea -o json",
        "  7. GET /user/login on <host of Ingress gitea/gitea-ingress> over HTTPS"
        "  [only if the Ingress has a host]",
        "  8. GET /api/v1/repos/search on <host of Ingress gitea/gitea-ingress> over HTTPS"
        "  [only if the Ingress has a host]",
        "  9. GET /v2/ on <host of Ingress gitea/gitea-ingress> over HTTPS"
        "  [only if the Ingress has a host]",
        " 10. POST /api/v1/user/repos on <host of Ingress gitea/gitea-ingress> over HTTPS as gitea_admin with "
        "<keyring gitea_admin_password>"
        "  [only if the Ingress has a host and the keyring holds gitea_admin_password]",
        '       {"name": "devops-doctor-<random>", "private": true, "auto_init": false, '
        '"description": "A temporary repository of devops k8s doctor. The doctor deletes it."}',
        " 11. DELETE /api/v1/repos/gitea_admin/devops-doctor-<random> on <host of Ingress gitea/gitea-ingress> over HTTPS as "
        "gitea_admin with <keyring gitea_admin_password>"
        "  [only if the create made the repository or got no answer]",
        " 12. kubectl --context lab exec -n gitea deploy/gitea -c gitea -- curl -sS -m 5 -o "
        "/dev/null https://github.com",
    ]


def test_the_dry_run_as_json_holds_the_requests_and_no_checks(
    process_fake: ProcessFake, stub_web: StubWeb, cli: Callable[..., Any]
) -> None:
    """The JSON dry run gives the same requests as data, with no check."""
    result = cli("k8s", "doctor", "--stack", "gitea", "--dry-run", "--format", "json")
    plan = json.loads(result.stdout)

    assert result.exit_code == 0
    assert (process_fake.calls, stub_web.sent, plan["checks"]) == ([], [], [])
    assert [request["method"] for request in plan["requests"]] == [
        *(["kubectl"] * 6),
        "GET",
        "GET",
        "GET",
        "POST",
        "DELETE",
        "kubectl",
    ]


def test_an_unknown_stack_is_refused(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """Only the stacks that have checks are accepted, and nothing runs for another."""
    result = cli("k8s", "doctor", "--stack", "llm")

    assert result.exit_code == 2
    assert "Invalid value for '--stack'" in result.stdout + result.stderr
    assert process_fake.calls == []
