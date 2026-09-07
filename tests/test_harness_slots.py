"""Unit and integration tests for Agent Harness Slots, Sub-Agent Offloading, and Tiered Synthesis."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.harness.skills import ParsedSkill
from devops_cli.ai.harness.slots import (
    AgentHarness,
    BaseSlot,
    ModelSlot,
    SkillSlot,
    SlotState,
    SlotType,
    SubAgentResult,
    SubAgentSlot,
    SynthesisTier,
    TieredExecutionResult,
    TokenSavingsSummary,
    ToolSlot,
)
from devops_cli.ai.router import TaskComplexity
from devops_cli.commands.ai import app as ai_app
from devops_cli.exceptions.ai import HarnessValidationError


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def sample_repo_path(tmp_path: Path) -> Path:
    """Create a mock repository structure with Python source files."""
    pkg_dir = tmp_path / "sample_pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    init_file = pkg_dir / "__init__.py"
    init_file.write_text('"""Sample package init."""\n', encoding="utf-8")

    core_file = pkg_dir / "core.py"
    core_file.write_text(
        '''"""Core module."""

class DataProcessor:
    """Processes pipeline data."""

    def __init__(self, name: str) -> None:
        self.name = name

    def process(self, items: list[str]) -> list[str]:
        """Transform input items."""
        return [item.upper() for item in items]

def compute_metrics(values: list[float]) -> dict[str, float]:
    """Calculate summary metrics."""
    return {"avg": sum(values) / len(values) if values else 0.0}
''',
        encoding="utf-8",
    )

    util_file = pkg_dir / "utils.py"
    util_file.write_text(
        '''"""Utility functions."""

def sanitize_input(val: str) -> str:
    """Strip whitespace and lower."""
    return val.strip().lower()
''',
        encoding="utf-8",
    )
    return tmp_path


def test_slot_enums() -> None:
    """Verify SlotState, SlotType, and SynthesisTier enum values."""
    assert SlotState.EMPTY == "empty"
    assert SlotState.ATTACHED == "attached"
    assert SlotState.ACTIVE == "active"
    assert SlotState.FAILED == "failed"
    assert SlotState.DETACHED == "detached"

    assert SlotType.MODEL == "model"
    assert SlotType.SKILL == "skill"
    assert SlotType.TOOL == "tool"
    assert SlotType.SUBAGENT == "subagent"

    assert SynthesisTier.DECIDE == "decide"
    assert SynthesisTier.TYPE == "type"
    assert SynthesisTier.CHECK == "check"


def test_base_slot_lifecycle() -> None:
    """Verify BaseSlot lifecycle state transitions."""
    slot = BaseSlot(name="test_slot", slot_type=SlotType.MODEL)
    assert slot.state == SlotState.EMPTY
    assert not slot.is_ready()

    slot.attach()
    assert slot.state == SlotState.ATTACHED
    assert slot.is_ready()

    slot.detach()
    assert slot.state == SlotState.DETACHED
    assert not slot.is_ready()


def test_model_slot_lifecycle_and_swapping() -> None:
    """Verify ModelSlot initialization, token estimation, swapping, and local check."""
    slot = ModelSlot(
        name="frontier_model",
        slot_type=SlotType.MODEL,
        provider="claude",
        model_name="claude-3-7-sonnet",
        tier=TaskComplexity.FRONTIER,
        is_local=False,
    )
    slot.attach()
    assert slot.is_ready()
    assert slot.provider == "claude"
    assert slot.model_name == "claude-3-7-sonnet"
    assert not slot.is_local

    # Token estimation
    tokens = slot.estimate_tokens("A quick brown fox jumps over the lazy dog.")
    assert tokens > 0

    # Ensure local fails on cloud model
    with pytest.raises(HarnessValidationError, match="must be local"):
        slot.ensure_local()

    # Swap model to local Ollama Qwen2.5-Coder
    slot.swap_model(
        provider="ollama",
        model_name="qwen2.5-coder:7b",
        tier=TaskComplexity.LOW,
        is_local=True,
    )
    assert slot.provider == "ollama"
    assert slot.model_name == "qwen2.5-coder:7b"
    assert slot.is_local
    # Now ensure_local should succeed without error
    slot.ensure_local()


def test_skill_slot_attach_detach(tmp_path: Path) -> None:
    """Verify SkillSlot registration, lookup, detachment, and prompt synthesis."""
    slot = SkillSlot(name="skills", slot_type=SlotType.SKILL)
    slot.attach()

    skill1 = ParsedSkill(
        name="ast-inspection",
        description="Inspects Python AST syntax trees",
        body="## Guidelines\nUse ast.parse to inspect symbols.",
        directory=tmp_path / "ast-inspection",
        loaded=True,
    )
    skill2 = ParsedSkill(
        name="git-diff",
        description="Analyzes unified diff hunks",
        body="## Guidelines\nCheck line numbers and additions.",
        directory=tmp_path / "git-diff",
        loaded=True,
    )

    slot.attach_skill(skill1)
    slot.attach_skill(skill2)

    assert slot.has_skill("ast-inspection")
    assert slot.has_skill("git-diff")
    assert not slot.has_skill("non-existent")

    prompts = slot.get_skill_prompts()
    assert len(prompts) == 2
    assert any("ast-inspection" in p for p in prompts)
    assert any("git-diff" in p for p in prompts)

    # Detach one skill
    detached = slot.detach_skill("ast-inspection")
    assert detached is True
    assert not slot.has_skill("ast-inspection")
    assert slot.has_skill("git-diff")

    # Detach non-existent
    assert slot.detach_skill("unknown") is False


def test_tool_slot_read_only_isolation() -> None:
    """Verify ToolSlot read-only filtering hides mutating functions."""

    def read_file(path: str) -> str:
        return "content"

    def search_symbols(query: str) -> list[str]:
        return ["found"]

    def write_file(path: str, data: str) -> bool:
        return True

    def delete_file(path: str) -> bool:
        return True

    slot = ToolSlot(name="tools", slot_type=SlotType.TOOL)
    slot.attach()

    slot.attach_tool(read_file)
    slot.attach_tool(search_symbols)
    slot.attach_tool(write_file)
    slot.attach_tool(delete_file)

    # Unfiltered tools
    assert len(slot.get_active_tools()) == 4

    # Enable read-only sandboxing
    slot.set_read_only(True)
    active = slot.get_active_tools()
    active_names = [getattr(t, "__name__", str(t)) for t in active]

    assert "read_file" in active_names
    assert "search_symbols" in active_names
    assert "write_file" not in active_names
    assert "delete_file" not in active_names

    # Detach tool
    detached = slot.detach_tool("read_file")
    assert detached is True
    assert "read_file" not in [getattr(t, "__name__", str(t)) for t in slot.get_active_tools()]


def test_subagent_slot_ast_offloading(sample_repo_path: Path) -> None:
    """Verify SubAgentSlot offload_ast_search indexes Python classes and functions."""
    slot = SubAgentSlot(name="subagent_slot", slot_type=SlotType.SUBAGENT)
    slot.attach()

    # Search for DataProcessor class
    res = slot.offload_ast_search(sample_repo_path, "DataProcessor")
    assert res.status == "success"
    assert "DataProcessor" in res.output
    assert res.tokens_used > 0
    assert len(res.data.get("matches", [])) == 1
    match = res.data["matches"][0]
    assert match["name"] == "DataProcessor"
    assert match["kind"] == "class"

    # Search for compute_metrics function
    fn_res = slot.offload_ast_search(sample_repo_path, "compute_metrics")
    assert fn_res.status == "success"
    assert len(fn_res.data.get("matches", [])) == 1
    assert fn_res.data["matches"][0]["kind"] == "function"

    # Search for non-existent symbol
    missing = slot.offload_ast_search(sample_repo_path, "NoSuchSymbol")
    assert missing.status == "success"
    assert len(missing.data.get("matches", [])) == 0


def test_subagent_slot_file_scout(sample_repo_path: Path) -> None:
    """Verify SubAgentSlot offload_file_scout locates source files."""
    slot = SubAgentSlot(name="subagent_slot", slot_type=SlotType.SUBAGENT)
    slot.attach()

    res = slot.offload_file_scout(sample_repo_path, "*.py")
    assert res.status == "success"
    files = res.data.get("files", [])
    assert len(files) >= 3
    assert any("core.py" in f for f in files)
    assert any("utils.py" in f for f in files)


def test_subagent_slot_symbol_catalog(sample_repo_path: Path) -> None:
    """Verify SubAgentSlot offload_symbol_catalog inventories repo symbols."""
    slot = SubAgentSlot(name="subagent_slot", slot_type=SlotType.SUBAGENT)
    slot.attach()

    catalog_res = slot.offload_symbol_catalog(sample_repo_path)
    assert catalog_res.status == "success"
    symbols = catalog_res.data.get("symbols", [])
    symbol_names = [s["name"] for s in symbols]
    assert "DataProcessor" in symbol_names
    assert "compute_metrics" in symbol_names
    assert "sanitize_input" in symbol_names


def test_token_savings_calculation() -> None:
    """Verify TokenSavingsSummary calculation and 85% target threshold."""
    # Exceeding 85% savings target (e.g. 150 frontier tokens, 850 offloaded tokens)
    s1 = TokenSavingsSummary.calculate(frontier_tokens=150, offloaded_tokens=850)
    assert s1.frontier_tokens == 150
    assert s1.offloaded_tokens == 850
    assert s1.baseline_frontier_without_offload == 1000
    assert s1.savings_percentage == 85.0
    assert s1.is_target_met is True

    # 90% savings
    s2 = TokenSavingsSummary.calculate(frontier_tokens=100, offloaded_tokens=900)
    assert s2.savings_percentage == 90.0
    assert s2.is_target_met is True

    # Below 85% savings target (e.g. 500 frontier tokens, 500 offloaded tokens)
    s3 = TokenSavingsSummary.calculate(frontier_tokens=500, offloaded_tokens=500)
    assert s3.savings_percentage == 50.0
    assert s3.is_target_met is False

    # Zero baseline edge case
    s4 = TokenSavingsSummary.calculate(frontier_tokens=0, offloaded_tokens=0)
    assert s4.savings_percentage == 0.0
    assert s4.is_target_met is False


def test_agent_harness_create_default() -> None:
    """Verify AgentHarness default constructor sets up all 4 slots."""
    harness = AgentHarness.create_default(
        frontier_model="claude-3-7-sonnet",
        local_model="qwen2.5-coder:7b",
    )
    assert harness.validate_invariants() is True
    assert harness.model_slot.model_name == "claude-3-7-sonnet"
    assert harness.model_slot.is_local is False
    assert harness.subagent_slot.model_slot.model_name == "qwen2.5-coder:7b"
    assert harness.subagent_slot.model_slot.is_local is True
    assert harness.subagent_slot.tool_slot.read_only is True


def test_tiered_synthesis_protocol_execution(sample_repo_path: Path) -> None:
    """Verify AgentHarness execute_tiered follows the 3-tier synthesis protocol."""
    harness = AgentHarness.create_default()

    task_description = "Locate DataProcessor and verify processing logic"
    result: TieredExecutionResult = harness.execute_tiered(
        task=task_description,
        repo_path=sample_repo_path,
        symbol_query="DataProcessor",
    )

    assert result.status == "completed"
    assert result.task == task_description
    assert "DataProcessor" in result.decision_plan
    assert len(result.subagent_results) >= 1
    assert isinstance(result.subagent_results[0], SubAgentResult)
    assert result.subagent_results[0].status == "success"
    assert "DataProcessor" in result.verification_report
    assert result.savings.offloaded_tokens > 0


def test_harness_failure_isolation(tmp_path: Path) -> None:
    """Verify that sub-agent query errors do not crash the harness."""
    harness = AgentHarness.create_default()

    # Query in an empty non-existent directory
    bogus_dir = tmp_path / "non_existent_folder"
    result = harness.execute_tiered(
        task="Investigate missing module",
        repo_path=bogus_dir,
        symbol_query="MissingSymbol",
    )
    # The harness should gracefully complete with status completed or partial
    assert result.status in ("completed", "partial")
    assert len(result.subagent_results) >= 1


def test_cli_ai_harness_status(runner: CliRunner) -> None:
    """Verify devops ai harness status CLI command renders slots overview."""
    result = runner.invoke(ai_app, ["harness", "status"])
    assert result.exit_code == 0
    assert "Agent Harness Slots" in result.stdout
    assert "ModelSlot" in result.stdout
    assert "SkillSlot" in result.stdout
    assert "ToolSlot" in result.stdout
    assert "SubAgentSlot" in result.stdout


def test_cli_ai_harness_offload(runner: CliRunner, sample_repo_path: Path) -> None:
    """Verify devops ai harness offload CLI command executes AST search."""
    result = runner.invoke(
        ai_app,
        [
            "harness",
            "offload",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
        ],
    )
    assert result.exit_code == 0
    assert "Sub-Agent Local Offload" in result.stdout
    assert "DataProcessor" in result.stdout
    assert "Token Savings" in result.stdout


def test_cli_ai_harness_status_json(runner: CliRunner) -> None:
    """Verify devops ai harness status --format json returns structured JSON."""
    result = runner.invoke(ai_app, ["harness", "status", "--format", "json"])
    assert result.exit_code == 0
    assert '"model_slot"' in result.stdout
    assert '"subagent_slot"' in result.stdout


def test_cli_ai_harness_offload_pattern_and_catalog(
    runner: CliRunner, sample_repo_path: Path
) -> None:
    """Verify offload with pattern and catalog defaults."""
    # Pattern scout
    res_pattern = runner.invoke(
        ai_app,
        ["harness", "offload", "--repo", str(sample_repo_path), "--pattern", "*.py"],
    )
    assert res_pattern.exit_code == 0
    assert "Sub-Agent Local Offload" in res_pattern.stdout

    # Symbol catalog (default when no symbol or pattern specified)
    res_catalog = runner.invoke(
        ai_app,
        ["harness", "offload", "--repo", str(sample_repo_path)],
    )
    assert res_catalog.exit_code == 0
    assert "Sub-Agent Local Offload" in res_catalog.stdout


def test_cli_ai_harness_offload_dry_run_and_json(runner: CliRunner, sample_repo_path: Path) -> None:
    """Verify dry-run and JSON output modes for offload command."""
    # Dry run
    res_dry = runner.invoke(
        ai_app,
        [
            "harness",
            "offload",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
            "--dry-run",
        ],
    )
    assert res_dry.exit_code == 0
    assert "DRY RUN" in res_dry.stdout or "subagent_offload" in res_dry.stdout

    # JSON output
    res_json = runner.invoke(
        ai_app,
        [
            "harness",
            "offload",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
            "--format",
            "json",
        ],
    )
    assert res_json.exit_code == 0
    assert '"result"' in res_json.stdout
    assert '"savings"' in res_json.stdout


def test_cli_ai_harness_run_command(runner: CliRunner, sample_repo_path: Path) -> None:
    """Verify devops ai harness run command executes 3-tier synthesis protocol."""
    result = runner.invoke(
        ai_app,
        [
            "harness",
            "run",
            "Inspect DataProcessor implementation",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
        ],
    )
    assert result.exit_code == 0
    assert "Tiered Synthesis Execution" in result.stdout
    assert "Tier 1 (Big Decides)" in result.stdout
    assert "Tier 2 (Small Types)" in result.stdout
    assert "Tier 3 (Big Checks)" in result.stdout
    assert "Token Savings" in result.stdout


def test_cli_ai_harness_run_dry_run_and_json(runner: CliRunner, sample_repo_path: Path) -> None:
    """Verify devops ai harness run dry-run and JSON modes."""
    # Dry run
    res_dry = runner.invoke(
        ai_app,
        [
            "harness",
            "run",
            "Inspect DataProcessor implementation",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
            "--dry-run",
        ],
    )
    assert res_dry.exit_code == 0
    assert "DRY RUN" in res_dry.stdout or "execute_tiered_synthesis" in res_dry.stdout

    # JSON output
    res_json = runner.invoke(
        ai_app,
        [
            "harness",
            "run",
            "Inspect DataProcessor implementation",
            "--repo",
            str(sample_repo_path),
            "--symbol",
            "DataProcessor",
            "--format",
            "json",
        ],
    )
    assert res_json.exit_code == 0
    assert '"decision_plan"' in res_json.stdout
    assert '"verification_report"' in res_json.stdout
