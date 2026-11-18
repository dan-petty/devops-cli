"""Each image build reads and writes its own `gha` cache scope: the `test-tree` row (#4928).

All image builds of `ci.yml`, `release.yml` and `service-image-test.yml` used the default `buildkit`
scope, so each `cache-to` replaced the cache index of the other images. These checks read the three
workflows and name each entry that lacks a scope, and each entry whose scope is not its target.
"""

from __future__ import annotations

from typing import Any, Final

import yaml

from tests.support.paths import REPO_ROOT

_WORKFLOWS: Final[tuple[str, ...]] = (
    ".github/workflows/ci.yml",
    ".github/workflows/release.yml",
    ".github/workflows/service-image-test.yml",
)
_CACHE_KEYS: Final[tuple[str, ...]] = ("cache-from", "cache-to")


def _options(value: str) -> dict[str, str]:
    """The `key=value` options of one cache entry."""
    return dict(part.split("=", 1) for part in value.split(",") if "=" in part)


def _image_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """The `with` mapping of each step that builds `./Dockerfile`."""
    steps: list[dict[str, Any]] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            options = step.get("with") or {}
            if options.get("file") == "./Dockerfile":
                steps.append(options)
    return steps


def check_each_image_build_cache_entry_names_a_scope() -> None:
    """Each `type=gha` entry of an image build names a scope, with its file and line."""
    failures: list[str] = []
    for name in _WORKFLOWS:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith(tuple(f"{key}:" for key in _CACHE_KEYS)):
                continue
            value = stripped.split(":", 1)[1].strip()
            if "type=gha" in value and "scope" not in _options(value):
                failures.append(f"{name}:{number}: {stripped} names no scope")
    assert not failures, "\n".join(failures)


def check_each_image_build_cache_entry_uses_its_target_scope() -> None:
    """Each `gha` entry of an image build names its target, and a write exports `mode=max`."""
    failures: list[str] = []
    for name in _WORKFLOWS:
        workflow = yaml.safe_load((REPO_ROOT / name).read_text(encoding="utf-8"))
        for step in _image_steps(workflow):
            target = str(step.get("target", "service"))
            for key in _CACHE_KEYS:
                value = step.get(key)
                if value is None:
                    continue
                options = _options(str(value))
                if options.get("type") != "gha":
                    continue
                if options.get("scope") != target:
                    failures.append(f"{name}: target {target} has {key} {value}")
                if key == "cache-to" and options.get("mode") != "max":
                    failures.append(f"{name}: cache-to of {target} has mode {options.get('mode')}")
    assert not failures, "\n".join(failures)
