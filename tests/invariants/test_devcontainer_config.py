"""Dev Container configuration invariants: what the committed files under `.devcontainer/` hold."""

from __future__ import annotations

import json
import tomllib

from tests.support.paths import REPO_ROOT

DEVCONTAINER = REPO_ROOT / ".devcontainer"


def test_a_devcontainer_terminal_runs_the_checkout_devops_before_the_image_copy() -> None:
    """The image installs a copy of devops in /usr/local/bin for child repositories and for the
    first post-create, which runs before the .venv volume holds the checkout. This repository's
    terminals and lifecycle commands put the checkout's .venv/bin first on PATH, so `devops` is
    its editable install and not the copy of the image's commit. The image configuration sets no
    PATH, so a child repository keeps the copy of the image (#2449)."""
    workspace = json.loads((DEVCONTAINER / "devcontainer.json").read_text(encoding="utf-8"))
    image = json.loads((DEVCONTAINER / "image" / "devcontainer.json").read_text(encoding="utf-8"))

    assert (workspace.get("remoteEnv"), image.get("remoteEnv")) == (
        {"PATH": "${containerWorkspaceFolder}/.venv/bin:${containerEnv:PATH}"},
        None,
    )


# The least process limit that leaves room for a burst of VS Code file searches (#3722). Each
# `rg` search starts one thread for each CPU, and a burst of about 100 searches filled the old
# limit of 2048 on 2026-11-05 and 2026-11-06.
MIN_PIDS_LIMIT = 4096


def _pids_limit(run_args: list[str]) -> int | None:
    """Return the value of the `--pids-limit` run argument, or None when it is absent."""
    for index, arg in enumerate(run_args):
        if arg.startswith("--pids-limit="):
            return int(arg.partition("=")[2])
        if arg == "--pids-limit":
            return int(run_args[index + 1])
    return None


def test_the_devcontainer_process_limit_leaves_room_for_a_burst_of_searches() -> None:
    """`runArgs` raises the process limit of the container above the 2048 default of rootless
    Podman, and keeps the GPUs (#3722)."""
    workspace = json.loads((DEVCONTAINER / "devcontainer.json").read_text(encoding="utf-8"))
    run_args = workspace["runArgs"]

    limit = _pids_limit(run_args)
    assert limit is not None, "runArgs holds no --pids-limit"
    assert limit >= MIN_PIDS_LIMIT, f"--pids-limit is {limit}; the minimum is {MIN_PIDS_LIMIT}"
    gpus = run_args.index("--gpus")
    assert run_args[gpus : gpus + 2] == ["--gpus", "all"]


def test_a_low_process_limit_is_below_the_minimum() -> None:
    """The reader sees both spellings of the option, and the old default is under the minimum."""
    assert _pids_limit(["--pids-limit", "2048"]) == 2048 < MIN_PIDS_LIMIT
    assert _pids_limit(["--pids-limit=8192"]) == 8192
    assert _pids_limit(["--gpus", "all"]) is None


def _workspace_and_image_configs() -> tuple[dict[str, object], dict[str, object]]:
    workspace = json.loads((DEVCONTAINER / "devcontainer.json").read_text(encoding="utf-8"))
    image = json.loads((DEVCONTAINER / "image" / "devcontainer.json").read_text(encoding="utf-8"))
    return workspace, image


def test_the_workspace_devcontainer_uses_the_published_image() -> None:
    """The release builds .devcontainer/image/devcontainer.json, and its devcontainer.metadata
    label gives the features, their run options, the remote user and the environment. A second
    copy of the build in the workspace configuration is edited twice and rebuilt on each
    workstation (#4248)."""
    from devops_cli.config.constants import CONST_DEVCONTAINER_PUBLISHED_IMAGE

    workspace, image = _workspace_and_image_configs()
    repeated_env = set(workspace.get("containerEnv") or {}) & set(image["containerEnv"])

    assert workspace.get("image") == CONST_DEVCONTAINER_PUBLISHED_IMAGE
    assert ("build" in workspace, "features" in workspace) == (False, False)
    assert repeated_env == set()
    assert not (DEVCONTAINER / "devcontainer-lock.json").exists()


CACHE_FOLDERS = (".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".uv")


def test_the_workspace_devcontainer_mounts_no_cache_volume() -> None:
    """The workspace and the volumes are on the same Linux disk, so a cache volume gives no
    speed, and every cache folder is in .gitignore (#4248)."""
    workspace, _image = _workspace_and_image_configs()
    targets = {
        part.removeprefix("target=")
        for mount in workspace["mounts"]
        for part in mount.split(",")
        if part.startswith("target=")
    }
    cache_targets = {f"${{containerWorkspaceFolder}}/{name}" for name in CACHE_FOLDERS}

    assert targets & cache_targets == set()
    assert "UV_CACHE_DIR" not in (workspace.get("containerEnv") or {})


DATA_MOUNTS = (
    "source=devops-cli-tmp,target=/tmp,type=volume",
    "source=devops-cli-data,target=${containerWorkspaceFolder}/.data,type=volume",
    "source=global-devcontainer-home,target=/home/vscode,type=volume",
    "source=${localEnv:HOME}${localEnv:USERPROFILE}/.ssh,target=/home/vscode/.ssh,type=bind,"
    "consistency=cached",
)


def test_the_workspace_devcontainer_keeps_the_mounts_that_hold_data() -> None:
    """.data holds agent worktrees and state, the home volume holds the keyring and its copies,
    and .ssh holds the keys. A rebuild without one of these mounts hides that data (#4248)."""
    workspace, _image = _workspace_and_image_configs()

    assert [mount for mount in DATA_MOUNTS if mount not in workspace["mounts"]] == []


def test_the_workspace_devcontainer_aligns_antigravity_and_vscode_customizations() -> None:
    """Antigravity and VS Code get the same extensions and editor settings."""
    workspace, _image = _workspace_and_image_configs()
    customizations = workspace["customizations"]

    assert customizations["antigravity"] == customizations["vscode"]


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
