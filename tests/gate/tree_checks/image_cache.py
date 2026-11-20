"""Each image build reads its own registry cache, and the release writes it: the `test-tree` row.

All image builds of `ci.yml`, `release.yml` and `service-image-test.yml` used the default `buildkit`
scope, so each `cache-to` replaced the cache index of the other images (#4928). The `gha` exports
then took up to 140 s for each image, and the registry export of the devcontainer took 14 s, so
each image build now reads `ghcr.io/<repository>/<target>:buildcache` (#6404). These checks read
the three workflows and name each `gha` entry, and each entry that does not name the ref of its
target.
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


def _cache_ref(target: str) -> str:
    """The registry ref that holds the build cache of `target`."""
    return f"ghcr.io/${{{{ github.repository }}}}/{target}:buildcache"


def _image_steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """The `with` mapping of each step that builds `./Dockerfile`."""
    steps: list[dict[str, Any]] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            options = step.get("with") or {}
            if options.get("file") == "./Dockerfile":
                steps.append(options)
    return steps


def check_no_cache_entry_uses_the_actions_cache() -> None:
    """No cache entry of the three workflows names `type=gha`, with its file and line."""
    failures: list[str] = []
    for name in _WORKFLOWS:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped.startswith(tuple(f"{key}:" for key in _CACHE_KEYS)):
                continue
            value = stripped.split(":", 1)[1].strip()
            if _options(value).get("type") == "gha":
                failures.append(f"{name}:{number}: {stripped} uses the Actions cache")
    assert not failures, "\n".join(failures)


def check_each_image_build_cache_entry_uses_its_target_ref() -> None:
    """Each cache entry of an image build names the ref of its target, and a write sets `mode=max`."""
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
                if options.get("type") != "registry" or options.get("ref") != _cache_ref(target):
                    failures.append(f"{name}: target {target} has {key} {value}")
                if key == "cache-to" and options.get("mode") != "max":
                    failures.append(f"{name}: cache-to of {target} has mode {options.get('mode')}")
    assert not failures, "\n".join(failures)
