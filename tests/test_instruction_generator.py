"""Unit tests for AI agent instruction generator and scaffolding utilities."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

from devops_cli.ai.instruction_generator import (
    CONST_CLAUDE_MD_FILENAME,
    CONST_COPILOT_INSTRUCTIONS_PATH,
    CONST_GEMINI_MD_FILENAME,
    ProjectMetadata,
    generate_agents_md,
    generate_instruction_content,
    generate_pointer_stub,
    parse_project_metadata,
    scaffold_agent_instructions,
)
from devops_cli.commands.ai import app as ai_app
from devops_cli.commands.devcontainer import app as devcontainer_app
from devops_cli.config.constants import (
    CONST_AGENTS_MD_FILENAME,
    CONST_AGENTS_MD_MAX_CHARS,
    CONST_AGENTS_MD_ROUTES,
)
from devops_cli.config.defaults import DEFAULT_AGENTS_MD_CHECK_COMMANDS
from tests.support.paths import REPO_ROOT

CONST_DELETED_PROCESS_TERMS: Final[tuple[str, ...]] = (
    "release branch",
    "`release/",
    "release/*",
    "release/v",
    "the cut",
    "cut PR",
    "changelog fragment",
    "changelog.d",
    "towncrier",
    "Part of #",
    "roadmap reprioritize",
    "roadmap close",
    "roadmap render",
    "roadmap migrate",
    "docs/ROADMAP.md",
    "devops release",
    "filing quota",
    "budget/borrowed",
    "#1153",
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_parse_project_metadata_with_pyproject(tmp_path: Path) -> None:
    """Verify parse_project_metadata extracts accurate project details from pyproject.toml."""
    pyproject_toml = """\
[project]
name = "sample-service"
version = "1.2.3"
description = "High performance API gateway"
requires-python = ">=3.14"
dependencies = ["fastapi>=0.110.0"]

[project.scripts]
sample-service = "sample_service.cli:app"

[dependency-groups]
dev = ["pytest>=8.0.0", "ruff>=0.9.0"]
"""
    (tmp_path / "pyproject.toml").write_text(pyproject_toml, encoding="utf-8")

    meta = parse_project_metadata(tmp_path)
    assert meta.name == "sample-service"
    assert meta.version == "1.2.3"
    assert meta.description == "High performance API gateway"
    assert meta.requires_python == ">=3.14"
    assert "sample-service" in meta.entry_point
    assert "fastapi>=0.110.0" in meta.dependencies
    assert "pytest>=8.0.0" in meta.dev_dependencies


def test_parse_project_metadata_fallback_when_no_pyproject(tmp_path: Path) -> None:
    """Verify fallback behavior when no pyproject.toml exists."""
    meta = parse_project_metadata(tmp_path)
    assert meta.name == tmp_path.name
    assert meta.version == "0.1.0"
    assert meta.requires_python == ">=3.14"


def test_generate_pointer_stub() -> None:
    """Verify each pointer stub sends its tool to the router AGENTS.md and repeats none of it."""
    claude_stub = generate_pointer_stub(
        title="Sample — Claude Instructions",
        tool_name="Claude Code",
        filename="CLAUDE.md",
        canonical_relpath="./AGENTS.md",
        import_line="@AGENTS.md",
    )
    gemini_stub = generate_pointer_stub(
        title="Sample — Gemini CLI Instructions",
        tool_name="Gemini CLI",
        filename=CONST_GEMINI_MD_FILENAME,
        canonical_relpath="./AGENTS.md",
        import_line="@./AGENTS.md",
    )
    assert (
        "# Sample — Claude Instructions" in claude_stub,
        "\n@AGENTS.md\n" in claude_stub,
        "[AGENTS.md](./AGENTS.md)" in claude_stub,
        "holds the rules for every task" in claude_stub,
        "devops ai agents" in claude_stub,
        "# Sample — Gemini CLI Instructions" in gemini_stub,
        "Gemini CLI looks specifically for\n> `GEMINI.md`" in gemini_stub,
        "\n@./AGENTS.md\n" in gemini_stub,
        "\n@AGENTS.md\n" not in gemini_stub,
    ) == (True, True, True, True, True, True, True, True, True)

    # The stub says to duplicate nothing, so it holds no rule of its own.
    assert [
        needle
        for needle in ("Pre-1.0 Alpha Notice", "Semantic Versioning", "All actual instructions")
        if needle in claude_stub + gemini_stub
    ] == []

    # Negative control: a stub whose tool reads no import line carries none.
    stub_without_import = generate_pointer_stub(
        title="Sample — GitHub Copilot Instructions",
        tool_name="GitHub Copilot",
        filename=CONST_COPILOT_INSTRUCTIONS_PATH,
        canonical_relpath="../AGENTS.md",
    )
    assert (
        [line for line in stub_without_import.splitlines() if line.startswith("@")],
        "[AGENTS.md](../AGENTS.md)" in stub_without_import,
    ) == ([], True)


@pytest.mark.parametrize(
    ("target_file", "title_suffix", "tool_name", "canonical_link", "import_lines"),
    [
        ("CLAUDE.md", "Claude Instructions", "Claude Code", "(./AGENTS.md)", ["@AGENTS.md"]),
        (
            "GEMINI.md",
            "Gemini CLI Instructions",
            "Gemini CLI",
            "(./AGENTS.md)",
            ["@./AGENTS.md"],
        ),
        (
            ".github/copilot-instructions.md",
            "GitHub Copilot Instructions",
            "GitHub Copilot",
            "(../AGENTS.md)",
            [],
        ),
    ],
)
def test_instruction_content_for_each_pointer_stub_comes_from_its_table_row(
    target_file: str,
    title_suffix: str,
    tool_name: str,
    canonical_link: str,
    import_lines: list[str],
) -> None:
    """Verify each stub file name selects its own title, tool, link and import line."""
    meta = ProjectMetadata(name="sample-project")
    content = generate_instruction_content(target_file, meta)
    assert (
        content.startswith(f"# sample-project — {title_suffix}\n"),
        f"{tool_name} looks specifically for\n> `{target_file}`" in content,
        f"[AGENTS.md]{canonical_link}" in content,
        [line for line in content.splitlines() if line.startswith("@")],
    ) == (True, True, True, import_lines)


def test_instruction_content_for_a_stub_path_ignores_a_leading_dot_slash() -> None:
    """Verify `./GEMINI.md` and `./.github/copilot-instructions.md` still select their stubs."""
    meta = ProjectMetadata(name="sample-project")
    assert [
        generate_instruction_content(f"./{target}", meta).splitlines()[0]
        for target in (CONST_GEMINI_MD_FILENAME, CONST_COPILOT_INSTRUCTIONS_PATH)
    ] == [
        "# sample-project — Gemini CLI Instructions",
        "# sample-project — GitHub Copilot Instructions",
    ]


def test_generated_agents_md_is_a_router(tmp_path: Path) -> None:
    """Verify the generated AGENTS.md holds the purpose, the rules for every task and a table
    that routes each kind of task to a document, within the size cap (#1961)."""
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    meta = parse_project_metadata(tmp_path).model_copy(
        update={
            "name": "sample-project",
            "description": "Workstation automation scripts",
            "entry_point": "sample (sample.main:app)",
        }
    )
    content = generate_agents_md(meta)
    headings = [line for line in content.splitlines() if line.startswith("#")]

    assert (
        headings,
        "Workstation automation scripts" in content,
        "`sample (sample.main:app)`" in content,
        "Canonical Source" in content,
        "| When you | Read |" in content,
        "| set up, name a branch, write a pull request title, run one check | "
        "[CONTRIBUTING.md](CONTRIBUTING.md) |" in content,
        len(content) <= CONST_AGENTS_MD_MAX_CHARS,
    ) == (
        [
            "# sample-project — AI Agent Instructions",
            "## Rules for every task",
            "## Where to look",
        ],
        True,
        True,
        True,
        True,
        True,
        True,
    )


def test_generated_agents_md_names_the_pre_push_checks_of_the_project(tmp_path: Path) -> None:
    """Verify the push rule names the project's own pre-push hooks, and the uv defaults only for
    a project that has none."""
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: lint\n"
        "        entry: make lint\n"
        "        stages: [pre-commit]\n"
        "      - id: gate\n"
        "        entry: make check\n"
        "        stages: [pre-push]\n",
        encoding="utf-8",
    )
    bare = tmp_path / "bare"
    bare.mkdir()

    hooked = generate_agents_md(parse_project_metadata(tmp_path))
    defaults = generate_agents_md(parse_project_metadata(bare))

    assert (
        "`make check`" in hooked,
        "make lint" in hooked,
        "uv run pytest" in hooked,
        all(f"`{command}`" in defaults for command in DEFAULT_AGENTS_MD_CHECK_COMMANDS),
    ) == (True, False, False, True)


def test_generated_agents_md_leaves_the_writing_standard_to_the_project() -> None:
    """Verify the generated router names no writing standard: each project owns its own, and the
    ASD-STE100 rule is devops-cli's (owner decision D2 of #1961)."""
    content = generate_agents_md(ProjectMetadata(name="sample-project"))
    assert (
        "ASD-STE100" in content,
        "ASD-STE100" in (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8"),
    ) == (
        False,
        True,
    )


def test_scaffold_agent_instructions(tmp_path: Path) -> None:
    """Verify scaffold_agent_instructions writes all default files."""
    written = scaffold_agent_instructions(tmp_path)
    agents_md = tmp_path / CONST_AGENTS_MD_FILENAME
    claude_md = tmp_path / CONST_CLAUDE_MD_FILENAME
    gemini_md = tmp_path / CONST_GEMINI_MD_FILENAME
    copilot_md = tmp_path / CONST_COPILOT_INSTRUCTIONS_PATH

    assert (
        len(written),
        agents_md.exists(),
        claude_md.exists(),
        gemini_md.exists(),
        copilot_md.exists(),
    ) == (4, True, True, True, True)

    assert (
        f"# {tmp_path.name}" in agents_md.read_text(encoding="utf-8"),
        "Claude Code" in claude_md.read_text(encoding="utf-8"),
        "Gemini CLI" in gemini_md.read_text(encoding="utf-8"),
        "GitHub Copilot" in copilot_md.read_text(encoding="utf-8"),
    ) == (True, True, True, True)


def test_scaffold_agent_instructions_skip_existing_without_force(tmp_path: Path) -> None:
    """Verify existing files are not overwritten unless force=True."""
    agents_md = tmp_path / CONST_AGENTS_MD_FILENAME
    agents_md.write_text("Custom instruction content", encoding="utf-8")

    # Call without force
    written = scaffold_agent_instructions(tmp_path, force=False)
    assert (agents_md not in written, agents_md.read_text(encoding="utf-8")) == (
        True,
        "Custom instruction content",
    )

    # Call with force
    written_force = scaffold_agent_instructions(tmp_path, force=True)
    assert (
        agents_md in written_force,
        "Canonical Source" in agents_md.read_text(encoding="utf-8"),
    ) == (
        True,
        True,
    )


def test_scaffold_agent_instructions_skips_an_existing_gemini_stub_without_force(
    tmp_path: Path,
) -> None:
    """Verify an existing GEMINI.md is left alone without force and rewritten with it."""
    gemini_md = tmp_path / CONST_GEMINI_MD_FILENAME
    gemini_md.write_text("Custom Gemini content", encoding="utf-8")

    written = scaffold_agent_instructions(tmp_path, force=False)
    assert (gemini_md in written, gemini_md.read_text(encoding="utf-8")) == (
        False,
        "Custom Gemini content",
    )

    written_force = scaffold_agent_instructions(tmp_path, force=True)
    assert (gemini_md in written_force, "Gemini CLI" in gemini_md.read_text(encoding="utf-8")) == (
        True,
        True,
    )


def test_devcontainer_init_scaffolds_agent_instructions(runner: CliRunner, tmp_path: Path) -> None:
    """Verify devops devcontainer init scaffolds AGENTS.md, CLAUDE.md, and copilot instructions."""
    result = runner.invoke(devcontainer_app, ["init", str(tmp_path), "--name", "init-test-proj"])
    assert (
        result.exit_code,
        (tmp_path / ".devcontainer" / "devcontainer.json").exists(),
        (tmp_path / ".vscode" / "mcp.json").exists(),
        (tmp_path / "AGENTS.md").exists(),
        (tmp_path / "CLAUDE.md").exists(),
        (tmp_path / "GEMINI.md").exists(),
        (tmp_path / ".github" / "copilot-instructions.md").exists(),
    ) == (0, True, True, True, True, True, True)


def test_devcontainer_post_create_scaffolds_agent_instructions(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify devops devcontainer post-create scaffolds missing agent instructions."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    # Every program answers as installed, as in the published image, so post-create runs no
    # installer: on a host without claude it ran Claude Code's real installer, a 276 MB download.
    monkeypatch.setattr("shutil.which", lambda cmd, *_args, **_kwargs: f"/usr/local/bin/{cmd}")

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "post-create-proj"\n', encoding="utf-8"
    )

    # Dry-run test
    res_dry = runner.invoke(
        devcontainer_app,
        ["post-create", "--workspace", str(tmp_path), "--dry-run"],
    )
    assert res_dry.exit_code == 0

    # Live execution test. --skip-tools keeps uv from installing the locked semgrep and bandit
    # from PyPI into the test's data directory.
    res_live = runner.invoke(
        devcontainer_app,
        ["post-create", "--workspace", str(tmp_path), "--skip-tools"],
    )
    assert (
        res_live.exit_code,
        (tmp_path / "AGENTS.md").exists(),
        (tmp_path / "CLAUDE.md").exists(),
        (tmp_path / "GEMINI.md").exists(),
        (tmp_path / ".github" / "copilot-instructions.md").exists(),
    ) == (0, True, True, True, True)


def test_ai_agents_command_scaffolds_instructions(runner: CliRunner, tmp_path: Path) -> None:
    """Verify devops ai agents command scaffolds files in target repository."""
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "ai-test-proj"\ndescription = "Testing AI agents generation"',
        encoding="utf-8",
    )

    result = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path), "--template"])
    assert (
        result.exit_code,
        (tmp_path / "AGENTS.md").exists(),
        (tmp_path / "CLAUDE.md").exists(),
        (tmp_path / "GEMINI.md").exists(),
        (tmp_path / ".github" / "copilot-instructions.md").exists(),
        "Testing AI agents generation" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8"),
    ) == (0, True, True, True, True, True)


def test_ai_agents_file_option_writes_only_the_gemini_stub_without_a_model_call(
    runner: CliRunner, tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify `devops ai agents --file GEMINI.md` writes the stub alone and calls no model."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "gemini-proj"\n', encoding="utf-8")

    result = runner.invoke(
        ai_app, ["agents", "--repo", str(tmp_path), "--file", CONST_GEMINI_MD_FILENAME]
    )
    gemini_stub = (tmp_path / CONST_GEMINI_MD_FILENAME).read_text(encoding="utf-8")
    assert (
        result.exit_code,
        sorted(path.name for path in tmp_path.iterdir() if path.is_file()),
        gemini_stub.splitlines()[0],
        "\n@./AGENTS.md\n" in gemini_stub,
        model_fake.call_count,
    ) == (
        0,
        ["GEMINI.md", "pyproject.toml"],
        "# gemini-proj — Gemini CLI Instructions",
        True,
        0,
    )


@pytest.mark.live("find")
def test_ai_agents_replaces_a_model_answer_over_the_cap_with_the_router(
    runner: CliRunner, tmp_path: Path, model_fake: ModelFake, config: Callable[..., Path]
) -> None:
    """Verify the model is told the size cap and the documents that exist, and an answer longer
    than the cap is replaced by the template router (#1961)."""
    config(ai={"rag": {"enabled": False}})
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "model-proj"\n', encoding="utf-8")
    (tmp_path / "CONTRIBUTING.md").write_text("# Contributing\n", encoding="utf-8")
    model_fake.answer("# model-proj\n" + "Rule.\n" * CONST_AGENTS_MD_MAX_CHARS)

    result = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path), "--file", "AGENTS.md"])
    [call] = model_fake.calls

    assert (
        result.exit_code,
        (tmp_path / "AGENTS.md").read_text(encoding="utf-8"),
        f"{CONST_AGENTS_MD_MAX_CHARS} characters" in call.system,
        "`CONTRIBUTING.md`" in call.system,
        "`SECURITY.md`" in call.system,
        "Generate the contents of" in call.user,
    ) == (0, generate_agents_md(parse_project_metadata(tmp_path)), True, True, False, False)


def test_instruction_generator_corrupt_pyproject_and_force_modes(tmp_path: Path) -> None:
    """Verify a corrupt pyproject.toml falls back to the directory name, and scaffold force/skip
    behavior."""
    # 1. Corrupt pyproject.toml handling
    bad_proj = tmp_path / "bad_proj"
    bad_proj.mkdir()
    (bad_proj / "pyproject.toml").write_text("invalid [toml content", encoding="utf-8")
    meta_corrupt = parse_project_metadata(bad_proj)
    assert meta_corrupt.name == "bad_proj"

    # 2. scaffold_agent_instructions force vs skip
    target_dir = tmp_path / "scaffold_test"
    target_dir.mkdir()
    (target_dir / "AGENTS.md").write_text("Existing AGENTS.md", encoding="utf-8")

    # Without force -> skip
    written_skip = scaffold_agent_instructions(target_dir, files=["AGENTS.md"], force=False)
    assert len(written_skip) == 0
    assert (target_dir / "AGENTS.md").read_text(encoding="utf-8") == "Existing AGENTS.md"

    # With force -> overwrite
    written_force = scaffold_agent_instructions(target_dir, files=["AGENTS.md"], force=True)
    assert len(written_force) == 1
    assert "AI Agent Instructions" in (target_dir / "AGENTS.md").read_text(encoding="utf-8")


def test_generate_agents_md_opens_every_pull_request_as_a_draft() -> None:
    """Verify generated AGENTS.md opens every pull request as a draft, with no condition, and
    names `devops pr ready` as the way out of the draft."""
    meta = ProjectMetadata(
        name="sample-project",
        description="Sample project testing draft PR rules",
        version="0.2.0",
        requires_python=">=3.14",
    )
    content = generate_agents_md(meta)
    assert (
        "open every pull request with `devops pr create`, which always opens a draft" in content,
        "devops pr ready" in content,
        "not yet fully implemented" in content,
    ) == (True, True, False)


def test_generated_agents_md_targets_the_default_branch_and_names_no_deleted_process(
    tmp_path: Path,
) -> None:
    """Verify generated AGENTS.md sends topic pull requests to the default branch and names no
    deleted process, such as a release branch, the cut or the filing quota, for a project with
    every routed document and for one with none."""
    for path, _task in CONST_AGENTS_MD_ROUTES:
        target = tmp_path / path
        if path.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("# Doc\n", encoding="utf-8")
    for content in (
        generate_agents_md(ProjectMetadata(name="sample-project")),
        generate_agents_md(parse_project_metadata(tmp_path)),
    ):
        assert (
            "PRs target the default branch" in content,
            [term for term in CONST_DELETED_PROCESS_TERMS if term in content],
        ) == (True, [])


def test_generate_agents_md_enforces_pr_monitor_and_ready() -> None:
    """Verify generated AGENTS.md has agents watch each pull request with `devops pr monitor`
    and mark it ready with `devops pr ready`; the command's defaults set the wait and the poll
    interval, so the document states no timing of its own."""
    content = generate_agents_md(
        ProjectMetadata(
            name="sample-project",
            description="Sample project testing PR monitoring",
            version="0.2.0",
            requires_python=">=3.14",
        )
    )
    assert (
        "devops pr monitor <pr_number>" in content,
        "devops pr ready <pr_number>" in content,
        "Copilot reviews a pull request only when a person requests it" in content,
        "60 seconds" in content,
        "5 minutes" in content,
    ) == (True, True, True, False, False)


def test_ai_agents_force_guard_and_refusal(
    runner: CliRunner, tmp_path: Path, model_fake: ModelFake
) -> None:
    """Verify devops ai agents refuses to overwrite AGENTS.md without --force while writing stubs."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-guard"\n', encoding="utf-8")
    agents_file = tmp_path / "AGENTS.md"
    original_bytes = b"# Original AGENTS.md\n"
    agents_file.write_bytes(original_bytes)

    claude_stub = tmp_path / "CLAUDE.md"
    copilot_stub = tmp_path / ".github" / "copilot-instructions.md"

    # 1. First run without --force: exits non-zero, leaves AGENTS.md untouched, writes stubs
    res1 = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path), "--template"])
    assert (
        res1.exit_code != 0,
        agents_file.read_bytes() == original_bytes,
        claude_stub.exists(),
        copilot_stub.exists(),
    ) == (True, True, True, True)

    # 2. Second run with --force: overwrites AGENTS.md and exits 0
    res2 = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path), "--template", "--force"])
    assert (
        res2.exit_code,
        agents_file.read_bytes() != original_bytes,
    ) == (0, True)

    # 3. Third run with --file CLAUDE.md and no --force exits 0
    res3 = runner.invoke(
        ai_app, ["agents", "--repo", str(tmp_path), "--template", "--file", "CLAUDE.md"]
    )
    assert res3.exit_code == 0

    # 4. Refused run never constructs or invokes the model client
    agents_file.write_bytes(original_bytes)
    res4 = runner.invoke(ai_app, ["agents", "--repo", str(tmp_path)])
    assert (res4.exit_code != 0, model_fake.call_count == 0) == (True, True)


def test_generate_agents_md_root_cause_and_premise_rules() -> None:
    """Verify the generated router keeps the root-cause rule and the premise-and-stop rule, and
    no rule files an item into a milestone or a roadmap document (#742, #1959)."""
    content = generate_agents_md(
        ProjectMetadata(
            name="sample-project",
            description="Sample project testing core engineering rules",
            version="0.2.0",
            requires_python=">=3.14",
        )
    )
    expected = (
        "Fix the cause.",
        "add a check that fails when the problem returns",
        "Check the premise first.",
        "write no compensating code",
    )
    ingestion_rules = (
        "Automatic Roadmap Ingestion",
        "STRUCTURED ROADMAP TASKS",
        "MUST FILE A CANDIDATE ISSUE (`devops gh issues create`)",
        "release_credit",
        "Continuous Interaction & Collaborative Value Improvement",
    )
    assert (
        [rule for rule in expected if rule not in content],
        [rule for rule in ingestion_rules if rule in content],
    ) == ([], [])
