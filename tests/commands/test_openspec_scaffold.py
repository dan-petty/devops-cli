"""The committed OpenSpec scaffold: its configuration, the skills it generates, what git keeps of
them, and the hooks and workflows that run the gate (#1844, ADR 0010).

OpenSpec fails quietly: a plain scalar containing ` #` is cut at the comment, an unknown
top-level key is ignored, and a skill hand-edited or generated under a wider profile only shows
in a regeneration. These tests read the committed files and need no `openspec`.
"""

from __future__ import annotations

import filecmp
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_DOCS_CLASS_RECORD,
    CONST_DOCS_CLASS_TOOL_GENERATED,
    CONST_DOCS_CLASS_TOOL_OWNED,
    CONST_DOCS_INVENTORY,
    CONST_DOCS_NAME_CHECKED_CLASSES,
    CONST_REVIEW_ROUTED_PATH_PATTERNS,
)
from devops_cli.tools_lock import load_tools_lock
from tests.support.paths import REPO_ROOT

CONFIG_PATH = REPO_ROOT / "openspec/config.yaml"
# The top-level keys of `openspec/config.yaml` the project allows. OpenSpec reads others it
# ignores without a word, and the project plans with these four (ADR 0010, Design).
CONFIG_KEYS = frozenset({"schema", "context", "rules", "operations"})
# The YAML scalar styles that read a text as written: folded (`>`) and literal (`|`).
BLOCK_SCALAR_STYLES = frozenset({">", "|"})
SKILL_WORKFLOWS = ("apply-change", "explore", "propose", "update-change")
SKILL_TREES = (".claude/skills", ".agents/skills", ".kilocode/skills")


def _text_nodes(node: yaml.Node, *, is_item: bool = False) -> list[yaml.ScalarNode]:
    """The scalar nodes under `node` that are list items, where a rule or a piece of guidance is
    written."""
    if isinstance(node, yaml.ScalarNode):
        return [node] if is_item else []
    if isinstance(node, yaml.SequenceNode):
        return [leaf for item in node.value for leaf in _text_nodes(item, is_item=True)]
    return [leaf for _, value in node.value for leaf in _text_nodes(value)]


def config_problems(text: str) -> list[str]:
    """Why `openspec/config.yaml` would be read differently from how it is written; empty when it
    is read as written. Each problem is led by the line it is on."""
    root = yaml.compose(text)
    if not isinstance(root, yaml.MappingNode):
        return ["1: the configuration is not a mapping"]
    problems = [
        f"{key.start_mark.line + 1}: {key.value} is not a key the project allows, and OpenSpec "
        "ignores it without a word"
        for key, _ in root.value
        if key.value not in CONFIG_KEYS
    ]
    texts = [value for key, value in root.value if key.value == "context"] + [
        leaf for key, value in root.value if key.value != "schema" for leaf in _text_nodes(value)
    ]
    problems += [
        f"{node.start_mark.line + 1}: a {node.style or 'plain'} scalar is cut at ' #' or read as "
        "a mapping at ': '; write it folded (>-) or literal (|)"
        for node in texts
        if isinstance(node, yaml.ScalarNode) and node.style not in BLOCK_SCALAR_STYLES
    ]
    return sorted(problems, key=lambda problem: int(problem.split(":")[0]))


def test_the_committed_configuration_is_read_as_it_is_written() -> None:
    """Only the four keys, and every context, rule and piece of guidance a folded or literal
    scalar, so the file means what it says."""
    assert config_problems(CONFIG_PATH.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("text", "problems"),
    [
        (
            "schema: spec-driven\nbogus: 1\n",
            ["2: bogus is not a key the project allows, and OpenSpec ignores it without a word"],
        ),
        (
            "schema: spec-driven\nrules:\n  proposal:\n    - Cite the issue # in Why.\n",
            [
                "4: a plain scalar is cut at ' #' or read as a mapping at ': '; write it folded (>-) or literal (|)"
            ],
        ),
        (
            "schema: spec-driven\nrules:\n  proposal:\n    - 'Cite the issue: in Why.'\n",
            [
                "4: a ' scalar is cut at ' #' or read as a mapping at ': '; write it folded (>-) or literal (|)"
            ],
        ),
        (
            "schema: spec-driven\ncontext: Cite the issue.\n",
            [
                "2: a plain scalar is cut at ' #' or read as a mapping at ': '; write it folded (>-) or literal (|)"
            ],
        ),
        (
            "schema: spec-driven\noperations:\n  apply:\n    guidance:\n      - Tick tasks.\n",
            [
                "5: a plain scalar is cut at ' #' or read as a mapping at ': '; write it folded (>-) or literal (|)"
            ],
        ),
        (
            "schema: spec-driven\ncontext: |\n  Text.\nrules:\n  specs:\n    - >-\n      Rule.\n"
            "operations:\n  apply:\n    guidance:\n      - |\n        Guidance.\n",
            [],
        ),
        ("- a\n- b\n", ["1: the configuration is not a mapping"]),
    ],
    ids=[
        "unknown-key",
        "plain-rule-with-a-comment",
        "quoted-rule",
        "plain-context",
        "plain-guidance",
        "block-scalars",
        "not-a-mapping",
    ],
)
def test_a_configuration_that_would_be_read_otherwise_is_reported(
    text: str, problems: list[str]
) -> None:
    """The quiet failures of OpenSpec's configuration, each with its line."""
    assert config_problems(text) == problems


def _front_matter(skill: Path) -> dict[str, Any]:
    """The YAML front matter of the skill file `skill`."""
    parts = skill.read_text(encoding="utf-8").split("---\n", 2)
    loaded = yaml.safe_load(parts[1])
    assert isinstance(loaded, dict)
    return loaded


def test_the_skills_are_the_four_workflows_of_the_custom_profile_in_both_trees() -> None:
    """Propose, explore, apply and update, and no archive or sync skill, which write the living
    spec that only the pull request that closes a change may; the Claude and agents trees are
    identical."""
    found = {
        tree: sorted(path.parent.name for path in (REPO_ROOT / tree).glob("openspec-*/SKILL.md"))
        for tree in SKILL_TREES
    }
    expected = sorted(f"openspec-{name}" for name in SKILL_WORKFLOWS)
    claude, agents, kilo = (REPO_ROOT / tree for tree in SKILL_TREES)
    assert (
        found,
        [
            filecmp.dircmp(claude, other, ignore=[".openspec-target"]).diff_files
            for other in (agents, kilo)
        ],
    ) == ({tree: expected for tree in SKILL_TREES}, [[], []])
    assert [
        filecmp.cmp(claude / name / "SKILL.md", other / name / "SKILL.md", shallow=False)
        for other in (agents, kilo)
        for name in expected
    ] == [True] * 8
    assert (agents / ".openspec-target").read_text(encoding="utf-8") == "agents\n"


def test_every_skill_was_generated_by_the_openspec_the_tools_lock_pins() -> None:
    """Each skill embeds the version that wrote it, so a bump of the pin that did not regenerate
    them (`uv run devops openspec regenerate`) is found without running OpenSpec."""
    pinned = load_tools_lock().npm["openspec"].version
    generated_by = {
        f"{tree}/{path.parent.name}": _front_matter(path)["metadata"]["generatedBy"]
        for tree in SKILL_TREES
        for path in (REPO_ROOT / tree).glob("openspec-*/SKILL.md")
    }
    assert sorted(generated_by.items()) == sorted(
        (f"{tree}/openspec-{name}", pinned) for tree in SKILL_TREES for name in SKILL_WORKFLOWS
    )


def _ignored(path: str) -> bool:
    """Whether git ignores `path`, whatever is tracked."""
    run = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", path],
        cwd=REPO_ROOT,
        check=False,
    )
    return run.returncode == 0


def test_git_keeps_the_generated_skills_and_nothing_else_under_claude() -> None:
    """The skills are committed because a cloud agent or a fresh clone never runs an install; other
    skills, local settings and worktrees under `.claude/` stay local."""
    paths = {
        ".claude/skills/openspec-explore/SKILL.md": False,
        ".agents/skills/openspec-explore/SKILL.md": False,
        ".agents/skills/.openspec-target": False,
        ".kilocode/skills/openspec-explore/SKILL.md": False,
        ".claude/settings.json": False,
        ".claude/skills/other-skill/SKILL.md": True,
        ".claude/settings.local.json": True,
        ".claude/worktrees/topic/README.md": True,
    }
    assert {path: _ignored(path) for path in paths} == paths


def test_the_documentation_inventory_classifies_the_openspec_documents() -> None:
    """A plan is a record, which names commands that do not exist until it merges; a living spec
    is written by `openspec archive` alone; a skill is generated by the tool and checked by
    regenerating it, so none of them has its command names checked."""

    def classes(path: str) -> list[str]:
        return sorted(
            name
            for name, globs in CONST_DOCS_INVENTORY.items()
            if any(PurePosixPath(path).full_match(glob) for glob in globs)
        )

    assert (
        classes("openspec/changes/1900-widget-export/proposal.md"),
        classes("openspec/changes/archive/2026-10-22-1900-widget-export/tasks.md"),
        classes("openspec/specs/widget-export/spec.md"),
        classes(".claude/skills/openspec-explore/SKILL.md"),
        classes(".agents/skills/openspec-apply-change/SKILL.md"),
        classes(".kilocode/skills/openspec-apply-change/SKILL.md"),
        [
            name
            for name in (
                CONST_DOCS_CLASS_RECORD,
                CONST_DOCS_CLASS_TOOL_OWNED,
                CONST_DOCS_CLASS_TOOL_GENERATED,
            )
            if name in CONST_DOCS_NAME_CHECKED_CLASSES
        ],
    ) == (
        [CONST_DOCS_CLASS_RECORD],
        [CONST_DOCS_CLASS_RECORD],
        [CONST_DOCS_CLASS_TOOL_OWNED],
        [CONST_DOCS_CLASS_TOOL_GENERATED],
        [CONST_DOCS_CLASS_TOOL_GENERATED],
        [CONST_DOCS_CLASS_TOOL_GENERATED],
        [],
    )


def test_a_review_routes_the_openspec_files_off_the_persona_pages() -> None:
    """Plans, specs and generated skills are planning documents and generated text, and code is
    not."""

    def routed(path: str) -> bool:
        return any(
            PurePosixPath(path).full_match(pattern) for pattern in CONST_REVIEW_ROUTED_PATH_PATTERNS
        )

    assert [
        routed("openspec/changes/1900-widget-export/design.md"),
        routed("openspec/specs/widget-export/spec.md"),
        routed("openspec/config.yaml"),
        routed(".claude/skills/openspec-explore/SKILL.md"),
        routed(".agents/skills/openspec-explore/SKILL.md"),
        routed(".agents/skills/.openspec-target"),
        routed(".kilocode/skills/openspec-explore/SKILL.md"),
        routed("openspec/changes/archive/2026-10-23-1847-x/tasks.md"),
        routed("src/devops_cli/openspec/gate.py"),
    ] == [True, True, True, True, True, True, True, True, False]


def test_every_devops_ci_runs_the_openspec_row_and_the_hook_runs_it_on_its_files() -> None:
    """The row has no path filter and no exemption; the commit hook runs only that row, when a
    commit touches the plans, the config or the skills."""
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hooks = {hook["id"]: hook for repo in config["repos"] for hook in repo["hooks"]}
    hook = hooks["openspec-gate"]
    touching = [
        "openspec/config.yaml",
        "openspec/changes/1900-widget-export/tasks.md",
        ".claude/skills/openspec-explore/SKILL.md",
        ".agents/skills/.openspec-target",
        ".kilocode/skills/openspec-explore/SKILL.md",
    ]
    assert (
        get_check_spec("openspec").cmd,
        (hook["entry"], hook["pass_filenames"], hook["stages"]),
        [bool(re.search(hook["files"], path)) for path in touching],
        re.search(hook["files"], "src/devops_cli/openspec/gate.py"),
    ) == (
        ["uv", "run", "devops", "openspec", "check"],
        ("uv run devops ci --only openspec", False, ["pre-commit"]),
        [True] * 5,
        None,
    )
