"""A save of the settings writes only the keys that changed, and keeps the comments, the order of
the keys, the keys that devops-cli does not know and the layout of the config file (#1999).

Before, a save wrote the whole settings model back to the file: it dropped every comment and every
unknown key, and it wrote every default and every value that an environment variable gave.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import (
    Settings,
    load_settings,
    reset_settings_cache,
    save_settings,
)
from devops_cli.exceptions import ConfigurationError
from tests.support.config_writes import written_keys
from tests.support.paths import REPO_ROOT

_COMMENTED = """\
# devops-cli settings of this workstation

github:
  default_org: old-org   # the org that `devops repos clone-org` reads

# A section that this version of devops-cli does not know.
legacy_section:
  keep: me
telemetry:
  enabled: false
valkey:
  host: localhost:6379
  port: 6379
  url: "valkey://example.com:6380/1"
"""


def _use(config_path: Path, text: str) -> None:
    """Make `text` the content of the active config file."""
    config_path.write_text(text, encoding="utf-8")
    reset_settings_cache()


def test_a_save_writes_only_the_changed_key_and_keeps_the_comments_and_unknown_keys(
    isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    """The removed `valkey.host` and `valkey.port` are unknown keys too, and they stay."""
    _use(isolate_devops_cli_config, _COMMENTED)
    settings = load_settings()
    settings.github.default_org = "new-org"

    save_settings(settings)

    assert (
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        written_keys(isolate_data_dir),
    ) == (
        _COMMENTED.replace("default_org: old-org   #", "default_org: new-org   #"),
        [["github.default_org"]],
    )


def test_the_example_config_keeps_every_line_but_the_changed_keys(
    isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    """A changed null, a new key in a section that a comment follows, a changed list and a new
    section: the comments that end a section stay after its last key."""
    example = (REPO_ROOT / "config.example.yaml").read_text(encoding="utf-8")
    _use(isolate_devops_cli_config, example)
    settings = load_settings()
    settings.github.default_org = "example-org"
    settings.ssh.key_prefix = "devops_cli"
    settings.ai.ollama_urls = ["http://a.example.com:11434", "http://b.example.com:11434"]
    settings.runs.index_url = "valkey://example.com:6379"

    save_settings(settings)

    expected = (
        example.replace("  default_org: null\n", "  default_org: example-org\n", 1)
        .replace("  rotation_days: 90\n", "  rotation_days: 90\n  key_prefix: devops_cli\n", 1)
        .replace(
            "    - http://localhost:11434\n",
            "    - http://a.example.com:11434\n    - http://b.example.com:11434\n",
            1,
        )
        + "runs:\n  index_url: valkey://example.com:6379\n"
    )
    assert (
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        written_keys(isolate_data_dir),
    ) == (
        expected,
        [["ai.ollama_urls", "github.default_org", "runs.index_url", "ssh.key_prefix"]],
    )


def test_a_key_that_keeps_its_default_stays_out_of_a_new_file(
    tmp_path: Path, isolate_data_dir: Path
) -> None:
    """The floor's environment gives the telemetry endpoint and the private network opt-in, and
    neither they nor a default reach the file."""
    new_file = tmp_path / "project" / "config.yaml"
    settings = load_settings()
    settings.github.default_org = "example-org"

    save_settings(settings, new_file)

    assert (new_file.read_text(encoding="utf-8"), written_keys(isolate_data_dir)) == (
        "github:\n  default_org: example-org\n",
        [["github.default_org"]],
    )


def test_a_removed_entry_leaves_the_file_and_a_key_with_a_dot_is_one_key(
    isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    _use(
        isolate_devops_cli_config,
        "ai:\n  gateway_weights:\n    qwen3.8:27b: 2   # the larger model\n    llama: 1\n",
    )
    settings = load_settings()
    del settings.ai.gateway_weights["llama"]

    save_settings(settings)

    assert (
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        written_keys(isolate_data_dir),
    ) == (
        "ai:\n  gateway_weights:\n    qwen3.8:27b: 2   # the larger model\n",
        [["ai.gateway_weights.llama"]],
    )


def test_a_file_of_comments_alone_keeps_them_before_the_new_keys(
    isolate_devops_cli_config: Path,
) -> None:
    comments = "# Settings come later.\n# github:\n#   default_org: example-org\n"
    _use(isolate_devops_cli_config, comments)
    settings = load_settings()
    settings.github.default_org = "example-org"

    save_settings(settings)

    assert isolate_devops_cli_config.read_text(encoding="utf-8") == (
        comments + "github:\n  default_org: example-org\n"
    )


def test_a_document_start_marker_stays(isolate_devops_cli_config: Path) -> None:
    _use(isolate_devops_cli_config, "---\ngithub:\n  default_org: old-org\n")
    settings = load_settings()
    settings.github.default_org = "new-org"

    save_settings(settings)

    assert isolate_devops_cli_config.read_text(encoding="utf-8") == (
        "---\ngithub:\n  default_org: new-org\n"
    )


def test_settings_made_in_code_write_the_values_that_differ_from_the_defaults(
    tmp_path: Path,
) -> None:
    """Settings that `load_settings` did not return start from the defaults of the model."""
    target = tmp_path / "config.yaml"
    target.write_text("ssh:\n  key_prefix: devops_cli\n", encoding="utf-8")

    save_settings(Settings.model_validate({"github": {"default_org": "example-org"}}), target)

    assert target.read_text(encoding="utf-8") == (
        "ssh:\n  key_prefix: devops_cli\ngithub:\n  default_org: example-org\n"
    )


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("- github\n- ssh\n", id="a-sequence"),
        pytest.param("github: [example-org\n", id="not-yaml"),
    ],
)
def test_a_file_that_holds_no_mapping_is_refused_and_stays_as_it_is(
    tmp_path: Path, content: str
) -> None:
    target = tmp_path / "project" / "config.yaml"
    target.parent.mkdir()
    target.write_text(content, encoding="utf-8")
    settings = Settings.model_validate({"github": {"default_org": "example-org"}})

    with pytest.raises(ConfigurationError) as raised:
        save_settings(settings, target)

    assert (
        raised.value.exit_code,
        raised.value.error_code,
        str(target) in raised.value.message,
        target.read_text(encoding="utf-8"),
        sorted(path.name for path in target.parent.iterdir()),
    ) == (1, "CONFIGURATION_ERROR", True, content, ["config.yaml"])


def test_config_set_writes_its_key_when_an_environment_variable_gives_the_same_value(
    cli: Any, isolate_devops_cli_config: Path, isolate_data_dir: Path
) -> None:
    """The person names the key to store, so the file gets it, also when the loaded settings
    already hold the value. Without the file, the value goes when the variable goes."""
    before = isolate_devops_cli_config.read_text(encoding="utf-8")

    result = cli(
        "config",
        "set",
        "github.default_org",
        "example-org",
        env={"DEVOPS_CLI_GITHUB_DEFAULT_ORG": "example-org"},
    )

    assert (
        result.exit_code,
        isolate_devops_cli_config.read_text(encoding="utf-8"),
        written_keys(isolate_data_dir),
    ) == (0, before + "github:\n  default_org: example-org\n", [["github.default_org"]])
