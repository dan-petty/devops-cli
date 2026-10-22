"""The agent skills OpenSpec generates, kept as the isolated `custom` profile writes them (ADR 0010).

The skills are committed, because a cloud agent or a fresh clone never runs an install but reads
the checkout. `openspec update` has no project-level profile pin, so a developer's wider global
profile once rewrote six of the eight files and added the archive and sync skills, which write
`openspec/specs/`, and which only the release cut may. A regeneration under the isolated
configuration (`isolated_openspec`) is the only one that leaves the tree as the project commits it.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from devops_cli.config.constants import CONST_OPENSPEC_DIR, CONST_OPENSPEC_GENERATED_GLOBS
from devops_cli.lang import MESSAGES
from devops_cli.openspec.tool import OpenSpecTool


def generated_files(directory: Path) -> dict[str, bytes]:
    """The content of each file OpenSpec's skills occupy under `directory`, by its path from it."""
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for pattern in CONST_OPENSPEC_GENERATED_GLOBS
        for path in directory.glob(pattern)
        if path.is_file()
    }


def regenerate_skills(tool: OpenSpecTool, directory: Path) -> None:
    """Rewrite the skills under `directory` with `openspec update --force`, which also removes the
    skills of a workflow the profile does not hold. Under any profile but the isolated one this
    would write the archive and sync skills, so it takes the tool `isolated_openspec` gives."""
    tool.run_checked(["update", "--force"], directory)


def _drift_message(path: str, committed: dict[str, bytes], regenerated: dict[str, bytes]) -> str:
    """How `path` differs between the committed skills and a regeneration of them."""
    if path not in committed:
        return MESSAGES.openspec.skill_missing.format(path=path)
    if path not in regenerated:
        return MESSAGES.openspec.skill_unexpected.format(path=path)
    return MESSAGES.openspec.skill_differs.format(path=path)


def missing_skill_trees(directory: Path) -> list[str]:
    """The globs of OpenSpec's generated files that match no file under `directory`. `openspec
    update` finds an agent by the skills it holds, so it cannot write back a tree deleted whole."""
    return [
        pattern
        for pattern in CONST_OPENSPEC_GENERATED_GLOBS
        if not any(path.is_file() for path in directory.glob(pattern))
    ]


def skill_drift(tool: OpenSpecTool, root: Path) -> list[str]:
    """One message per skill tree missing from `root`, and per skill file in it that a
    regeneration under the isolated profile would change, add or remove. The regeneration runs in
    a scratch copy of the skills."""
    committed = generated_files(root)
    with tempfile.TemporaryDirectory(prefix="openspec-skills-") as scratch:
        copy = Path(scratch)
        (copy / CONST_OPENSPEC_DIR).mkdir()
        for path, content in committed.items():
            (copy / path).parent.mkdir(parents=True, exist_ok=True)
            (copy / path).write_bytes(content)
        regenerate_skills(tool, copy)
        regenerated = generated_files(copy)
    return [
        *(
            MESSAGES.openspec.skill_tree_missing.format(pattern=pattern)
            for pattern in missing_skill_trees(root)
        ),
        *(
            _drift_message(path, committed, regenerated)
            for path in sorted(committed.keys() | regenerated.keys())
            if committed.get(path) != regenerated.get(path)
        ),
    ]
