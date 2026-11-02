"""No MCP tool publishes a parameter that takes a secret value (#3222, SECURITY.md rule 12).

The model writes the arguments of a tool call. A secret in an argument passes through the model
context, the provider, the LLM cache and the run trace. So a credential comes from the connection
or the configuration, or as a reference that the server resolves.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.ai.mcp.server import mcp
from devops_cli.config.constants import (
    CONST_MCP_SECRET_PARAMETER_ALLOWLIST,
    CONST_MCP_SECRET_PARAMETER_WORDS,
)
from devops_cli.exceptions import ValidationError
from devops_cli.security.sanitizer import is_secret_parameter_name

# A reason is a sentence, not a word: a new entry has to say why the parameter holds no value.
_MIN_REASON_CHARS = 30


def _takes_text(schema: dict[str, Any]) -> bool:
    """Report whether a parameter can hold free text: a string, or a list of strings.

    A flag, a number and a choice from a fixed list cannot hold a secret value.
    """
    if "enum" in schema or "const" in schema:
        return False
    for branch in schema.get("anyOf", []) + schema.get("oneOf", []):
        if _takes_text(branch):
            return True
    declared = schema.get("type")
    if declared == "string":
        return True
    if declared == "array":
        return _takes_text(schema.get("items", {}))
    return declared is None and not ("anyOf" in schema or "oneOf" in schema)


def _published_parameters() -> dict[str, dict[str, dict[str, Any]]]:
    """The properties of every registered tool, gated or not."""
    tools = asyncio.run(mcp._list_tools())
    return {tool.name: tool.parameters.get("properties", {}) for tool in tools}


def _secret_suggesting() -> list[tuple[str, str]]:
    """Every (tool, parameter) with a secret-suggesting name that can hold text."""
    return sorted(
        (tool, name)
        for tool, properties in _published_parameters().items()
        for name, schema in properties.items()
        if is_secret_parameter_name(name) and _takes_text(schema)
    )


def test_no_published_parameter_takes_a_secret_value() -> None:
    """Each text parameter with a secret-suggesting name is on the allow-list, with its reason."""
    unlisted = [
        pair for pair in _secret_suggesting() if pair not in CONST_MCP_SECRET_PARAMETER_ALLOWLIST
    ]

    assert unlisted == []


def test_the_allow_list_holds_only_live_entries_with_a_reason() -> None:
    """An entry names a published parameter that the guard would refuse, and says why it is safe."""
    live = set(_secret_suggesting())
    stale = sorted(pair for pair in CONST_MCP_SECRET_PARAMETER_ALLOWLIST if pair not in live)
    short = sorted(
        pair
        for pair, reason in CONST_MCP_SECRET_PARAMETER_ALLOWLIST.items()
        if len(reason.strip()) < _MIN_REASON_CHARS
    )

    assert (stale, short) == ([], [])


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "db_password",
        "token",
        "oidc_token",
        "api_key",
        "API_KEY",
        "apikey",
        "private_key",
        "client_secret",
        "credential",
        "credentials",
        "bearer",
        "bearer_header",
        "passphrase",
        "key_values",
    ],
)
def test_a_name_with_a_secret_word_suggests_a_secret(name: str) -> None:
    assert is_secret_parameter_name(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "key",
        "key_path",
        "key_dir",
        "namespace",
        "workspace",
        "keyless",
        "image",
        "value",
        "dry_run",
    ],
)
def test_a_name_without_a_secret_word_suggests_none(name: str) -> None:
    assert is_secret_parameter_name(name) is False


def test_the_words_are_lower_case_and_not_empty() -> None:
    """The matcher lower-cases the name, so a word with a capital would never match."""
    assert all(word and word == word.lower() for word in CONST_MCP_SECRET_PARAMETER_WORDS)


def test_vault_set_is_not_a_tool() -> None:
    """`vault_set` stores the values that a model would write, so a person runs it at the shell."""
    assert "vault_set" not in _published_parameters()


def test_vault_get_publishes_no_option_that_shows_the_value() -> None:
    """A tool never returns a credential: `show` would print the value into the reply."""
    assert "show" not in _published_parameters()["vault_get"]


def test_docker_sign_refuses_a_token_that_is_not_a_reference() -> None:
    """The tool takes `keyring:<name>` for the OIDC token, and never the token itself."""
    from devops_cli.ai.mcp.server import docker_sign

    raw = "eyJhbGciOiJSUzI1NiJ9.example-oidc-token"
    with patch("devops_cli.ai.mcp.server._run_mcp_cmd") as run:
        with pytest.raises(ValidationError, match="oidc_token") as refused:
            docker_sign("example.com/app:1.0.0", oidc_token=raw)

    assert (run.called, raw in str(refused.value)) == (False, False)


def test_docker_sign_passes_a_keyring_reference_in_argv() -> None:
    """A reference carries no secret, so the command line holds it and no environment is set."""
    from devops_cli.ai.mcp.server import docker_sign

    with patch("devops_cli.ai.mcp.server._run_mcp_cmd", return_value="Signed") as run:
        docker_sign("example.com/app:1.0.0", oidc_token="keyring:cosign_oidc", dry_run=True)

    argv = run.call_args.args[0]
    assert (
        argv[argv.index("--oidc-token") + 1],
        "env" in run.call_args.kwargs,
    ) == ("keyring:cosign_oidc", False)
