"""The Renovate configuration covers the image tags that the manifests under `k8s/` pin, and the
chart versions that the Argo CD Applications pin."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

import yaml

from tests.support.paths import REPO_ROOT

_IMAGE_WITH_TAG = re.compile(r"^\s*-?\s*image:\s*\S+:[\w][\w.-]*\s*$", re.MULTILINE)


def _renovate() -> dict[str, Any]:
    return json.loads((REPO_ROOT / ".github" / "renovate.json").read_text(encoding="utf-8"))


def _tracked_k8s_yaml() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "k8s"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [name for name in out.splitlines() if name.endswith((".yaml", ".yml"))]


def test_kubernetes_manager_has_a_file_pattern() -> None:
    """The `kubernetes` manager matches no file by default, so the config must name `k8s/`."""
    patterns = _renovate().get("kubernetes", {}).get("managerFilePatterns", [])

    assert patterns == ["/^k8s/.+\\.ya?ml$/"]


def test_every_manifest_that_pins_an_image_tag_matches_a_pattern() -> None:
    patterns = [
        re.compile(p.strip("/"))
        for p in _renovate().get("kubernetes", {}).get("managerFilePatterns", [])
    ]
    pinned = [
        name
        for name in _tracked_k8s_yaml()
        if _IMAGE_WITH_TAG.search((REPO_ROOT / name).read_text(encoding="utf-8"))
    ]
    unmatched = [name for name in pinned if not any(p.search(name) for p in patterns)]

    assert (bool(pinned), unmatched) == (True, [])


def test_kubernetes_updates_carry_the_infra_label_and_the_chore_prefix() -> None:
    renovate = _renovate()
    rules = [r for r in renovate["packageRules"] if r.get("matchManagers") == ["kubernetes"]]

    assert (renovate["commitMessagePrefix"], [r["labels"] for r in rules]) == (
        "chore(deps):",
        [["type/chore", "scope/infra"]],
    )


def _applications_that_pin_a_chart() -> list[str]:
    """Each tracked file under `k8s/` that holds an Argo CD Application with a Helm chart source."""
    found = []
    for name in _tracked_k8s_yaml():
        documents = yaml.safe_load_all((REPO_ROOT / name).read_text(encoding="utf-8"))
        for document in documents:
            if not isinstance(document, dict) or document.get("kind") != "Application":
                continue
            spec = document.get("spec", {})
            sources = [*([spec["source"]] if "source" in spec else []), *spec.get("sources", [])]
            if any("chart" in source for source in sources):
                found.append(name)
                break
    return found


def test_the_argocd_manager_reads_every_application_that_pins_a_chart() -> None:
    """The `argocd` manager matches no file by default, so a chart pin in an Application gets no
    update pull request unless the config names its file (#1659)."""
    patterns = [
        re.compile(p.strip("/"))
        for p in _renovate().get("argocd", {}).get("managerFilePatterns", [])
    ]
    pinned = _applications_that_pin_a_chart()
    unmatched = [name for name in pinned if not any(p.search(name) for p in patterns)]

    assert (bool(pinned), unmatched) == (True, [])


def test_argocd_updates_carry_the_infra_label_and_leave_the_git_sources_alone() -> None:
    """A chart update carries the labels of a manifest update. Renovate reads a source with no
    chart as a git dependency at `main`, which Argo CD tracks on purpose (ADR 0013), so those
    dependencies are off."""
    rules = [
        {key: value for key, value in rule.items() if key != "description"}
        for rule in _renovate()["packageRules"]
        if rule.get("matchManagers") == ["argocd"]
    ]

    assert sorted(json.dumps(rule, sort_keys=True) for rule in rules) == sorted(
        json.dumps(rule, sort_keys=True)
        for rule in (
            {"matchManagers": ["argocd"], "labels": ["type/chore", "scope/infra"]},
            {"matchManagers": ["argocd"], "matchDatasources": ["git-tags"], "enabled": False},
        )
    )
