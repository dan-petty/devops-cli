"""Deploy-time Argo CD Application overrides carry the homelab hosts the repository never holds (#1290)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from syrupy.assertion import SnapshotAssertion

from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.argocd_overrides import (
    ApplicationSource,
    application_patch,
    application_source,
    host_patches,
    render_at_revision,
)
from tests.support.fakes.git import GitFake
from tests.support.fakes.process import ProcessAnswer, ProcessCall

# The configured domain has to differ from the repository's placeholder, example.com, for a
# substitution to show; example.org is reserved for documentation by RFC 2606 like example.com.
DOMAIN = "example.org"

RENDERED = """\
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: chat
  namespace: llm
spec:
  rules:
    - host: chat.example.com
    - host: example.com
    - host: "*.example.com"
  tls:
    - hosts:
        - chat.example.com
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: dashboard
  namespace: kube-system
spec:
  routes:
    - match: Host(`traefik.example.com`) && PathPrefix(`/dashboard`)
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: local
  namespace: llm
spec:
  rules:
    - host: localhost
---
apiVersion: v1
kind: Service
metadata:
  name: chat
  namespace: llm
"""


def _decoded(patches: list[dict]) -> list[tuple[dict, list[dict]]]:
    return [(p["target"], json.loads(p["patch"])) for p in patches]


def test_each_placeholder_host_is_checked_then_set_to_the_configured_domain() -> None:
    ingress = {"group": "networking.k8s.io", "version": "v1", "kind": "Ingress"}
    route = {"group": "traefik.io", "version": "v1alpha1", "kind": "IngressRoute"}
    assert _decoded(host_patches(RENDERED, DOMAIN)) == [
        (
            {**ingress, "name": "chat", "namespace": "llm"},
            [
                {"op": "test", "path": "/spec/rules/0/host", "value": "chat.example.com"},
                {"op": "replace", "path": "/spec/rules/0/host", "value": "chat.example.org"},
                {"op": "test", "path": "/spec/rules/1/host", "value": "example.com"},
                {"op": "replace", "path": "/spec/rules/1/host", "value": "example.org"},
                {"op": "test", "path": "/spec/rules/2/host", "value": "*.example.com"},
                {"op": "replace", "path": "/spec/rules/2/host", "value": "*.example.org"},
                {"op": "test", "path": "/spec/tls/0/hosts/0", "value": "chat.example.com"},
                {"op": "replace", "path": "/spec/tls/0/hosts/0", "value": "chat.example.org"},
            ],
        ),
        (
            {**route, "name": "dashboard", "namespace": "kube-system"},
            [
                {
                    "op": "test",
                    "path": "/spec/routes/0/match",
                    "value": "Host(`traefik.example.com`) && PathPrefix(`/dashboard`)",
                },
                {
                    "op": "replace",
                    "path": "/spec/routes/0/match",
                    "value": "Host(`traefik.example.org`) && PathPrefix(`/dashboard`)",
                },
            ],
        ),
    ]


def test_a_domain_that_is_not_a_hostname_is_refused() -> None:
    with pytest.raises(KubernetesContextError, match="Invalid domain name"):
        host_patches(RENDERED, "not a domain")


def test_the_patch_sets_the_kustomize_patches_of_the_application_source(
    snapshot: SnapshotAssertion,
) -> None:
    patches = host_patches(RENDERED, DOMAIN)
    assert patches == snapshot
    assert application_patch(patches) == {"spec": {"source": {"kustomize": {"patches": patches}}}}


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ({"sources": [{"repoURL": "https://example.com/repo"}]}, "several sources"),
        ({"source": {"path": "k8s/x"}}, "names no spec.source.repoURL"),
    ],
)
def test_an_application_the_overrides_cannot_follow_is_refused_by_name(
    spec: dict, message: str
) -> None:
    printed = json.dumps({"metadata": {"name": "ingress"}, "spec": spec})
    with pytest.raises(KubernetesContextError, match=f"Application 'ingress' .*{message}"):
        application_source(printed)


@pytest.mark.parametrize("field", ["repo_url", "revision"])
def test_a_revision_or_repository_from_the_cluster_is_never_read_as_a_git_option(
    tmp_path: Path, field: str, git_fake: GitFake
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    marker = tmp_path / "marker"
    option = f"--upload-pack=touch {marker}; git-upload-pack"
    fields = {"repo_url": ".", "revision": "main", "path": "k8s/app", field: option}
    hostile = ApplicationSource(**fields)

    def _answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if "fetch" in call.argv:
            assert "--end-of-options" in call.argv
            return subprocess.CompletedProcess(
                list(call.argv), 128, "", "fatal: repository not found"
            )
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    git_fake.answer(lambda _call: True, ProcessAnswer(side_effect=_answer))

    with pytest.raises(KubernetesContextError) as raised:
        render_at_revision(hostile, repo / "work", _guarded_run)
    assert raised.value.error_code == "K8S_CONTEXT_ERROR"
    assert not marker.exists()


def test_an_applications_source_is_read_from_its_kubectl_json() -> None:
    printed = json.dumps(
        {
            "spec": {
                "source": {
                    "repoURL": "https://example.com/repo",
                    "targetRevision": "main",
                    "path": "k8s/x",
                }
            }
        }
    )
    assert application_source(printed) == ApplicationSource(
        "https://example.com/repo", "main", "k8s/x"
    )


def _guarded_run(
    cmd: list[str],
    *,
    check: bool = False,
    capture: bool = True,
    timeout: float,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """A runner as `deploy-stack` gives `render_at_revision`: it starts the command with
    `run_subprocess`, so the environment of the caller passes the guard of
    `build_subprocess_env`."""
    return run_subprocess(cmd, check=check, capture_output=capture, timeout=timeout, env=env)


def test_an_application_renders_what_its_revision_holds(tmp_path: Path, git_fake: GitFake) -> None:
    canned = (
        "apiVersion: networking.k8s.io/v1\n"
        "kind: Ingress\n"
        "metadata:\n"
        "  name: chat\n"
        "spec:\n"
        "  rules:\n"
        "    - host: chat.example.com\n"
    )

    def _answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if len(call.argv) > 1 and call.argv[1] == "kustomize":
            return subprocess.CompletedProcess(list(call.argv), 0, canned, "")
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    git_fake.answer(lambda _call: True, ProcessAnswer(side_effect=_answer))
    rendered = render_at_revision(
        ApplicationSource("https://example.com/repo", "main", "k8s/app"),
        tmp_path / "work",
        _guarded_run,
    )
    assert [d["spec"]["rules"] for d in yaml.safe_load_all(rendered)] == [
        [{"host": "chat.example.com"}]
    ]


def test_only_the_fetch_gets_the_ssh_option_and_every_command_gets_only_the_prompt_switch(
    tmp_path: Path,
) -> None:
    """The SSH option is an argument of `git fetch`, the one command that opens an SSH
    connection, and the environment of each command holds `GIT_TERMINAL_PROMPT=0` and no other
    key (#2483)."""
    started: list[tuple[list[str], dict[str, str] | None]] = []

    def record(
        cmd: list[str], *, env: dict[str, str] | None = None, **_: object
    ) -> subprocess.CompletedProcess[str]:
        started.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    source = ApplicationSource("ssh://git@example.com/repository.git", "main", "k8s/app")
    render_at_revision(source, tmp_path / "work", record)

    fetch = next(cmd for cmd, _ in started if "fetch" in cmd)
    before_subcommand = fetch[: fetch.index("fetch")]
    assert (
        [fetch[at + 1] for at, word in enumerate(fetch) if word == "-c"],
        "-c" in before_subcommand,
        [cmd for cmd, _ in started if "-c" in cmd] == [fetch],
        [env for _, env in started],
    ) == (
        ["core.sshCommand=ssh -o BatchMode=yes"],
        True,
        True,
        [{"GIT_TERMINAL_PROMPT": "0"}] * len(started),
    )


@pytest.mark.parametrize(
    ("revision", "path", "message"),
    [("main", "../outside", "leaves its repository"), ("missing", "k8s/app", "git -C")],
)
def test_a_revision_that_cannot_render_is_refused(
    tmp_path: Path, revision: str, path: str, message: str, git_fake: GitFake
) -> None:
    def _answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if "fetch" in call.argv and "missing" in call.argv:
            return subprocess.CompletedProcess(
                list(call.argv), 128, "", "fatal: couldn't find remote ref missing"
            )
        return subprocess.CompletedProcess(list(call.argv), 0, "", "")

    git_fake.answer(lambda _call: True, ProcessAnswer(side_effect=_answer))
    with pytest.raises(KubernetesContextError, match=message):
        render_at_revision(
            ApplicationSource("https://example.com/repo", revision, path),
            tmp_path / "work",
            _guarded_run,
        )
