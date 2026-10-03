"""Unit tests for Checkov IaC static policy scanner."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from devops_cli.security.checkov import _run_native_fallback_iac_checks, run_checkov_scan


def test_fallback_iac_checks_dockerfile(tmp_path: Path) -> None:
    dockerfile = tmp_path / "Dockerfile"
    dockerfile.write_text("FROM alpine:latest\nRUN apk add curl\n", encoding="utf-8")

    findings = _run_native_fallback_iac_checks(tmp_path)
    assert len(findings) >= 2  # :latest tag and missing non-root USER
    titles = [f.title for f in findings]
    assert any("latest" in t for t in titles)
    assert any("root" in t for t in titles)


def test_fallback_iac_checks_k8s_privileged(tmp_path: Path) -> None:
    k8s_file = tmp_path / "deployment.yaml"
    k8s_file.write_text(
        """apiVersion: apps/v1
kind: Deployment
metadata:
  name: test
spec:
  template:
    spec:
      containers:
      - name: test
        securityContext:
          privileged: true
""",
        encoding="utf-8",
    )

    findings = _run_native_fallback_iac_checks(tmp_path)
    assert any(f.severity == "CRITICAL" and "Privileged" in f.title for f in findings)


def test_run_checkov_scan_list_output(tmp_path: Path) -> None:
    """Verify checkov list output parsing with severity and location extraction."""
    fake_output = json.dumps(
        [
            {
                "results": {
                    "failed_checks": [
                        {
                            "check_id": "CKV_AWS_1",
                            "check_name": "CRITICAL S3 bucket has public read policy",
                            "file_path": "/main.tf",
                            "file_line_range": [10, 20],
                            "guideline": "Restrict public access to S3.",
                        },
                        {
                            "check_id": "CKV_AWS_2",
                            "check_name": "LOW S3 bucket tagging missing",
                            "file_path": "",
                            "file_line_range": [],
                            "guideline": "",
                        },
                    ]
                }
            }
        ]
    )
    mock_proc = MagicMock(stdout=fake_output)
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings = run_checkov_scan(tmp_path, framework="terraform")
        assert len(findings) == 2
        assert findings[0].severity == "CRITICAL"
        assert findings[0].location == "main.tf:10"


def test_run_checkov_scan_single_dict_output(tmp_path: Path) -> None:
    """Verify checkov single dictionary output format parsing."""
    single_dict_output = json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_DOCKER_1",
                        "check_name": "Ensure container has healthcheck",
                        "file_path": "/Dockerfile",
                        "file_line_range": [1, 2],
                        "guideline": "Add HEALTHCHECK instruction.",
                    }
                ]
            }
        }
    )
    mock_proc = MagicMock(stdout=single_dict_output)
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings_dict = run_checkov_scan(tmp_path)
        assert len(findings_dict) == 1


def test_run_checkov_scan_error_and_empty_output(tmp_path: Path) -> None:
    """Verify checkov handling of invalid json, empty stdout, and exceptions."""
    with patch("shutil.which", return_value="/usr/local/bin/checkov"):
        # Invalid JSON
        with patch("subprocess.run", return_value=MagicMock(stdout="invalid json checkov output")):
            assert isinstance(run_checkov_scan(tmp_path), list)

        # Empty output
        with patch("subprocess.run", return_value=MagicMock(stdout="")):
            assert len(run_checkov_scan(tmp_path)) == 0

        # Exception fallback
        with patch("subprocess.run", side_effect=Exception("Execution failed")):
            assert isinstance(run_checkov_scan(tmp_path), list)


def test_run_checkov_scan_missing_binary(tmp_path: Path) -> None:
    """Verify graceful handling when checkov binary is not in PATH."""
    with patch("shutil.which", return_value=None):
        findings_nobin = run_checkov_scan(tmp_path)
        assert isinstance(findings_nobin, list)


def test_run_checkov_scan_nonzero_exit_with_findings(tmp_path: Path) -> None:
    """Verify checkov scan parses findings even when checkov CLI exits non-zero (failed checks found)."""
    fake_output = json.dumps(
        {
            "results": {
                "failed_checks": [
                    {
                        "check_id": "CKV_AWS_1",
                        "check_name": "S3 bucket has public read policy",
                        "file_path": "/main.tf",
                        "file_line_range": [10, 20],
                        "guideline": "Restrict public access.",
                    }
                ]
            }
        }
    )
    # Checkov returns exit code 1 when failed checks exist
    mock_proc = subprocess.CompletedProcess(
        args=["checkov", "-d", str(tmp_path), "-o", "json"],
        returncode=1,
        stdout=fake_output,
        stderr="",
    )
    with (
        patch("shutil.which", return_value="/usr/local/bin/checkov"),
        patch("subprocess.run", return_value=mock_proc),
    ):
        findings = run_checkov_scan(tmp_path)
        assert len(findings) == 1
        assert findings[0].location == "main.tf:10"
        assert "[CKV_AWS_1]" in findings[0].title


_PINNED = "python:3.12-slim@sha256:" + "a" * 64

_DOCKERFILES: dict[str, str] = {
    "platform-flag": "FROM --platform=$BUILDPLATFORM python:latest AS build\nUSER 1000\n",
    "untagged": "FROM alpine\nUSER 1000\n",
    "lowercase-user": "FROM python:3.12-slim\nuser nobody\n",
    "stage-alias": "FROM python:3.12-slim AS base\nFROM base AS b\nFROM b\nUSER 1\n",
    "digest-pinned": "FROM python:latest@sha256:" + "a" * 64 + "\nUSER 1\n",
    "scratch-and-arg": "ARG BASE=python:3.12\nFROM $BASE AS build\nFROM scratch\nUSER 1\n",
    "registry-port": "FROM example.com:5000/team/app\nUSER 1\n",
    "registry-port-tagged": "FROM example.com:5000/team/app:1.2\nUSER 1\n",
    # A heredoc body is not instructions: Python's `from x import y` is no FROM, nginx's `user` no USER.
    "python-heredoc": (
        f"FROM {_PINNED}\nRUN python3 - <<'PY'\nfrom pathlib import Path\n"
        "from __future__ import annotations\nPY\nUSER 1000\n"
    ),
    "tab-heredoc": "FROM python:3.12\nRUN <<-EOF\n\tfrom os import sep\n\tEOF\nUSER 1\n",
    "two-heredocs": (
        'FROM python:3.12\nCOPY <<one <<"two" /app/\nfrom a import b\none\n'
        "from c import d\ntwo\nUSER 1\n"
    ),
    "nginx-heredoc": "FROM nginx:1.27.0\nCOPY <<EOF /etc/nginx/nginx.conf\nuser  nginx;\nEOF\n",
    "onbuild-heredoc": "FROM python:3.12\nONBUILD RUN <<EOF\nfrom a import b\nEOF\nUSER 1\n",
    # A continuation line belongs to the instruction it continues; comments inside are skipped.
    "continued-run": f'FROM {_PINNED}\nRUN python3 -c "\\\nfrom os import environ"\nUSER 1000\n',
    "continued-from-pinned": (
        f"FROM --platform=$BUILDPLATFORM \\\n    {_PINNED} AS build\nFROM build\nUSER 1000\n"
    ),
    "continued-from-latest": "FROM \\\n  # the base\n  python:latest\nUSER \\\n  1000\n",
    "continued-from-commented": "FROM \\\n  # the base\n  python:3.12\nUSER 1000\n",
    "escape-backtick": (
        "# escape=`\nFROM `\n    mcr.microsoft.com/windows/nanoserver\nRUN dir C:\\\nUSER app\n"
    ),
    # Only a variable in the name and tag can hide the tag; one in the registry or path cannot.
    "arg-registry-latest": "ARG REGISTRY=docker.io\nFROM ${REGISTRY}/library/python:latest\nUSER 1\n",
    "arg-registry-untagged": "ARG REGISTRY=docker.io\nFROM ${REGISTRY:-docker.io}/python\nUSER 1\n",
    "arg-tag-or-image": (
        "ARG TAG=3.12\nARG IMAGE=python:3.12\nFROM python:${TAG}\n"
        "FROM ${IMAGE:-docker.io/python}\nFROM $IMAGE\nUSER 1\n"
    ),
}


def test_fallback_dockerfile_reads_from_flags_tags_digests_stages_and_user(tmp_path: Path) -> None:
    """A FROM is unpinned when it has no digest and no tag or `latest`; USER is case-insensitive.

    Instructions are read as Docker reads them: continued across lines, and never from a heredoc.
    Each Dockerfile maps to the lines flagged for `latest` and the number of root findings.
    """
    results: dict[str, tuple[list[int], int]] = {}
    for name, content in _DOCKERFILES.items():
        dockerfile = tmp_path / name / "Dockerfile"
        dockerfile.parent.mkdir()
        dockerfile.write_text(content, encoding="utf-8")
        findings = _run_native_fallback_iac_checks(dockerfile)
        results[name] = (
            [int(f.location.rsplit(":", 1)[1]) for f in findings if "latest" in f.title],
            sum("root" in f.title for f in findings),
        )

    assert results == {
        "platform-flag": ([1], 0),
        "untagged": ([1], 0),
        "lowercase-user": ([], 0),
        "stage-alias": ([], 0),
        "digest-pinned": ([], 0),
        "scratch-and-arg": ([], 0),
        "registry-port": ([1], 0),
        "registry-port-tagged": ([], 0),
        "python-heredoc": ([], 0),
        "tab-heredoc": ([], 0),
        "two-heredocs": ([], 0),
        "nginx-heredoc": ([], 1),
        "onbuild-heredoc": ([], 0),
        "continued-run": ([], 0),
        "continued-from-pinned": ([], 0),
        "continued-from-latest": ([1], 0),
        "continued-from-commented": ([], 0),
        "escape-backtick": ([2], 0),
        "arg-registry-latest": ([2], 0),
        "arg-registry-untagged": ([2], 0),
        "arg-tag-or-image": ([], 0),
    }


_PRIVILEGED_MANIFESTS: dict[str, str] = {
    "daemonset.yaml": """apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: feature-discovery
spec:
  template:
    spec:
      containers:
        - name: worker
          image: example.com/worker:1
          securityContext:
            privileged: true
""",
    "cronjob.yaml": """apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup
spec:
  schedule: "0 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          initContainers:
            - name: prepare
              image: example.com/prepare:1
          containers:
            - name: backup
              image: example.com/backup:1
              securityContext:
                privileged: true
""",
    "pod.yaml": """apiVersion: v1
kind: Pod
metadata:
  name: debug
spec:
  containers:
    - name: shell
      image: example.com/shell:1
      securityContext:
        privileged:   True
""",
    "multi.yaml": """apiVersion: v1
kind: Service
metadata:
  name: db
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: db
spec:
  template:
    spec:
      containers:
        - name: db
          image: example.com/db:1
          securityContext:
            privileged: false
        - name: sidecar
          image: example.com/sidecar:1
          securityContext:
            privileged: true
""",
    # `kubectl get -o yaml` writes a List; an OpenShift Template keeps its resources in `objects`.
    "export.yaml": """apiVersion: v1
kind: List
items:
  - apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: web
    spec:
      template:
        spec:
          containers:
            - name: web
              image: example.com/web:1
              securityContext:
                privileged: true
metadata:
  resourceVersion: ""
""",
    "template.yaml": """apiVersion: template.openshift.io/v1
kind: Template
metadata:
  name: debug
objects:
  - apiVersion: v1
    kind: Pod
    metadata:
      name: debug
    spec:
      containers:
        - name: shell
          image: example.com/shell:1
          securityContext:
            privileged: true
parameters:
  - name: NAME
""",
    "settings.yaml": "feature:\n  privileged: true\n",
    "chart-template.yaml": (
        "kind: Pod\nspec:\n  containers: {{ .Values.containers }}\n"
        "      securityContext:\n        privileged: yes\n"
    ),
}


def test_fallback_k8s_flags_privileged_containers_in_every_pod_spec(tmp_path: Path) -> None:
    """Every workload kind's pod spec is read; YAML that will not parse falls back to a line match."""
    for name, content in _PRIVILEGED_MANIFESTS.items():
        (tmp_path / name).write_text(content, encoding="utf-8")

    locations = sorted(
        f.location
        for f in _run_native_fallback_iac_checks(tmp_path)
        if f.title == "Privileged container execution allowed"
    )

    assert locations == [
        "chart-template.yaml:5",
        "cronjob.yaml:18",
        "daemonset.yaml:12",
        "export.yaml:15",
        "multi.yaml:21",
        "pod.yaml:10",
        "template.yaml:15",
    ]


def test_fallback_k8s_matches_yaml_nested_too_deep_to_walk_line_by_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """YAML nested deeper than the composer can recurse is matched line by line.

    The RecursionError would otherwise end the whole fallback, and every IaC finding with it.
    The pure-Python loader recurses per level; libyaml only overflows far deeper.
    """
    from devops_cli.security import checkov

    monkeypatch.setattr(checkov, "_YAML_LOADER", yaml.SafeLoader)
    depth = 1500
    nested = "kind: List\nitems: " + "[{items: " * depth + "[]" + "}]" * depth + "\n"
    (tmp_path / "deep.yaml").write_text(nested + "---\n" + _PRIVILEGED_MANIFESTS["pod.yaml"])
    (tmp_path / "daemonset.yaml").write_text(_PRIVILEGED_MANIFESTS["daemonset.yaml"])

    locations = sorted(f.location for f in _run_native_fallback_iac_checks(tmp_path))

    assert locations == ["daemonset.yaml:12", "deep.yaml:13"]


def test_fallback_k8s_walks_each_aliased_resource_once(tmp_path: Path) -> None:
    """Anchors fanned out through `items` are walked once each, so a 2 KB file finishes (#957).

    Composed YAML shares an aliased node, so a walk that followed every reference took time
    exponential in the alias depth: nine levels of ten references never returned.
    """
    pod = "{kind: Pod, spec: {containers: [{name: shell, securityContext: {privileged: true}}]}}"
    lines = ["kind: List", f"x0: &l0 [{pod}]"]
    lines += [
        f"x{i}: &l{i} [" + ", ".join([f"{{kind: List, items: *l{i - 1}}}"] * 10) + "]"
        for i in range(1, 10)
    ]
    lines.append("items: *l9")
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "fan.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert [f.location for f in _run_native_fallback_iac_checks(manifests)] == ["fan.yaml:2"]


@pytest.mark.skipif(not yaml.__with_libyaml__, reason="PyYAML is built without libyaml")
def test_fallback_k8s_composes_with_libyaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """libyaml's loader composes a large manifest several times faster, with the same line marks."""
    loaders: list[type] = []
    compose_all = yaml.compose_all

    def spy(stream: str, Loader: type) -> Iterator[yaml.Node]:  # noqa: N803
        loaders.append(Loader)
        return compose_all(stream, Loader=Loader)

    monkeypatch.setattr(yaml, "compose_all", spy)
    # A directory of its own: tmp_path also holds the test config's YAML.
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "pod.yaml").write_text(_PRIVILEGED_MANIFESTS["pod.yaml"])

    locations = [f.location for f in _run_native_fallback_iac_checks(manifests)]

    assert (loaders, locations) == ([yaml.CSafeLoader], ["pod.yaml:10"])
