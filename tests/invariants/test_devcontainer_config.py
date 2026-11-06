"""Dev Container configuration invariants: what the committed files under `.devcontainer/` hold."""

from __future__ import annotations

import json

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
