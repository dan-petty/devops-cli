"""Deploy-time Argo CD Application overrides carry the homelab hosts the repository never holds (#1290)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml
from syrupy.assertion import SnapshotAssertion

from devops_cli.core.process import git_reaches_remote, run_subprocess
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


START_PAGE = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: start
  namespace: start
  annotations:
    note: start.example.com
spec:
  template:
    spec:
      initContainers:
        - name: wait
          env:
            - name: TARGET
              value: start.example.com
      containers:
        - name: homepage
          args: ["--host", "start.example.com"]
          env:
            - name: MY_POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
            - name: HOMEPAGE_VAR_DOMAIN
              value: example.com
            - name: PORT
              value: "3000"
            - name: HOMEPAGE_ALLOWED_HOSTS
              value: $(MY_POD_IP):3000,start.example.com
"""


def test_each_placeholder_env_value_is_checked_then_set_to_the_configured_domain() -> None:
    """Only the env values of a Deployment that hold the placeholder change: not a value
    without it, and not the placeholder in an annotation or an argument (#4542)."""
    containers = "/spec/template/spec/containers/0/env"
    init = "/spec/template/spec/initContainers/0/env"
    deployment = {"group": "apps", "version": "v1", "kind": "Deployment"}
    assert _decoded(host_patches(START_PAGE, DOMAIN)) == [
        (
            {**deployment, "name": "start", "namespace": "start"},
            [
                {"op": "test", "path": f"{init}/0/value", "value": "start.example.com"},
                {"op": "replace", "path": f"{init}/0/value", "value": "start.example.org"},
                {"op": "test", "path": f"{containers}/1/value", "value": "example.com"},
                {"op": "replace", "path": f"{containers}/1/value", "value": "example.org"},
                {
                    "op": "test",
                    "path": f"{containers}/3/value",
                    "value": "$(MY_POD_IP):3000,start.example.com",
                },
                {
                    "op": "replace",
                    "path": f"{containers}/3/value",
                    "value": "$(MY_POD_IP):3000,start.example.org",
                },
            ],
        )
    ]


def test_a_deployment_whose_env_values_hold_no_placeholder_gets_no_patch() -> None:
    plain = START_PAGE.replace("example.com", "example.net")
    assert host_patches(plain, DOMAIN) == []


ORIGINS = """\
apiVersion: v1
kind: ConfigMap
metadata:
  name: open-webui-origins
  namespace: llm
  annotations:
    note: chat.example.com
data:
  CORS_ALLOW_ORIGIN: https://chat.example.com;https://homelab.example.com
  MODE: strict
binaryData:
  logo: Y2hhdC5leGFtcGxlLmNvbQ==
"""


def test_each_placeholder_configmap_data_value_is_checked_then_set_to_the_configured_domain() -> (
    None
):
    """Only the data values of a ConfigMap that hold the placeholder change: not a value without
    it, not binary data, and not the placeholder in an annotation (#5306)."""
    cors = "/data/CORS_ALLOW_ORIGIN"
    assert _decoded(host_patches(ORIGINS, DOMAIN)) == [
        (
            {
                "group": "",
                "version": "v1",
                "kind": "ConfigMap",
                "name": "open-webui-origins",
                "namespace": "llm",
            },
            [
                {
                    "op": "test",
                    "path": cors,
                    "value": "https://chat.example.com;https://homelab.example.com",
                },
                {
                    "op": "replace",
                    "path": cors,
                    "value": "https://chat.example.org;https://homelab.example.org",
                },
            ],
        )
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


def _started_commands(
    source: ApplicationSource, workdir: Path
) -> list[tuple[list[str], dict[str, str] | None]]:
    """Each command that `render_at_revision` starts for `source`, with its environment."""
    started: list[tuple[list[str], dict[str, str] | None]] = []

    def record(
        cmd: list[str], *, env: dict[str, str] | None = None, **_: object
    ) -> subprocess.CompletedProcess[str]:
        started.append((cmd, env))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    render_at_revision(source, workdir, record)
    return started


def _config_before_subcommand(cmd: list[str], subcommand: str) -> list[str]:
    """The `-c` values of `cmd` before its git subcommand, in order."""
    before = cmd[: cmd.index(subcommand)]
    return [before[at + 1] for at, word in enumerate(before) if word == "-c"]


def test_only_the_fetch_gets_git_options_and_every_command_gets_only_the_prompt_switch(
    tmp_path: Path,
) -> None:
    """The SSH option and the credential helpers of github.com are arguments of `git fetch`, the
    one command that reaches a remote, and the environment of each command holds
    `GIT_TERMINAL_PROMPT=0` and no other key (#2483, #5294)."""
    source = ApplicationSource("ssh://git@example.com/repository.git", "main", "k8s/app")
    started = _started_commands(source, tmp_path / "work")

    fetch = next(cmd for cmd, _ in started if "fetch" in cmd)
    assert (
        _config_before_subcommand(fetch, "fetch"),
        fetch.count("-c"),
        [cmd for cmd, _ in started if "-c" in cmd] == [fetch],
        [env for _, env in started],
    ) == (
        [
            "core.sshCommand=ssh -o BatchMode=yes",
            "credential.https://github.com.helper=",
            "credential.https://github.com.helper=!gh auth git-credential",
        ],
        3,
        True,
        [{"GIT_TERMINAL_PROMPT": "0"}] * len(started),
    )


def test_a_private_github_repository_is_fetched_with_the_credential_of_the_github_session(
    tmp_path: Path,
) -> None:
    """An Application can name a private repository on github.com (#5294). The fetch names gh as
    the only credential helper of github.com: the empty value first clears the helpers of the
    config files. The fetch reaches a remote, so the process runner gives it the session's token
    as GH_TOKEN, which `gh auth git-credential` reads."""
    source = ApplicationSource("https://github.com/example/private-repository", "main", "k8s/app")
    started = _started_commands(source, tmp_path / "work")

    fetch = next(cmd for cmd, _ in started if "fetch" in cmd)
    helper = "credential.https://github.com.helper="
    assert (
        [
            value.removeprefix(helper)
            for value in _config_before_subcommand(fetch, "fetch")
            if value.startswith(helper)
        ],
        git_reaches_remote(fetch[1:]),
        fetch[-2:],
    ) == (["", "!gh auth git-credential"], True, [source.repo_url, source.revision])


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
