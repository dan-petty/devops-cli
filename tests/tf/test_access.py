"""Unit tests for `devops tf` agent access, core budget floor, and reader App credentials (#5320)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from devops_cli.config.defaults import DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import ConfigurationError, TFAccessRefusedError, TFBudgetError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.tf.access import (
    TF_AGENT_ACCESS_KEY,
    TFAccessLevel,
    check_github_core_budget,
    is_github_stack_path,
    prepare_tf_stack_run,
    reader_github_env,
    require_agent_access,
    stack_agent_access,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.keyring import FakeKeyring


def _generate_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")


def test_is_github_stack_path_matches_tf_github_trees(tmp_path: Path) -> None:
    assert (
        is_github_stack_path("tf/github/dan-petty"),
        is_github_stack_path(Path("org/tf/github/dan-petty")),
        is_github_stack_path(tmp_path / "tf" / "github" / "retric-ai"),
        is_github_stack_path("tf/examples/aws"),
        is_github_stack_path(tmp_path / "other" / "github"),
    ) == (True, True, True, False, False)


@pytest.mark.parametrize("action", ["apply", "destroy"])
def test_agent_apply_and_destroy_are_refused_at_plan_level(
    tmp_path: Path, config: Any, agent_caller: None, action: str
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    config(tf={"stacks": [{"path": "tf/github/dan-petty"}]})

    with pytest.raises(TFAccessRefusedError) as caught:
        require_agent_access(stack, action=action)

    assert TF_AGENT_ACCESS_KEY in caught.value.message
    assert "plan" in caught.value.message
    assert action in caught.value.message


def test_agent_apply_and_destroy_allowed_at_apply_level(
    tmp_path: Path, config: Any, agent_caller: None
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    config(tf={"stacks": [{"path": "tf/github/dan-petty", "agent_access": "apply"}]})

    assert load_settings().tf.stacks[0].agent_access is TFAccessLevel.APPLY
    assert require_agent_access(stack, action="apply") is None
    assert require_agent_access(stack, action="destroy") is None


def test_person_apply_and_destroy_pass_at_plan_level(
    tmp_path: Path, config: Any, person_caller: None
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    config(tf={"stacks": [{"path": "tf/github/dan-petty", "agent_access": "plan"}]})

    assert require_agent_access(stack, action="apply") is None
    assert require_agent_access(stack, action="destroy") is None


def test_core_budget_floor_refuses_249_and_allows_250() -> None:
    limiter = get_github_rate_limiter()
    future_reset = time.time() + 1800.0
    limiter.update_quota("core", remaining=249, limit=5000, reset_epoch=future_reset)

    with pytest.raises(TFBudgetError) as caught:
        check_github_core_budget()

    assert "249" in caught.value.message
    assert str(DEFAULT_TF_GITHUB_CORE_BUDGET_FLOOR) in caught.value.message

    limiter.update_quota("core", remaining=250, limit=5000, reset_epoch=future_reset)
    assert check_github_core_budget() is None


def test_agent_plan_mints_reader_token_without_touching_writer_key(
    tmp_path: Path,
    config: Any,
    agent_caller: None,
    keyring_store: FakeKeyring,
    github_api: GitHubApiFake,
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    pem = _generate_pem()
    keyring_store.values["tf_github_reader_private_key"] = pem
    keyring_store.values["service_github_app_private_key"] = "writer-should-not-be-read"
    config(
        tf={
            "stacks": [{"path": "tf/github/dan-petty"}],
            "github_reader": {"app_id": 2001, "installation_id": 77},
        }
    )
    github_api.route(
        "POST",
        "/app/installations/77/access_tokens",
        github_json(
            {
                "token": "ghs_reader_installation_tok",
                "expires_at": "2026-11-25T12:35:00Z",
                "permissions": {"metadata": "read"},
            }
        ),
    )

    child_env = prepare_tf_stack_run(stack, action="plan", dry_run=False)

    assert child_env == {"GITHUB_TOKEN": "ghs_reader_installation_tok"}
    assert "tf_github_reader_private_key" in keyring_store.secret_reads()
    assert "service_github_app_private_key" not in keyring_store.secret_reads()


def test_agent_plan_missing_reader_credentials_refuses_naming_all_three_keys(
    tmp_path: Path,
    config: Any,
    agent_caller: None,
    keyring_store: FakeKeyring,
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    keyring_store.values["service_github_app_private_key"] = _generate_pem()
    config(tf={"stacks": [{"path": "tf/github/dan-petty"}]})

    with pytest.raises(ConfigurationError) as caught:
        prepare_tf_stack_run(stack, action="plan", dry_run=False)

    msg = caught.value.message
    assert "tf.github_reader.app_id" in msg
    assert "tf.github_reader.installation_id" in msg
    assert "tf.github_reader.private_key" in msg
    assert "service_github_app_private_key" not in keyring_store.secret_reads()


def test_agent_plan_refuses_when_reader_token_mint_fails(
    tmp_path: Path,
    config: Any,
    agent_caller: None,
    keyring_store: FakeKeyring,
    github_api: GitHubApiFake,
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    keyring_store.values["tf_github_reader_private_key"] = _generate_pem()
    config(
        tf={
            "stacks": [{"path": "tf/github/dan-petty"}],
            "github_reader": {"app_id": 2001, "installation_id": 77},
        }
    )
    github_api.route(
        "POST",
        "/app/installations/77/access_tokens",
        github_json({"message": "Requested permissions not granted"}, status=422),
    )

    with pytest.raises(TFAccessRefusedError) as caught:
        prepare_tf_stack_run(stack, action="plan", dry_run=False)

    assert caught.value.details["key"] == "tf.github_reader.private_key"
    assert "devops-settings-reader" in caught.value.message


def test_person_caller_and_dry_run_mint_no_reader_token(
    tmp_path: Path,
    config: Any,
    person_caller: None,
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    stack.mkdir(parents=True)
    config(tf={"stacks": [{"path": "tf/github/dan-petty"}]})

    assert reader_github_env() == {}
    assert prepare_tf_stack_run(stack, action="plan", dry_run=True) is None


def test_stack_agent_access_resolves_non_matching_and_non_github_entries(
    tmp_path: Path,
    config: Any,
) -> None:
    stack = tmp_path / "tf" / "github" / "dan-petty"
    other = tmp_path / "examples" / "aws"
    stack.mkdir(parents=True)
    other.mkdir(parents=True)
    config(
        tf={
            "stacks": [
                {"path": "tf/github/someone-else"},
                {"path": "examples/aws"},
                {"path": str(stack), "agent_access": "apply"},
            ]
        }
    )

    assert stack_agent_access(stack) is TFAccessLevel.APPLY
    assert stack_agent_access(other) is None
