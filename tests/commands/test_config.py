"""Verify what the `devops config` commands tell the user about the config file they write."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tests.support.config_writes import written_keys


def test_config_init_names_the_active_config_file_it_writes(
    cli: Any, config: Any, tmp_path: Path, isolate_data_dir: Path
) -> None:
    """The wizard wrote the active config file but named the default config path (#1998). It
    writes only the keys that the answers change (#1999).

    The floor's `DEVOPS_CLI_CONFIG` makes a file under `tmp_path` the active config. An empty
    PATH holds no gh, so the wizard asks no gh question and starts no program.
    """
    active = config(github={"default_org": "old-org"})
    no_programs = tmp_path / "no-programs"
    no_programs.mkdir()
    answers = f"new-org\n{tmp_path / 'repos'}\n\n\n\n"

    result = cli("config", "init", input=answers, env={"PATH": str(no_programs)})

    named = [line for line in result.output.splitlines() if line.startswith("Config file:")]
    written = yaml.safe_load(active.read_text(encoding="utf-8"))["github"]["default_org"]
    assert (result.exit_code, named, written, written_keys(isolate_data_dir)) == (
        0,
        [f"Config file: {active}"],
        "new-org",
        [["github.default_org", "repos.base_dir"]],
    )
