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
from devops_cli.telemetry.instruments import INSTRUMENTS
from devops_cli.telemetry.semconv import load_genai_snapshot


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
    assert "DEVOPS_CLI_GRAFANA_TOKEN" in var_names


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
    """Write and check every generated file, syncing a README under `tmp_path`.

    With the default README this rewrote the repository's own, which the workspace tripwire
    reports whenever that README already differs from HEAD.
    """
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Title\n\n## Complete Command Matrix\n\n| Command Group | Subcommand |\n|---|---|\n\n---\n",
        encoding="utf-8",
    )
    with patch.object(generator, "_find_readme", return_value=readme):
        written = generator.write_all_docs(tmp_path)
        # Check passes when docs are unchanged
        ok, errors = generator.check_docs(tmp_path)
    expected = ("CLI_REFERENCE.md", "ENV_VARS.md", "MCP_TOOLS.md", "commands/repos.md")
    assert (
        all((tmp_path / name).exists() for name in expected),
        readme in written,
        ok,
        errors,
    ) == (True, True, True, [])

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
    res = runner.invoke(docs_app, ["generate", "--no-sync-readme", "--output-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert (tmp_path / "CLI_REFERENCE.md").exists()

    # Check command passes
    check_res = runner.invoke(
        docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)]
    )
    assert check_res.exit_code == 0

    # Generate --check flag
    gen_check_res = runner.invoke(
        docs_app, ["generate", "--check", "--no-sync-readme", "--output-dir", str(tmp_path)]
    )
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
    runner.invoke(docs_app, ["generate", "--no-sync-readme", "--output-dir", str(tmp_path)])
    (tmp_path / "CLI_REFERENCE.md").write_text("Corrupt", encoding="utf-8")

    res = runner.invoke(docs_app, ["check", "--no-check-readme", "--output-dir", str(tmp_path)])
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
    assert "<!-- COMMAND_MATRIX_START -->\n\n|" in content
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
    assert "<!-- COMMAND_MATRIX_START -->\n\n|" in readme.read_text(encoding="utf-8")

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
    assert (
        _clean_text("Clone all repos from a GitHub org into repos/<org>/.")
        == "Clone all repos from a GitHub org into repos/\\<org\\>/."
    )
    assert _clean_text("`devops repos clone-org <org>`") == "`devops repos clone-org <org>`"
    assert (
        _clean_text("Details: <details><summary>Click</summary>text</details> with <placeholder>")
        == "Details: <details><summary>Click</summary>text</details> with \\<placeholder\\>"
    )

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


@pytest.mark.parametrize(
    "option",
    [
        click.Option(["--api-key"], default="secret_live_api_key_12345", help="API secret token."),
        click.Option(["--auth"], default="ghp_token_xyz", envvar="DEVOPS_AUTH_TOKEN"),
        click.Option(["--api-token"], default="abc"),
        click.Option(["--password"], default="x"),
        click.Option(["--api-key"], default="sk-123"),
        click.Option(["--apikey"], default="sk-123"),
        click.Option(["--secret-id"], default="abc"),
        click.Option(["--endpoint"], default="abc", envvar="DEVOPS_CLI_CLIENT_SECRET"),
        click.Option(["--pin"], default="1234", hide_input=True),
        click.Option(["--pin"], type=click.INT, default=1234, hide_input=True),
    ],
    ids=[
        "api-key",
        "envvar-token",
        "api-token",
        "password",
        "api-key-short",
        "apikey",
        "secret-id",
        "envvar-secret",
        "hide-input",
        "hide-input-int",
    ],
)
def test_doc_generator_masks_sensitive_param_defaults(
    generator: DocGenerator, option: click.Option
) -> None:
    """A text default is masked when the option's name or envvar names a credential, word by word,
    or when the option hides its input, Click's own marker for a secret, whatever its type."""
    assert generator.introspect_param(option).default == "<masked>"


@pytest.mark.parametrize(
    ("option", "shown"),
    [
        (click.Option(["--port"], type=click.INT, default=8080), "8080"),
        (click.Option(["--max-tokens"], type=click.INT, default=200), "200"),
        (click.Option(["--valkey-port"], type=click.INT, default=6379), "6379"),
        (click.Option(["--key-size", "-k"], type=click.INT, default=4096), "4096"),
        (click.Option(["--max-tokens-increase"], type=click.FLOAT, default=0.2), "0.2"),
        (click.Option(["--secret-name"], default="homelab-tls"), "homelab-tls"),
        (
            click.Option(
                ["--token-file"],
                type=click.Path(path_type=Path),
                default=Path("/etc/devops-cli/token"),
            ),
            "/etc/devops-cli/token",
        ),
        (click.Option(["--show-password/--hide-password"], default=True), "True"),
    ],
    ids=[
        "port",
        "max-tokens",
        "valkey-port",
        "key-size",
        "max-tokens-increase",
        "secret-name",
        "token-path",
        "password-switch",
    ],
)
def test_doc_generator_shows_defaults_that_are_not_credentials(
    generator: DocGenerator, option: click.Option, shown: str
) -> None:
    """A number, a boolean or a path cannot be a credential, and a credential word inside another
    word (MAX_TOKENS, VALKEY_PORT, KEY_SIZE) or before NAME names no credential (#956)."""
    assert generator.introspect_param(option).default == shown


def test_doc_generator_renders_an_on_off_pair_as_two_switches(generator: DocGenerator) -> None:
    """`--rootless/--root` is one boolean with an off switch, not two aliases: `--root` turns the
    UID/GID mapping off. The table shows the pair apart from comma-joined aliases (#956)."""
    pair = generator.introspect_param(
        click.Option(["--rootless/--root"], default=True, help="Run as the host user.")
    )
    aliased = generator.introspect_param(click.Option(["--key-size", "-k"], default=2048))
    lines: list[str] = []
    generator._render_command_markdown(
        CommandDoc(
            name="run",
            full_path="devops docker run",
            summary="",
            description="",
            usage="devops docker run [OPTIONS]",
            params=[pair, aliased],
        ),
        lines,
    )
    rendered = "\n".join(lines)

    assert (
        pair.flags,
        pair.off_flags,
        aliased.off_flags,
        "| `--rootless` / `--root` | `boolean` | `True` |" in rendered,
        "`--rootless`, `--root`" in rendered,
        "| `--key-size`, `-k` |" in rendered,
    ) == (["--rootless"], ["--root"], [], True, False, True)


def _option_cells(page: str, flag: str) -> list[tuple[str, str]]:
    """The flag and default cells of each option row for `flag` in a generated command page."""
    rows = (row.split(" | ") for row in page.splitlines() if row.startswith(f"| `{flag}`"))
    return [(cells[0].removeprefix("| "), cells[2]) for cells in rows]


def test_committed_command_pages_show_the_defaults_and_switches_they_hid() -> None:
    """The committed reference, which `devops docs check` keeps equal to the generator's output,
    shows the defaults it masked and the off switch it listed as an alias (#956)."""
    from devops_cli.config.constants import CONST_RUNS_INDEX_SECRET
    from devops_cli.config.defaults import (
        DEFAULT_GATEWAY_TUNE_MAX_TOKENS,
        DEFAULT_K8S_TLS_SECRET_NAME,
        DEFAULT_TLS_KEY_SIZE,
        DEFAULT_VALKEY_PORT,
    )

    pages = Path(__file__).resolve().parents[1] / "docs" / "commands"
    ai, k8s, tls, docker = (
        (pages / f"{name}.md").read_text(encoding="utf-8")
        for name in ("ai", "k8s", "tls", "docker")
    )

    assert (
        _option_cells(ai, "--max-tokens"),
        _option_cells(ai, "--max-tokens-increase"),
        _option_cells(ai, "--secret-name"),
        _option_cells(k8s, "--valkey-port"),
        _option_cells(k8s, "--secret-name"),
        _option_cells(tls, "--key-size"),
        _option_cells(tls, "--secret-name"),
        _option_cells(docker, "--rootless"),
    ) == (
        [("`--max-tokens`", "`1500`"), ("`--max-tokens`", f"`{DEFAULT_GATEWAY_TUNE_MAX_TOKENS}`")],
        [("`--max-tokens-increase`", "`0.2`")],
        [("`--secret-name`", f"`{CONST_RUNS_INDEX_SECRET}`")],
        [("`--valkey-port`", f"`{DEFAULT_VALKEY_PORT}`")],
        [("`--secret-name`", f"`{DEFAULT_K8S_TLS_SECRET_NAME}`")],
        [("`--key-size`, `-k`", f"`{DEFAULT_TLS_KEY_SIZE}`")] * 2,
        [("`--secret-name`", f"`{DEFAULT_K8S_TLS_SECRET_NAME}`")],
        [("`--rootless` / `--root`", "`True`")],
    )


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


def test_configuration_and_telemetry_docs_name_the_telemetry_variables_that_work(
    generator: DocGenerator,
) -> None:
    """The telemetry rows name the registered `DEVOPS_CLI_TELEMETRY_*` variables, and the tracing
    reference names no variable devops-cli stopped reading (#956)."""
    configuration = generator.generate_configuration_docs().splitlines()
    telemetry = generator.generate_telemetry_docs()
    rows = {
        row.split(" | ")[0]: row
        for row in configuration[configuration.index("## Telemetry & Metrics (`telemetry`)") :]
        if row.startswith("| `")
    }

    assert (
        "`DEVOPS_CLI_TELEMETRY_ENABLED`" in rows["| `enabled`"],
        "`DEVOPS_CLI_TELEMETRY_ENDPOINT`" in rows["| `endpoint`"],
        "`DEVOPS_CLI_TELEMETRY_ENDPOINT`" in telemetry,
        "`OTEL_EXPORTER_OTLP_ENDPOINT`" in telemetry,
        "DEVOPS_CLI_OTEL_ENDPOINT" in telemetry,
    ) == (True, True, True, True, False)


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
    assert "| Metric Name | Type | Unit | Description |" in content
    # The table lists the metrics devops-cli sends, and only those (#564).
    listed = {line.split("`")[1] for line in content.splitlines() if line.startswith("| `")}
    assert listed == {i.name for i in INSTRUMENTS}
    # The LLM span section names the GenAI conventions commit the snapshot pins (#588).
    pinned = load_genai_snapshot()["source"]["commit"]
    assert ("## LLM Span Attributes" in content, f"`{pinned}`" in content) == (True, True)


def test_doc_generator_knowledge_base_index(generator: DocGenerator) -> None:
    """Verify programmatic generation of KNOWLEDGE_BASE.md and KB article index."""
    content = generator.generate_knowledge_base_index()
    assert "# DevOps CLI Knowledge Base Catalog" in content
    assert "Division 1: DevOps CLI Information" in content
    assert "Division 2: Information Technology Domain-Specific" in content
    assert "tasks/" in content
    assert "tools/" in content
    assert "valkey.md" in content
    assert "Valkey" in content


def test_parse_mcp_input_schema_parameters_with_anyof_array() -> None:
    """Verify that optional array parameters using anyOf resolve to 'array' rather than falling back."""
    from devops_cli.docs.generator import _parse_mcp_input_schema_parameters

    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Vault path"},
            "keys": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "default": None,
                "description": "Optional secret keys",
            },
        },
        "required": ["path"],
    }
    params = _parse_mcp_input_schema_parameters(schema)
    assert len(params) == 2
    by_name = {p["name"]: p for p in params}
    assert by_name["path"]["type"] == "string"
    assert by_name["path"]["required"] is True
    assert by_name["keys"]["type"] == "array"
    assert by_name["keys"]["required"] is False
