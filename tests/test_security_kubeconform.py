"""The kubeconform adapter reads the one report object that the pinned kubeconform writes (#2214).

The runs are kubeconform 0.8.0's, recorded on 2026-10-28 over `_MANIFESTS`: the run with the command
of the adapter in `tests/fixtures/scanner_runs/runs_with_findings.json`, and a run with `-verbose
-skip ConfigMap` in `tests/fixtures/scanner_runs/kubeconform_verbose_run.json`. Without `-verbose`,
kubeconform lists only the resources that are invalid or that it could not validate.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.ai.review_schema import Finding
from devops_cli.security.base import ScanOutcome
from devops_cli.security.kubeconform import KubeconformScanner, run_kubeconform_validation
from devops_cli.tools_lock import load_tools_lock
from tests.support.fakes.scanners import ScannerFake
from tests.support.fakes.tool_executor import ToolAnswer
from tests.support.paths import FIXTURES

# The manifest of both recorded runs: a valid Deployment, a Service whose port is a string, a
# ConfigMap with a key that its schema does not allow, and a custom resource with no schema.
_MANIFESTS = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: shop
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: nginx:1.27.0
---
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: shop
spec:
  selector:
    app: web
  ports:
    - port: "http"
      targetPort: 8080
---
apiVersion: example.com/v1
kind: Widget
metadata:
  name: blue
spec:
  size: 3
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: settings
  namespace: shop
data:
  mode: fast
replicas: 3
"""

_SCHEMA = (
    "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/master/master-standalone-strict"
)

_WIDGET = Finding(
    severity="HIGH",
    location="k8s/app.yaml:Widget/blue",
    title="[Kubeconform statusError] Widget 'blue' could not be validated",
    description="could not find schema for Widget",
    fix="Correct the resource so that kubeconform can read it, or give kubeconform a schema for its kind.",
    confidence_score=None,
)
_CONFIGMAP = Finding(
    severity="HIGH",
    location="k8s/app.yaml:ConfigMap/settings",
    title="[Kubeconform statusInvalid] ConfigMap 'settings' does not match its schema",
    description=(
        "problem validating schema. Check JSON formatting: jsonschema validation failed with "
        f"'{_SCHEMA}/configmap-v1.json#' - at '': additional properties 'replicas' not allowed"
    ),
    fix="Correct the resource to match its schema: additional properties 'replicas' not allowed.",
    confidence_score=None,
)
_SERVICE = Finding(
    severity="HIGH",
    location="k8s/app.yaml:Service/web",
    title="[Kubeconform statusInvalid] Service 'web' does not match its schema",
    description=(
        "problem validating schema. Check JSON formatting: jsonschema validation failed with "
        f"'{_SCHEMA}/service-v1.json#' - at '/spec/ports/0/port': got string, want integer"
    ),
    fix="Correct the resource to match its schema: /spec/ports/0/port: got string, want integer.",
    confidence_score=None,
)


def _manifests(tmp_path: Path, git: Callable[..., None]) -> Path:
    """The directory `k8s` of a checkout, holding the manifest of the recorded runs."""
    tree = tmp_path / "tree"
    manifests = tree / "k8s"
    manifests.mkdir(parents=True)
    git(tree, "init", "-q")
    (manifests / "app.yaml").write_text(_MANIFESTS, encoding="utf-8")
    return manifests


def test_kubeconform_reports_each_resource_it_finds_invalid_or_cannot_validate(
    scanner_fake: ScannerFake, tmp_path: Path, git: Callable[..., None]
) -> None:
    """kubeconform writes one report object with a `resources` list. Each resource with
    `statusInvalid` or `statusError` is one HIGH finding at its manifest and object, in the order
    of the report."""
    manifests = _manifests(tmp_path, git)
    recorded = scanner_fake.script_run_with_findings("kubeconform", tree=manifests.parent)

    outcome = run_kubeconform_validation(manifests)

    assert (scanner_fake.runs, outcome.status, outcome.findings) == (
        [recorded],
        "ran",
        [_WIDGET, _CONFIGMAP, _SERVICE],
    )


def test_kubeconform_gives_no_finding_for_a_valid_or_skipped_resource(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """A `-verbose` report also lists the resources that are valid and those that kubeconform
    skipped. Neither is a finding."""
    manifests = _manifests(tmp_path, git)
    run = json.loads((FIXTURES / "scanner_runs" / "kubeconform_verbose_run.json").read_text())
    report = json.loads(run["stdout"].replace("{tree}", str(manifests.parent)))

    findings = KubeconformScanner().parse_output(report, manifests)

    assert run["version"] == load_tools_lock().tools()["kubeconform"].version
    assert [status["status"] for status in report["resources"]] == [
        "statusSkipped",
        "statusError",
        "statusInvalid",
        "statusValid",
    ]
    assert findings == [_WIDGET, _SERVICE]


def test_a_resource_that_kubeconform_cannot_read_is_named_by_its_manifest(
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """kubeconform writes an empty kind and name for a file that is not YAML, so the finding names
    the manifest alone."""
    manifests = _manifests(tmp_path, git)
    report = {
        "resources": [
            {
                "filename": str(manifests / "app.yaml"),
                "kind": "",
                "name": "",
                "version": "",
                "status": "statusError",
                "msg": "error unmarshalling resource: error converting YAML to JSON",
            }
        ]
    }

    findings = KubeconformScanner().parse_output(report, manifests)

    assert [(finding.location, finding.title) for finding in findings] == [
        ("k8s/app.yaml", "[Kubeconform statusError] k8s/app.yaml could not be validated")
    ]


def test_kubeconform_that_finds_nothing_is_a_clean_scan(
    scanner_fake: ScannerFake, tmp_path: Path
) -> None:
    """With no invalid resource, kubeconform writes an empty `resources` list and exits 0."""
    scanner_fake.script("kubeconform", ToolAnswer(stdout='{\n  "resources": []\n}\n'))

    outcome = run_kubeconform_validation(tmp_path)

    assert outcome == ScanOutcome("ran", [])


def test_a_missing_kubeconform_is_unavailable_and_runs_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """kubeconform is pinned, so its adapter has no hand-written checks: with no kubeconform on
    PATH, the scan is unavailable and has no findings, also for a manifest with no `kind`."""
    no_scanners = tmp_path / "no-scanners"
    no_scanners.mkdir()
    monkeypatch.setenv("PATH", str(no_scanners))
    (tmp_path / "bad.yaml").write_text("apiVersion: apps/v1\nmetadata:\n  name: x\n")

    outcome = run_kubeconform_validation(tmp_path)

    assert outcome == ScanOutcome("unavailable", [], "Binary 'kubeconform' not found on PATH")
