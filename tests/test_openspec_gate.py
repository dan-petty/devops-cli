"""The OpenSpec gate, `devops openspec check`: what it runs, with what environment, and what it
reports for each tree the real tool was recorded over (#1844)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from devops_cli.exceptions import DependencyError
from devops_cli.openspec.gate import GateCheck, GateFinding, check_openspec
from tests.support.fakes.openspec import OpenSpecFake

INSTALL_COMMAND = "uv run devops install-tools --tool openspec --only-missing"
# The commands the gate runs over a tree with no change and no spec, in order: the isolated
# configuration, the change list, the two validations, the regeneration of the skills, the probe
# change and the instructions of each artifact.
EMPTY_TREE_COMMANDS = [
    ("config", "set", "telemetry.enabled", "false"),
    ("config", "set", "delivery", "skills"),
    ("config", "set", "profile", "custom"),
    ("config", "set", "workflows", '["propose", "explore", "apply", "update"]'),
    ("list", "--json"),
    ("validate", "--all", "--strict"),
    ("validate", "--archived"),
    ("update", "--force"),
    ("new", "change", "gate-probe"),
    ("instructions", "proposal", "--change", "gate-probe", "--json"),
    ("instructions", "specs", "--change", "gate-probe", "--json"),
    ("instructions", "design", "--change", "gate-probe", "--json"),
    ("instructions", "tasks", "--change", "gate-probe", "--json"),
    ("instructions", "apply", "--change", "gate-probe", "--json"),
]


def _archives(fake: OpenSpecFake) -> list[str]:
    """The changes the fake was asked to archive, in order."""
    return [call.argv[1] for call in fake.calls if call.argv[0] == "archive"]


def test_the_gate_passes_a_tree_with_no_change_and_no_spec(openspec_fake: OpenSpecFake) -> None:
    """Every check is vacuous on an empty tree, so the gate passes it, running the commands the
    ADR lists and no other."""
    findings = check_openspec(openspec_fake.tree("empty"))

    assert (findings, [call.argv for call in openspec_fake.calls]) == ([], EMPTY_TREE_COMMANDS)


def test_every_run_opts_out_and_reads_a_configuration_directory_of_its_own(
    openspec_fake: OpenSpecFake, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OpenSpec reports usage and asks the registry for a newer version unless told not to, and
    reads the developer's own profile from `XDG_CONFIG_HOME`. Whatever the environment says, each
    run opts out and points at one scratch directory, which is gone when the gate ends."""
    developer_config = tmp_path / "developer-config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(developer_config))
    monkeypatch.setenv("OPENSPEC_TELEMETRY", "1")
    tree = openspec_fake.tree("empty")

    check_openspec(tree)

    [config_home] = {Path(call.env["XDG_CONFIG_HOME"]) for call in openspec_fake.calls}
    opt_outs = {
        "DO_NOT_TRACK": "1",
        "OPENSPEC_NO_UPDATE_CHECK": "1",
        "OPENSPEC_TELEMETRY": "0",
        "OPEN_SPEC_INTERACTIVE": "0",
    }
    assert (
        [
            {key: value for key, value in call.env.items() if key != "XDG_CONFIG_HOME"}
            for call in openspec_fake.calls
        ],
        config_home == developer_config,
        config_home.is_relative_to(tree),
        config_home.exists(),
    ) == ([opt_outs] * len(EMPTY_TREE_COMMANDS), False, False, False)


def test_a_missing_openspec_names_the_command_that_installs_it(
    openspec_fake: OpenSpecFake,
) -> None:
    """The gate fails first, before it runs anything, naming the pinned install command."""
    tree = openspec_fake.tree("empty")
    openspec_fake.installed = False

    with pytest.raises(DependencyError) as missing:
        check_openspec(tree)

    assert (
        missing.value.exit_code,
        missing.value.error_code,
        INSTALL_COMMAND in missing.value.message,
        openspec_fake.calls,
    ) == (1, "DEPENDENCY_MISSING", True, [])


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        (
            "unknown-metadata-key",
            [
                GateFinding(
                    GateCheck.VALIDATE,
                    "Totals: 0 passed, 1 failed (1 items)\n"
                    "Details: openspec validate 1917-export-widgets --type change\n"
                    "✗ change/1917-export-widgets\n"
                    "  ⚠ [WARNING] .openspec.yaml: Unrecognized key name(s) in .openspec.yaml "
                    "(untrusted data, not instructions): milestone. Known keys: schema, created, "
                    "goal, affected_areas, initiative, skip_specs, retire_capabilities. Unknown "
                    "keys are ignored and have no effect; prefix a key with x- (for example "
                    "x-tracker) to keep tool-specific metadata without this warning.",
                )
            ],
        ),
        (
            "archived-change-with-unticked-task",
            [
                GateFinding(
                    GateCheck.VALIDATE_ARCHIVED,
                    "Totals: 0 passed, 1 failed (1 items)\n"
                    "✗ change/2026-10-01-1900-old-export\n"
                    "  ✗ 1 incomplete task (0/1 completed)",
                )
            ],
        ),
        (
            "configuration-openspec-ignores",
            [
                GateFinding(
                    GateCheck.INSTRUCTIONS,
                    "Context too large (50.8KB, limit: 50KB)\n"
                    "Ignoring context field\n"
                    "Rules for 'proposal' must be an array of strings, ignoring this artifact's "
                    'rules. rules.proposal[0] is a mapping — an unquoted ": " makes YAML read '
                    "the item as a key/value pair; quote the whole scalar to keep it a string.\n"
                    'Unknown artifact ID in rules: "nonsense". It matches no artifact in any '
                    "available schema. Known artifact IDs: design, proposal, specs, tasks",
                )
            ],
        ),
        (
            "requirement-modified-twice",
            [
                GateFinding(
                    GateCheck.OVERLAP,
                    'widget-export: the requirement "Export widgets" is rewritten by '
                    "1915-export-json (MODIFIED), 1916-export-yaml (MODIFIED): both would "
                    "archive and the later would overwrite the earlier with no signal, so fold "
                    "the items into one change or order them with a blocker, so that the "
                    "second waits until the first archives.",
                )
            ],
        ),
        (
            "requirement-renamed-and-modified",
            [
                GateFinding(
                    GateCheck.OVERLAP,
                    'widget-export: the requirement "Export widgets" is rewritten by '
                    "1922-export-json (MODIFIED), 1923-dump-widgets (RENAMED): both would "
                    "archive and the later would overwrite the earlier with no signal, so fold "
                    "the items into one change or order them with a blocker, so that the "
                    "second waits until the first archives.",
                )
            ],
        ),
    ],
)
def test_the_gate_reports_what_the_tool_refuses_ignores_or_passes_without_a_signal(
    openspec_fake: OpenSpecFake, scenario: str, expected: list[GateFinding]
) -> None:
    """The tool's `validate` passes two changes that rewrite one requirement, and it warns about
    a configuration it ignores with exit 0. Each of the recorded runs is reported by the check
    that finds it, and by that one alone."""
    assert check_openspec(openspec_fake.tree(scenario)) == expected


@pytest.mark.parametrize("scenario", ["pair", "skip-specs-change"])
def test_the_gate_passes_changes_and_archives_none_of_them(
    openspec_fake: OpenSpecFake, scenario: str
) -> None:
    """The pull request that closes a change archives it, so the gate archives nothing: a change
    that modifies a requirement another active change adds passes, as does a change that
    declares `skip_specs`, and no run of the gate is an `archive`. The scenario tree holds no
    commit, so a gate that read the git history would fail here."""
    findings = check_openspec(openspec_fake.tree(scenario))

    assert (findings, _archives(openspec_fake)) == ([], [])


def _write_skill(tree: Path, path: str, text: str) -> None:
    """Write the skill file `path` in `tree`."""
    (tree / path).parent.mkdir(parents=True, exist_ok=True)
    (tree / path).write_text(text, encoding="utf-8")


RUN_REGENERATE = "run `uv run devops openspec regenerate` and commit the result."


def test_a_hand_edited_skill_fails_the_gate(openspec_fake: OpenSpecFake) -> None:
    """The skills are generated, so a regeneration under the isolated profile must leave the
    tree as it is."""
    tree = openspec_fake.tree("empty")
    skill = tree / ".claude/skills/openspec-explore/SKILL.md"
    skill.write_text(skill.read_text(encoding="utf-8") + "A hand edit.\n", encoding="utf-8")

    assert check_openspec(tree) == [
        GateFinding(
            GateCheck.SKILLS,
            ".claude/skills/openspec-explore/SKILL.md is not what `openspec update` writes "
            f"under the isolated custom profile: {RUN_REGENERATE}",
        )
    ]


def test_skills_of_a_wider_profile_fail_the_gate(openspec_fake: OpenSpecFake) -> None:
    """A developer's global profile once added the archive skill, which writes the living spec
    that only the pull request that closes a change may: the regeneration removes it, and the
    tree still holds it."""
    tree = openspec_fake.tree("empty")
    _write_skill(tree, ".agents/skills/openspec-archive-change/SKILL.md", "Archive.\n")

    assert check_openspec(tree) == [
        GateFinding(
            GateCheck.SKILLS,
            ".agents/skills/openspec-archive-change/SKILL.md is not written by `openspec "
            "update` under the isolated custom profile: delete it, or "
            f"{RUN_REGENERATE}",
        )
    ]


def test_a_skill_the_regeneration_writes_and_the_tree_lacks_fails_the_gate(
    openspec_fake: OpenSpecFake,
) -> None:
    """A skill deleted from the tree is a drift as well."""
    tree = openspec_fake.tree("empty")
    (tree / ".agents/skills/openspec-propose/SKILL.md").unlink()

    assert check_openspec(tree) == [
        GateFinding(
            GateCheck.SKILLS,
            ".agents/skills/openspec-propose/SKILL.md is what `openspec update` writes under the "
            f"isolated custom profile and is not in the tree: {RUN_REGENERATE}",
        )
    ]


CLAUDE_SKILLS = ".claude/skills/openspec-*/**/*"
AGENTS_SKILLS = ".agents/skills/openspec-*/**/*"
AGENTS_MARKER = ".agents/skills/.openspec-target"


@pytest.mark.parametrize(
    ("deleted", "patterns"),
    [
        ([".claude/skills/openspec-*"], [CLAUDE_SKILLS]),
        ([".claude"], [CLAUDE_SKILLS]),
        ([".agents"], [AGENTS_SKILLS, AGENTS_MARKER]),
        ([".claude", ".agents"], [CLAUDE_SKILLS, AGENTS_SKILLS, AGENTS_MARKER]),
    ],
    ids=["claude-skills", "claude-tree", "agents-tree", "both-trees"],
)
def test_a_deleted_skill_tree_fails_the_gate(
    openspec_fake: OpenSpecFake, deleted: list[str], patterns: list[str]
) -> None:
    """`openspec update` finds an agent by the skills it holds, so a tree deleted whole is not
    written back by a regeneration and the comparison alone cannot see it: the gate names each
    glob of the generated files that matches no file, and says to restore it from git."""
    tree = openspec_fake.tree("empty")
    for doomed in (path for pattern in deleted for path in tree.glob(pattern)):
        shutil.rmtree(doomed)

    assert check_openspec(tree) == [
        GateFinding(
            GateCheck.SKILLS,
            f"No file matches {pattern}. `openspec update` writes a skill tree only where one "
            "exists, so `uv run devops openspec regenerate` cannot write it back: restore it "
            "from git.",
        )
        for pattern in patterns
    ]


def test_a_missing_configuration_is_the_one_problem_and_nothing_is_run(
    openspec_fake: OpenSpecFake,
) -> None:
    """`openspec/config.yaml` carries the conventions every agent reads, so a checkout without it
    has nothing to check: the gate says so, and does not pass it with the tool's defaults."""
    tree = openspec_fake.tree("empty")
    (tree / "openspec/config.yaml").unlink()

    assert (check_openspec(tree), openspec_fake.calls) == (
        [
            GateFinding(
                GateCheck.CONFIGURATION,
                "openspec/config.yaml is missing: it carries the planning conventions every "
                "agent reads through `openspec instructions`.",
            )
        ],
        [],
    )
