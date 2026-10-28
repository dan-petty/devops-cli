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
