"""Tests verifying third-party telemetry, phone-home, and update checks are disabled."""

import json
from typing import Any

from devops_cli.core.templating import render_json_template
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"

# What turns off OpenSpec's PostHog events and its npm registry check, besides DO_NOT_TRACK=1,
# which stops both on its own: OPENSPEC_TELEMETRY=0 does too, and OPENSPEC_NO_UPDATE_CHECK=1
# stops the registry check alone.
OPENSPEC_OPT_OUTS = {
    "DO_NOT_TRACK": "1",
    "OPENSPEC_TELEMETRY": "0",
    "OPENSPEC_NO_UPDATE_CHECK": "1",
}


def _rendered_devcontainer_template() -> dict[str, Any]:
    """The devcontainer a project scaffolded from the packaged template gets."""
    rendered: dict[str, Any] = json.loads(
        render_json_template(
            "devcontainer.json.j2",
            project_name="demo",
            python_version="3.14",
            image=None,
            published=False,
            home_volume=None,
            minikube=False,
        )
    )
    return rendered


def test_a_rendered_devcontainer_template_omits_claude_code_nonessential_traffic() -> None:
    """The devcontainer template omits CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC so remote sessions work."""
    env = _rendered_devcontainer_template()["containerEnv"]
    assert "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC" not in env


def test_a_scaffolded_devcontainer_opts_out_of_openspec_telemetry_and_its_update_check() -> None:
    """OpenSpec sends events to a PostHog proxy and asks the npm registry for a newer release on
    every `validate`, `list`, `update` and `version --check`, unless the environment says not to."""
    env = _rendered_devcontainer_template()["containerEnv"]

    assert {key: env.get(key) for key in OPENSPEC_OPT_OUTS} == OPENSPEC_OPT_OUTS
