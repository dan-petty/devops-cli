"""The setting `infra.repos`: the infra repos of `devops infra`, each with its agent access level
(#5121)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from devops_cli.config.settings import InfraConfig, load_settings
from devops_cli.infra.access import AgentAccess


def test_a_repo_entry_with_no_agent_access_reads_as_none(config: Callable[..., Path]) -> None:
    config(infra={"repos": [{"repo": "example-org/infra"}]})

    entry = load_settings().infra.repos[0]

    assert (entry.agent_access, entry.ssh_key_prefix, entry.kube_context, entry.path) == (
        AgentAccess.NONE,
        "ansible",
        None,
        None,
    )


def test_a_repo_entry_keeps_the_level_that_a_person_set(config: Callable[..., Path]) -> None:
    config(infra={"repos": [{"repo": "example-org/infra", "agent_access": "full"}]})

    assert load_settings().infra.repos[0].agent_access is AgentAccess.FULL


@pytest.mark.parametrize(
    "repos",
    [
        pytest.param([{"repo": "not a repository"}], id="not-owner-and-name"),
        pytest.param(
            [{"repo": "example-org/infra"}, {"repo": "Example-Org/Infra"}], id="one-repo-twice"
        ),
        pytest.param([{"repo": "example-org/infra", "agent_access": "all"}], id="unknown-level"),
        pytest.param(
            [{"repo": "example-org/infra", "k8s_dir": "k8s"}], id="project-fact-not-a-setting"
        ),
    ],
)
def test_an_invalid_repo_entry_is_refused(repos: list[dict[str, object]]) -> None:
    with pytest.raises(ValidationError) as caught:
        InfraConfig.model_validate({"repos": repos})

    assert [error["loc"][0] for error in caught.value.errors()] == ["repos"]
