"""Dev Container configuration invariants: what the committed files under `.devcontainer/` hold."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tests.support.paths import REPO_ROOT

DEVCONTAINER = REPO_ROOT / ".devcontainer"


LOCK = REPO_ROOT / "src" / "devops_cli" / "tools_lock" / "tools.lock"


def test_the_image_build_installs_the_tools_with_native_steps_under_usr_local() -> None:
    """The image build gets each tool with a step of Docker or of its package manager, and puts
    the commands in /usr/local/bin and the files of a Python or Node tool in
    /usr/local/share/devops-tools: no custom installer runs, so a tool is on PATH with no setting
    and a rebuild of the image is the way to change it."""
    dockerfile = (DEVCONTAINER / "Dockerfile").read_text(encoding="utf-8")
    lock = tomllib.loads(LOCK.read_text(encoding="utf-8"))

    missing_binary_pins = [
        f"{name} {arch}"
        for name, tool in lock["binary"].items()
        for arch in ("amd64", "arm64")
        for platform in [tool["platforms"][f"linux-{arch}"]]
        if platform["url"] not in dockerfile or platform["sha256"] not in dockerfile
    ]
    unhashed_python = [
        name
        for name, tool in lock["python"].items()
        if f"uv pip sync --require-hashes -p /usr/local/share/devops-tools/{name}/bin/python"
        not in dockerfile.replace("\\\n    ", "")
        or f"COPY src/devops_cli/tools_lock/{tool['requirements']} " not in dockerfile
    ]
    unlocked_npm = [
        name
        for name in lock["npm"]
        if f"cd /opt/{name} && npm ci --ignore-scripts" not in dockerfile
    ]

    assert (
        "install-tools" in dockerfile,
        "sha256sum -c" in dockerfile,
        "COPY --from=tools /out/bin/ /usr/local/bin/" in dockerfile,
        missing_binary_pins,
        unhashed_python,
        unlocked_npm,
    ) == (False, True, True, [], [], [])


def _config_label(path: Path) -> str:
    """Return the path of a config as the repository holds it."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _config_of(path: Path) -> dict[str, object]:
    """Return the config that a `devcontainer.json` holds."""
    return json.loads(path.read_text(encoding="utf-8"))


def _feature_options(config: dict[str, object]) -> dict[str, dict[str, object]]:
    """Return the options of each feature of a config, keyed by the feature id."""
    features = config.get("features")
    if not isinstance(features, dict):
        return {}
    return {
        feature: options if isinstance(options, dict) else {}
        for feature, options in features.items()
    }


def _unresolved_feature_violations(path: Path, config: dict[str, object]) -> list[str]:
    """Return one message for each feature that the lockfile beside the config does not resolve."""
    lock_path = path.with_name("devcontainer-lock.json")
    lock = _config_of(lock_path) if lock_path.is_file() else {}
    resolved = lock.get("features")
    return [
        f"{_config_label(path)}: {feature} has no resolved digest in {lock_path.name}"
        for feature in _feature_options(config)
        if not (
            isinstance(resolved, dict)
            and isinstance(resolved.get(feature), dict)
            and resolved[feature].get("resolved")
        )
    ]


def _devcontainer_configs() -> list[Path]:
    """Return the config of the workspace, of the image and of any other config of the tree."""
    return sorted(DEVCONTAINER.rglob("devcontainer.json"))


def test_the_lockfile_beside_each_devcontainer_config_resolves_its_features() -> None:
    """The image build runs with `--frozen-lockfile`, so a feature that the lockfile beside the
    config does not resolve is a feature that the build cannot install (#3612)."""
    violations = [
        message
        for path in _devcontainer_configs()
        for message in _unresolved_feature_violations(path, _config_of(path))
    ]

    assert violations == []


def test_a_feature_without_a_resolved_digest_is_a_violation(tmp_path: Path) -> None:
    """The reader names each feature that the lockfile beside the config does not resolve
    (#3612)."""
    feature = "ghcr.io/devcontainers/features/docker-in-docker:2"
    path = tmp_path / "devcontainer.json"
    config = {"features": {feature: {}}}

    assert _unresolved_feature_violations(path, config) == [
        f"{path}: {feature} has no resolved digest in devcontainer-lock.json"
    ]
    (tmp_path / "devcontainer-lock.json").write_text(
        json.dumps({"features": {feature: {"resolved": "ghcr.io/example@sha256:0"}}}),
        encoding="utf-8",
    )
    assert _unresolved_feature_violations(path, config) == []
