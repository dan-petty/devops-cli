"""Tests for automated documentation generation and validation engine."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import click
import pytest
from typer.testing import CliRunner

from devops_cli.commands.docs import app as docs_app
from devops_cli.docs.generator import (
    CommandDoc,
    CommandGroupDoc,
    DocGenerator,
    MCPToolDoc,
    ParamDoc,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def generator() -> DocGenerator:
    return DocGenerator()


def test_doc_generator_introspect_param(generator: DocGenerator) -> None:
    opt = click.Option(
        ["--test-opt", "-t"],
        type=click.STRING,
        default="hello",
        help="A test option.",
        envvar="DEVOPS_TEST_OPT",
    )
    param_doc = generator.introspect_param(opt)
    assert param_doc.name == "test_opt"
    assert param_doc.kind == "option"
    assert "--test-opt" in param_doc.flags
    assert "-t" in param_doc.flags
    assert param_doc.type_name == "string"
    assert param_doc.default == "hello"
    assert param_doc.description == "A test option."
    assert param_doc.envvar == "DEVOPS_TEST_OPT"

    arg = click.Argument(["target"], type=click.Path(), required=True)
    arg_doc = generator.introspect_param(arg)
    assert arg_doc.name == "target"
    assert arg_doc.kind == "argument"
    assert arg_doc.required is True
    assert arg_doc.type_name == "path"


def test_doc_generator_introspect_command(generator: DocGenerator) -> None:
    @click.command("sample", help="Sample command description.")
    @click.option("--count", type=click.INT, default=1, help="Count of items.")
    @click.argument("name", type=click.STRING)
    def sample_cmd(name: str, count: int) -> None:
        pass

    doc = generator.introspect_command(sample_cmd, parent_path="devops test")
    assert doc.name == "sample"
    assert doc.full_path == "devops test sample"
    assert "Sample command description." in doc.description
    assert len(doc.params) == 2
    assert doc.is_group is False
    assert "devops test sample [OPTIONS] <name>" in doc.usage


def test_doc_generator_introspect_all_groups(generator: DocGenerator) -> None:
    groups = generator.introspect_all_groups()
    assert len(groups) >= 15
    group_names = [g.name for g in groups]
    assert "repos" in group_names
    assert "ssh" in group_names
    assert "k8s" in group_names
    assert "config" in group_names
    assert "docs" in group_names
    assert "ci" in group_names


def test_doc_generator_introspect_env_vars(generator: DocGenerator) -> None:
    specs = generator.introspect_env_vars()
    assert len(specs) >= 20
    var_names = [s.env_var for s in specs]
    assert "DEVOPS_CLI_CONFIG" in var_names
    assert "DEVOPS_CLI_GITHUB_TOKEN" in var_names


def test_doc_generator_introspect_mcp_tools(generator: DocGenerator) -> None:
    tools = generator.introspect_mcp_tools()
    assert len(tools) >= 10
    tool_names = [t.name for t in tools]
    assert "repos_list" in tool_names
    assert "review_path" in tool_names


def test_render_markdown_and_json(generator: DocGenerator) -> None:
    groups = [
        CommandGroupDoc(
            name="dummy",
            module_path="dummy.path",
            summary="Dummy summary",
            description="Dummy long description",
            commands=[
                CommandDoc(
                    name="run",
                    full_path="devops dummy run",
                    summary="Run dummy",
                    description="Run dummy detail",
                    usage="devops dummy run [OPTIONS]",
                    params=[
                        ParamDoc(
                            name="flag",
                            kind="flag",
                            flags=["--flag"],
                            type_name="boolean",
                            description="A flag",
                            default=None,
                            required=False,
                        )
                    ],
                )
            ],
        )
    ]

    cli_md = generator.render_cli_reference_markdown(groups)
    assert "# DevOps CLI Reference" in cli_md
    assert "## devops dummy" in cli_md
    assert "`devops dummy run`" in cli_md

    group_md = generator.render_command_group_markdown(groups[0])
    assert "# `devops dummy`" in group_md

    readme_table = generator.render_readme_matrix(groups)
    assert "| Command Group | Subcommand / Usage | Purpose & Features |" in readme_table
    assert "**dummy**" in readme_table

    tools = [
        MCPToolDoc(
            name="test_tool",
            description="A test tool",
            parameters=[{"name": "arg", "type": "string", "required": True, "default": None}],
        )
    ]
    mcp_md = generator.render_mcp_tools_markdown(tools)
    assert "# FastMCP Tool Catalog" in mcp_md
    assert "### `test_tool`" in mcp_md

    json_dict = generator.to_json_dict()
    assert "groups" in json_dict
    assert "env_vars" in json_dict
    assert "mcp_tools" in json_dict


def test_write_and_check_docs(generator: DocGenerator, tmp_path: Path) -> None:
    written = generator.write_all_docs(tmp_path)
    assert len(written) > 0
    assert (tmp_path / "CLI_REFERENCE.md").exists()
    assert (tmp_path / "ENV_VARS.md").exists()
    assert (tmp_path / "MCP_TOOLS.md").exists()
    assert (tmp_path / "commands" / "repos.md").exists()

    # Check passes when docs are unchanged
    ok, errors = generator.check_docs(tmp_path)
    assert ok is True
    assert len(errors) == 0

    # Stale file detection
    (tmp_path / "CLI_REFERENCE.md").write_text("Modified content", encoding="utf-8")
    ok_stale, errors_stale = generator.check_docs(tmp_path)
    assert ok_stale is False
    assert any("differs from generated content" in e for e in errors_stale)

    # Missing file detection
    (tmp_path / "ENV_VARS.md").unlink()
    ok_missing, errors_missing = generator.check_docs(tmp_path)
    assert ok_missing is False
    assert any("Missing documentation file" in e for e in errors_missing)


def test_docs_cli_generate_and_check(runner: CliRunner, tmp_path: Path) -> None:
    res = runner.invoke(docs_app, ["generate", "--output-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "CLI_REFERENCE.md").exists()

    # Check command passes
    check_res = runner.invoke(docs_app, ["check", "--output-dir", str(tmp_path)])
    assert check_res.exit_code == 0

    # Generate --check flag
    gen_check_res = runner.invoke(docs_app, ["generate", "--check", "--output-dir", str(tmp_path)])
    assert gen_check_res.exit_code == 0

    # JSON export
    json_res = runner.invoke(
        docs_app, ["generate", "--format", "json", "--output-dir", str(tmp_path)]
    )
    assert json_res.exit_code == 0
    schema_file = tmp_path / "cli_schema.json"
    assert schema_file.exists()
    data = json.loads(schema_file.read_text(encoding="utf-8"))
    assert "groups" in data

    # Invalid format error
    inv_res = runner.invoke(
        docs_app, ["generate", "--format", "xml", "--output-dir", str(tmp_path)]
    )
    assert inv_res.exit_code == 1


def test_docs_cli_check_fails_on_stale(runner: CliRunner, tmp_path: Path) -> None:
    runner.invoke(docs_app, ["generate", "--output-dir", str(tmp_path)])
    (tmp_path / "CLI_REFERENCE.md").write_text("Corrupt", encoding="utf-8")

    res = runner.invoke(docs_app, ["check", "--output-dir", str(tmp_path)])
    assert res.exit_code == 1


def test_sync_and_check_readme(generator: DocGenerator, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Sample\n\n## Complete Command Matrix\n\n| Old | Table |\n|---|---|\n\n---\n",
        encoding="utf-8",
    )

    # Initial sync
    ok = generator.sync_readme(readme)
    assert ok is True
    content = readme.read_text(encoding="utf-8")
    assert "<!-- COMMAND_MATRIX_START -->" in content
    assert "<!-- COMMAND_MATRIX_END -->" in content
    assert "| **repos** |" in content

    # Check passes when synchronized
    check_ok, err = generator.check_readme(readme)
    assert check_ok is True
    assert err is None

    # Stale table detection
    stale_content = content.replace("| **repos** |", "| **corrupt** |")
    readme.write_text(stale_content, encoding="utf-8")
    check_ok_stale, err_stale = generator.check_readme(readme)
    assert check_ok_stale is False
    assert err_stale is not None


def test_docs_cli_sync_readme(runner: CliRunner, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Header\n\n<!-- COMMAND_MATRIX_START -->\nold\n<!-- COMMAND_MATRIX_END -->\n",
        encoding="utf-8",
    )

    # Sync CLI command
    res = runner.invoke(docs_app, ["sync-readme", "--readme-path", str(readme)])
    assert res.exit_code == 0
    assert "<!-- COMMAND_MATRIX_START -->" in readme.read_text(encoding="utf-8")

    # Check flag passes
    check_res = runner.invoke(docs_app, ["sync-readme", "--check", "--readme-path", str(readme)])
    assert check_res.exit_code == 0

    # Corrupt table fails check
    readme.write_text(
        "# Header\n\n<!-- COMMAND_MATRIX_START -->\nstale\n<!-- COMMAND_MATRIX_END -->\n"
    )
    fail_res = runner.invoke(docs_app, ["sync-readme", "--check", "--readme-path", str(readme)])
    assert fail_res.exit_code == 1


def test_ci_docs_command(runner: CliRunner) -> None:
    from devops_cli.commands.ci import app as ci_app

    with patch("devops_cli.commands.ci._run", return_value=True) as mock_run:
        res = runner.invoke(ci_app, ["docs"])
        assert res.exit_code == 0
        mock_run.assert_called_once()


def test_doc_generator_write_all_and_check(generator: DocGenerator, tmp_path: Path) -> None:
    """Verify write_all_docs and check_docs."""
    out_dir = tmp_path / "docs"
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n## Complete Command Matrix\n\n| Command Group | Subcommand |\n|---|---|\n\n---\n",
        encoding="utf-8",
    )

    written = generator.write_all_docs(out_dir, sync_readme_table=False)
    assert len(written) > 0

    ok = generator.sync_readme(readme)
    assert ok is True

    # Check docs with readme sync enabled
    with patch.object(generator, "_find_readme", return_value=readme):
        written_with_sync = generator.write_all_docs(out_dir, sync_readme_table=True)
        assert len(written_with_sync) > 0

        ok_check, check_errs = generator.check_docs(out_dir, check_readme_table=True)
        assert ok_check is True

    # Readme with no markers or table returns error in check_readme
    empty_readme = tmp_path / "EMPTY.md"
    empty_readme.write_text("# No matrix here\n", encoding="utf-8")
    no_matrix_ok, no_matrix_err = generator.check_readme(empty_readme)
    assert no_matrix_ok is False
    assert "Could not find" in str(no_matrix_err)


def test_docs_cli_dry_run_and_format_helpers(runner: CliRunner, tmp_path: Path) -> None:
    """Verify dry-run execution for docs commands and helper formatters."""
    from devops_cli.docs.generator import _clean_text, _format_type
    from devops_cli.dry_run import set_dry_run

    # Format type helper
    assert _format_type(click.FLOAT) == "float"
    assert _format_type(click.BOOL) == "boolean"
    assert _format_type(click.INT) == "integer"
    assert _format_type(click.Choice(["a", "b"])) == "choice (a|b)"
    assert _clean_text("[bold red]Warning[/bold red]") == "Warning"

    # Dry-run execution
    set_dry_run(True)
    try:
        res_dry = runner.invoke(docs_app, ["generate", "--output-dir", str(tmp_path)])
        assert res_dry.exit_code == 0
        assert not (tmp_path / "CLI_REFERENCE.md").exists()

        res_json_dry = runner.invoke(
            docs_app,
            ["generate", "--format", "json", "--output-dir", str(tmp_path)],
        )
        assert res_json_dry.exit_code == 0

        readme = tmp_path / "README.md"
        readme.write_text("# Readme\n", encoding="utf-8")
        res_sync_dry = runner.invoke(docs_app, ["sync-readme", "--readme-path", str(readme)])
        assert res_sync_dry.exit_code == 0
    finally:
        set_dry_run(False)


def test_doc_generator_masks_sensitive_param_defaults(generator: DocGenerator) -> None:
    """Verify that parameters with names or envvars indicating secrets mask default values."""
    # Sensitive option name
    secret_opt = click.Option(
        ["--api-key"],
        type=click.STRING,
        default="secret_live_api_key_12345",
        help="API secret token.",
    )
    doc_secret = generator.introspect_param(secret_opt)
    assert doc_secret.default == "<masked>"

    # Sensitive envvar
    token_opt = click.Option(
        ["--auth"],
        type=click.STRING,
        default="ghp_token_xyz",
        envvar="DEVOPS_AUTH_TOKEN",
        help="Auth credential.",
    )
    doc_token = generator.introspect_param(token_opt)
    assert doc_token.default == "<masked>"

    # Non-sensitive option preserves normal default
    normal_opt = click.Option(
        ["--port"],
        type=click.INT,
        default=8080,
        help="Service port.",
    )
    doc_normal = generator.introspect_param(normal_opt)
    assert doc_normal.default == "8080"


def test_doc_generator_introspect_single_group_untrusted_prefix_rejected(
    generator: DocGenerator,
) -> None:
    """_introspect_single_group must reject module paths outside devops_cli.commands."""
    untrusted_res = generator._introspect_single_group(
        name="malicious",
        module_path="os.system",
        summary="Untrusted module",
    )
    assert untrusted_res is None


def test_doc_generator_configuration_docs(generator: DocGenerator) -> None:
    """Verify programmatic generation of CONFIGURATION.md from Pydantic settings."""
    content = generator.generate_configuration_docs()
    assert "# DevOps CLI Configuration Reference" in content
    assert "SSH Configuration" in content or "ssh" in content.lower()
    assert "Telemetry Configuration" in content or "telemetry" in content.lower()
    assert "AI Configuration" in content or "ai" in content.lower()
    assert "DEVOPS_CLI_" in content
    assert "| Option | Type | Default | Environment Variable | Description |" in content


def test_doc_generator_error_catalog_docs(generator: DocGenerator) -> None:
    """Verify programmatic generation of ERRORS.md from DevOpsCLIError hierarchy."""
    content = generator.generate_error_catalog_docs()
    assert "# DevOps CLI Exit Code & Error Catalog" in content
    assert "VALIDATION_ERROR" in content or "CONFIGURATION_ERROR" in content
    assert "| Error Code | Exit Code | Domain | Description |" in content
    assert "SSRF_BLOCKED" in content or "CONFIGURATION_ERROR" in content


def test_doc_generator_telemetry_docs(generator: DocGenerator) -> None:
    """Verify programmatic generation of TELEMETRY.md from OpenTelemetry & metrics."""
    content = generator.generate_telemetry_docs()
    assert "# DevOps CLI Telemetry & Distributed Tracing Reference" in content
    assert "OpenTelemetry" in content
    assert "devops_cli_" in content
    assert "| Metric Name | Type | Description |" in content


def test_doc_generator_knowledge_base_index(generator: DocGenerator) -> None:
    """Verify programmatic generation of KNOWLEDGE_BASE.md and KB article index."""
    content = generator.generate_knowledge_base_index()
    assert "# DevOps CLI Knowledge Base Catalog" in content
    assert "Division 1: DevOps CLI Information" in content
    assert "Division 2: Information Technology Domain-Specific" in content
    assert "tasks/" in content
    assert "tools/" in content
