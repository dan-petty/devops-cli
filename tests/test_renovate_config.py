"""The Renovate configuration covers the image tags that the manifests under `k8s/` pin."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

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

    assert patterns


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
