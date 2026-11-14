"""The `devops roadmap registries` command lists and audits the test registry declarations (#3332).

The command reads the module-level `REGISTRY_COUNTS` declarations of the test modules, prints each
entry with its token, its kind, its target path and its source `path:line`, and exits 1 on a
finding. It declares the `no-external-request` dry-run class.
"""

from __future__ import annotations

from devops_cli.lang import HELP


def test_the_registries_help_texts_exist() -> None:
    """The command and its `--path` option have a help text, so `devops roadmap --help` lists the
    command and a person reads what `--path` chooses."""
    assert HELP.roadmap.registries.strip()
    assert HELP.roadmap.registries_path.strip()
