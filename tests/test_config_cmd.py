"""Tests for devops config subcommands (show, get, set, output, env)."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.config import app
from devops_cli.config.os_keyring import (
    KeyringLockedError,
    SecretStorageError,
    get_keyring_secret,
    has_encrypted_backend,
    has_keyring_secret,
    keyring_read,
    keyring_write,
    store_keyring_secret,
)
from devops_cli.main import app as main_app
from tests.support.fakes.keyring import FakeKeyring

pytestmark = pytest.mark.usefixtures("keyring_store")

runner = CliRunner(env={"COLUMNS": "250"})


def test_config_output_table_view() -> None:
    result = runner.invoke(app, ["output"])
    assert result.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in result.stdout
    assert "DEVOPS_CLI_GRAFANA_TOKEN" in result.stdout
    assert "devops-cli environment variables" in result.stdout


def test_config_output_export_view() -> None:
    result = runner.invoke(app, ["output", "--export"])
    assert result.exit_code == 0
    assert "# devops-cli environment variables export" in result.stdout
    assert "export DEVOPS_CLI_" in result.stdout or "# export DEVOPS_CLI_" in result.stdout
    assert '# export DEVOPS_CLI_GRAFANA_TOKEN="****"' in result.stdout


def test_config_output_json_view() -> None:
    result = runner.invoke(app, ["output", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    env_vars = [item["env_var"] for item in data]
    assert "DEVOPS_CLI_CONFIG" in env_vars
    assert "DEVOPS_CLI_AI_MODEL" in env_vars
    assert "DEVOPS_CLI_GRAFANA_TOKEN" in env_vars

    ai_model_item = next(item for item in data if item["env_var"] == "DEVOPS_CLI_AI_MODEL")
    assert ai_model_item["option_key"] == "ai.model"
    assert ai_model_item["is_secret"] is False

    grafana_token_item = next(
        item for item in data if item["env_var"] == "DEVOPS_CLI_GRAFANA_TOKEN"
    )
    assert (grafana_token_item["option_key"], grafana_token_item["is_secret"]) == (
        "grafana.token",
        True,
    )


def test_github_token_is_not_a_config_option() -> None:
    """A person's GitHub identity comes only from `gh auth token`: no option, keyring key or
    variable holds a gh token. The GitHub credentials devops-cli keeps are the private keys of
    two GitHub Apps: the roadmap's (`service.github_app`, ADR 0015) and the one Argo CD's GitHub
    notifier acts as (`argocd.github_app_private_key`, #2000)."""
    from devops_cli.config.env import get_all_env_var_specs, secret_keys, setting_variables

    def github_section(keys: Iterable[str]) -> list[str]:
        return sorted(key for key in keys if key.partition(".")[0] == "github")

    assert (
        github_section(setting_variables().keys() | secret_keys()),
        github_section(secret_keys()),
        [(s.env_var, s.is_secret) for s in get_all_env_var_specs() if "GITHUB" in s.env_var],
    ) == (
        ["github.default_org"],
        [],
        [
            ("DEVOPS_CLI_ARGOCD_GITHUB_APP_ID", False),
            ("DEVOPS_CLI_ARGOCD_GITHUB_APP_INSTALLATION_ID", False),
            ("DEVOPS_CLI_ARGOCD_GITHUB_APP_PRIVATE_KEY", True),
            ("DEVOPS_CLI_GITHUB_DEFAULT_ORG", False),
            ("DEVOPS_CLI_SERVICE_GITHUB_APP_APP_ID", False),
            ("DEVOPS_CLI_SERVICE_GITHUB_APP_INSTALLATION_ID", False),
            ("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", True),
            ("DEVOPS_CLI_SERVICE_GITHUB_APP_SLUG", False),
        ],
    )


def test_the_ai_cache_backend_is_not_a_config_option() -> None:
    """The AI cache has no backend choice: no option, variable, field or key reads one."""
    from devops_cli.config.env import get_all_env_var_specs, option_env_vars
    from devops_cli.config.settings import Settings

    assert (
        "ai.cache.backend" in option_env_vars(),
        any(spec.env_var == "DEVOPS_CLI_AI_CACHE_BACKEND" for spec in get_all_env_var_specs()),
        "backend" in Settings().ai.cache.model_dump(),
        runner.invoke(app, ["get", "ai.cache.backend"]).exit_code,
    ) == (False, False, False, 1)


def test_valkey_url_is_the_one_option_that_names_the_valkey_address() -> None:
    """No option, variable or field holds a Valkey host, port or database beside `valkey.url`."""
    from devops_cli.config.env import get_all_env_var_specs, option_env_vars
    from devops_cli.config.settings import ValkeyConfig

    assert (
        sorted(key for key in option_env_vars() if key.startswith("valkey.")),
        sorted(
            spec.env_var
            for spec in get_all_env_var_specs()
            if spec.env_var.startswith("DEVOPS_CLI_VALKEY_")
        ),
        sorted(ValkeyConfig.model_fields),
        [runner.invoke(app, ["get", key]).exit_code for key in ("valkey.host", "valkey.db")],
    ) == (
        ["valkey.password", "valkey.timeout", "valkey.url"],
        ["DEVOPS_CLI_VALKEY_PASSWORD", "DEVOPS_CLI_VALKEY_TIMEOUT", "DEVOPS_CLI_VALKEY_URL"],
        ["password", "threat_intel_ttl", "timeout", "url"],
        [1, 1],
    )


def test_the_valkey_timeout_variable_names_the_default_timeout() -> None:
    from devops_cli.config.defaults import DEFAULT_VALKEY_TIMEOUT_SECONDS
    from devops_cli.config.env import get_all_env_var_specs

    assert [
        spec.description.endswith(f"(default: {DEFAULT_VALKEY_TIMEOUT_SECONDS})")
        for spec in get_all_env_var_specs()
        if spec.env_var == "DEVOPS_CLI_VALKEY_TIMEOUT"
    ] == [True]


def test_config_env_aliases() -> None:
    res1 = runner.invoke(app, ["env"])
    assert res1.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in res1.stdout

    res2 = runner.invoke(app, ["env-vars"])
    assert res2.exit_code == 0
    assert "DEVOPS_CLI_AI_MODEL" in res2.stdout


def test_config_output_reflects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_MODEL", "gpt-4o")
    result = runner.invoke(app, ["output", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    ai_item = next(item for item in data if item["env_var"] == "DEVOPS_CLI_AI_MODEL")
    assert ai_item["value"] == "gpt-4o"
    assert ai_item["from_env"] is True

    result_table = runner.invoke(app, ["output"])
    assert result_table.exit_code == 0
    assert "gpt-4o" in result_table.stdout
    assert "(via env)" in result_table.stdout


def test_config_show_includes_allow_private_network_and_active_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_cfg = tmp_path / "custom_config.yaml"
    custom_cfg.write_text(
        "ai:\n"
        "  allow_private_network: true\n"
        "  hardware_cost_usd: 7000.0\n"
        "  reference_model: gpt-4o\n"
        "  ollama_urls:\n"
        "    - http://example.com:11434\n"
        "    - http://example.com:11435\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(custom_cfg))

    result = runner.invoke(app, ["show"])
    assert (
        result.exit_code,
        "ai.allow_private_network" in result.stdout,
        "ai.hardware_cost_usd" in result.stdout,
        "7000.0" in result.stdout,
        "ai.reference_model" in result.stdout,
        "gpt-4o" in result.stdout,
        "ai.ollama_urls" in result.stdout,
        "http://example.com:11434, http://example.com:11435" in result.stdout,
        "True" in result.stdout,
        str(custom_cfg) in result.stdout,
    ) == (0, True, True, True, True, True, True, True, True, True)


def test_config_show_includes_the_reference_models_and_their_provider(
    config: Callable[..., Path],
) -> None:
    """`devops config show` lists both reference models and the provider that prices them."""
    config(
        ai={
            "reference_model": "gpt-4o",
            "reference_embedding_model": "text-embedding-3-large",
            "reference_provider": "openai",
        }
    )

    result = runner.invoke(app, ["show"])
    rows = {
        cells[0]: cells[1] for line in result.stdout.splitlines() if len(cells := line.split()) >= 2
    }

    assert (
        result.exit_code,
        rows.get("ai.reference_model"),
        rows.get("ai.reference_embedding_model"),
        rows.get("ai.reference_provider"),
    ) == (0, "gpt-4o", "text-embedding-3-large", "openai")


def test_config_show_warns_about_a_reference_model_that_genai_prices_does_not_know(
    config: Callable[..., Path], caplog: pytest.LogCaptureFixture
) -> None:
    """`devops config show` checks both reference models against the pricing registry and logs a
    warning for each one that genai-prices does not know. It is a warning, not a load error, so
    a registry update cannot break config loading (#1672)."""
    config(ai={"reference_model": "gpt-4o-mni", "reference_embedding_model": "embed-9"})
    caplog.set_level(logging.WARNING)

    result = runner.invoke(app, ["show"])

    assert (
        result.exit_code,
        [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING],
    ) == (
        0,
        [
            "genai-prices and the price overrides hold no price for gpt-4o-mni (ai.reference_model) under provider openai, so the local savings of chat tokens are unpriced.",
            "genai-prices and the price overrides hold no price for embed-9 (ai.reference_embedding_model) under provider openai, so the local savings of embedding tokens are unpriced.",
        ],
    )


def test_dotted_set_rejects_top_level_section_overwrite() -> None:
    """dotted_set must raise ValueError when setting a top-level section directly."""
    from devops_cli.config.settings import Settings, dotted_set

    settings = Settings()
    with pytest.raises(ValueError, match="Cannot set top-level section 'github' directly"):
        dotted_set(settings, "github", "invalid_string_overwrite")


def test_config_commands_comprehensive(tmp_path: Path) -> None:
    """Verify config show, get, set, output, env, auth-headless, audit-stream subcommands."""
    cfg_file = tmp_path / "config.yaml"
    with (
        patch("devops_cli.config.settings.CONFIG_PATH", cfg_file),
        patch("devops_cli.commands.config._gh_auth_status", return_value=True),
    ):
        res_show = runner.invoke(main_app, ["config", "show"])
        assert res_show.exit_code == 0

        res_get = runner.invoke(main_app, ["config", "get", "ai.provider"])
        assert res_get.exit_code == 0

        res_set = runner.invoke(main_app, ["config", "set", "ai.provider", "openai"])
        assert res_set.exit_code == 0

        res_out = runner.invoke(main_app, ["config", "output"])
        assert res_out.exit_code == 0

        res_env = runner.invoke(main_app, ["config", "env"])
        assert res_env.exit_code == 0

        res_headless = runner.invoke(app, ["auth-headless", "grafana.token", "FAKE-token"])
        assert res_headless.exit_code == 0

        res_headless_bad = runner.invoke(app, ["auth-headless", "invalid_key", "val"])
        assert res_headless_bad.exit_code == 1

        with patch("devops_cli.core.audit.stream_audit_records", return_value=5):
            res_stream = runner.invoke(app, ["audit-stream", "https://example.com/ingest"])
            assert res_stream.exit_code == 0


@pytest.mark.parametrize(
    ("selected", "usable"),
    [
        pytest.param("fail", False, id="the library's fail backend"),
        pytest.param(type("PlaintextKeyring", (), {"priority": 1})(), False, id="plaintext"),
        pytest.param(type("CustomKeyring", (), {"priority": 0})(), False, id="zero priority"),
        pytest.param(type("EncryptedKeyring", (), {"priority": 5})(), True, id="encrypted"),
    ],
)
def test_only_an_encrypted_backend_with_a_priority_is_usable(
    keyring_store: FakeKeyring, selected: object, usable: bool
) -> None:
    """The fail backend, no backend, a plaintext backend and a zero-priority one are refused."""
    from keyring.backends.fail import Keyring as FailKeyring

    keyring_store.selected = FailKeyring() if selected == "fail" else selected

    assert has_encrypted_backend() is usable


def _chainer_of(*members: object) -> object:
    """Build a ChainerBackend over the given backends, as keyring does when several are viable."""
    from keyring.backends.chainer import ChainerBackend

    return type("FakeChainer", (ChainerBackend,), {"backends": list(members), "priority": 10})()


def test_a_chainer_hiding_a_plaintext_backend_is_rejected(keyring_store: FakeKeyring) -> None:
    """The chainer writes to the next backend when one fails, so a locked Secret Service
    would hand the secret to the plaintext backend behind it."""
    secure = type("EncryptedKeyring", (), {"priority": 5})()
    plaintext = type("PlaintextKeyring", (), {"priority": 0.5})()
    keyring_store.selected = _chainer_of(secure, plaintext)

    assert has_encrypted_backend() is False


def test_a_fake_backend_class_a_test_defines_is_not_left_for_later_tests() -> None:
    """keyring registers every backend class and picks the highest-priority one when it next
    detects a backend: a `FakeChainer` from the tests here, priority 10, became a later test's
    keyring, whose writes failed on its stand-in member's missing `set_password`."""
    import keyring.core
    from keyring.backend import KeyringBackend

    from tests.keyring_isolation import keyring_backends_restored

    chosen = keyring.core._keyring_backend
    with keyring_backends_restored():
        fake = _chainer_of(type("EncryptedKeyring", (), {"priority": 5})())
        keyring.core._keyring_backend = fake
        during = type(fake) in KeyringBackend._classes
    assert (
        during,
        type(fake) in KeyringBackend._classes,
        keyring.core._keyring_backend is chosen,
    ) == (True, False, True)


def test_a_locked_backend_class_a_test_defines_is_no_viable_backend_after_it() -> None:
    """A `ChainerBackend` asks `get_viable_backends()` for its members: a priority-1 test backend
    raising `KeyringLocked` stayed one, and later settings reads warned that the keyring was
    locked (#1601)."""
    from keyring.backend import KeyringBackend
    from keyring.errors import KeyringLocked

    from tests.keyring_isolation import keyring_backends_restored

    def locked(*_: object) -> None:
        raise KeyringLocked("locked")

    with keyring_backends_restored():
        raising = type(
            "Raising",
            (KeyringBackend,),
            {
                "priority": 1,
                "get_password": locked,
                "set_password": locked,
                "delete_password": locked,
            },
        )
        during = raising in KeyringBackend.get_viable_backends()
    assert (during, raising in KeyringBackend.get_viable_backends()) == (True, False)


def test_a_chainer_of_encrypted_backends_is_accepted(keyring_store: FakeKeyring) -> None:
    """Rejecting every chainer would lock out hosts with two real keyrings installed."""
    first = type("EncryptedKeyring", (), {"priority": 5})()
    second = type("OtherEncryptedKeyring", (), {"priority": 4})()
    keyring_store.selected = _chainer_of(first, second)

    assert has_encrypted_backend() is True


def test_storing_into_a_locked_keyring_names_the_unlock_command(
    keyring_store: FakeKeyring, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generic storage failure gave no hint that one command would fix it."""
    monkeypatch.delenv("DEVOPS_CLI_HEADLESS_AUTH", raising=False)
    keyring_store.locked = True

    with pytest.raises(KeyringLockedError, match="devops devcontainer unlock-keyring"):
        store_keyring_secret("grafana_token", "FAKE-token")


def test_reading_from_a_locked_keyring_names_the_unlock_command(
    keyring_store: FakeKeyring, caplog: pytest.LogCaptureFixture
) -> None:
    """The secret is there, just locked; reporting it as missing sends people to re-enter it."""
    keyring_store.locked = True

    with caplog.at_level(logging.WARNING, logger="devops_cli.config.os_keyring"):
        found = (get_keyring_secret("grafana_token"), has_keyring_secret("grafana_token"))

    warnings = [record.getMessage() for record in caplog.records]
    assert (found, len(warnings)) == ((None, False), 2)
    assert all("devops devcontainer unlock-keyring" in warning for warning in warnings)


def test_strict_keyring_access_raises_instead_of_reading_as_missing(
    keyring_store: FakeKeyring,
) -> None:
    """A locked or failing keyring raises in the strict helpers; nothing falls back to memory."""
    from keyring.errors import KeyringError, KeyringLocked

    class Raising:
        priority = 1
        error: Exception = KeyringLocked("locked")

        def get_password(self, service: str, username: str) -> str | None:
            raise self.error

        def set_password(self, service: str, username: str, password: str) -> None:
            raise self.error

        def delete_password(self, service: str, username: str) -> None:
            raise self.error

    backend = Raising()
    keyring_store.selected = backend
    raised: list[type[Exception]] = []
    for error in (KeyringLocked("locked"), KeyringError("broken")):
        backend.error = error
        for call in (lambda: keyring_read("k"), lambda: keyring_write("k", "v")):
            with pytest.raises(SecretStorageError) as caught:
                call()
            raised.append(type(caught.value))
    assert raised == [
        KeyringLockedError,
        KeyringLockedError,
        SecretStorageError,
        SecretStorageError,
    ]
