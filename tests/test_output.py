"""Unit tests for the centralized output generation and stream management subsystem."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.output.console import (
    escape_text,
    get_console,
    get_stderr_console,
    print_dry_run_command,
    print_dry_run_result,
    print_error,
    print_info,
    print_markdown,
    print_message,
    print_muted,
    print_panel,
    print_section,
    print_step,
    print_success,
    print_syntax,
    print_syntax_panel,
    print_table,
    print_warning,
    progress_context,
    render_dry_run_result,
    track_progress,
    write_stderr,
    write_stdout,
    write_stream,
)
from devops_cli.output.file_writer import (
    write_bytes_file,
    write_file,
    write_json_file,
    write_serialized_file,
    write_text_file,
    write_yaml_file,
)
from devops_cli.output.formatter import (
    format_code_span,
    format_duration,
    format_json,
    format_key_value_pairs,
    format_latency,
    format_link,
    format_location,
    format_output,
    format_serialized,
    format_severity,
    format_status_badge,
    format_yaml,
    render_table,
)
from devops_cli.output.models import (
    KeyValuePayload,
    MarkdownPayload,
    PanelPayload,
    ProgressStep,
    RulePayload,
    StatusBadge,
    SyntaxPayload,
    TableColumn,
    TablePayload,
)


class SampleModel(BaseModel):
    name: str
    count: int


def test_console_instances() -> None:
    """Test standard console and stderr console instances."""
    c1 = get_console()
    assert hasattr(c1, "print")
    assert getattr(c1, "is_terminal", None) in (True, False, None)

    err1 = get_stderr_console()
    assert hasattr(err1, "print")
    assert getattr(err1, "is_terminal", None) in (True, False, None)


def test_write_stdout_and_stderr() -> None:
    """Test raw stream writing to stdout and stderr."""
    with patch("sys.stdout.write") as mock_stdout, patch("sys.stdout.flush"):
        write_stdout("hello world")
        mock_stdout.assert_called_once_with("hello world")

    with patch("sys.stderr.write") as mock_stderr, patch("sys.stderr.flush"):
        write_stderr("error diagnostic")
        mock_stderr.assert_called_once_with("error diagnostic")

    with patch("sys.stdout.write") as mock_stdout, patch("sys.stdout.flush"):
        write_stream("custom stream", stream="stdout")
        mock_stdout.assert_called_once_with("custom stream")

    with patch("sys.stderr.write") as mock_stderr, patch("sys.stderr.flush"):
        write_stream("custom err", stream="stderr")
        mock_stderr.assert_called_once_with("custom err")


def test_escape_text_and_streaming() -> None:
    """Test escape_text markup escaping and low-level streams."""
    assert escape_text("[bold red]alert[/bold red]") == r"\[bold red]alert\[/bold red]"


def test_styled_print_helpers() -> None:
    """Test styled printing functions (success, error, warning, info, muted, step)."""
    buf = io.StringIO()
    test_console = get_console(file=buf, color_system=None)

    print_success("Operation completed", console=test_console)
    print_error("Failed to connect", console=test_console)
    print_warning("High latency detected", console=test_console)
    print_info("Starting background worker", console=test_console)
    print_muted("Checking cache", console=test_console)
    print_step("Deploy stack", "k8s-prod", console=test_console)
    print_message("Raw text", level="raw", console=test_console)
    print_message("Custom prefix", level="info", prefix=">> ", console=test_console)

    output = buf.getvalue()
    assert "✓ Operation completed" in output
    assert "✗ Failed to connect" in output
    assert "! High latency detected" in output
    assert "ℹ Starting background worker" in output
    assert "Checking cache" in output
    assert "➔ Deploy stack (k8s-prod)" in output
    assert "Raw text" in output
    assert ">> Custom prefix" in output


def test_print_panel_and_table() -> None:
    """Test panel and table rendering helpers."""
    buf = io.StringIO()
    test_console = get_console(file=buf, color_system=None)

    print_panel("Important Notice", title="Alert", console=test_console)
    table = render_table("Status Overview", ["Component", "Status"], [["API", "Healthy"]])
    print_table(table, console=test_console)

    output = buf.getvalue()
    assert "Important Notice" in output
    assert "Alert" in output
    assert "API" in output
    assert "Healthy" in output


def test_file_writer_atomic_text_json_yaml_bytes(tmp_path: Path) -> None:
    """Test defensive and atomic file output generation for text, JSON, YAML, and binary data."""
    # 1. Text file with nested directory creation
    text_file = tmp_path / "deep" / "nested" / "doc.txt"
    written_text = write_text_file(text_file, "Hello, DevOps!", atomic=True, mode=0o644)
    assert written_text.is_file()
    assert written_text.read_text(encoding="utf-8") == "Hello, DevOps!"

    # 1b. Non-atomic text file with mode
    text_file_non_atomic = tmp_path / "deep" / "direct.txt"
    written_direct = write_text_file(text_file_non_atomic, "Direct write", atomic=False, mode=0o600)
    assert written_direct.is_file()
    assert written_direct.read_text(encoding="utf-8") == "Direct write"

    # 2. JSON file with Pydantic model serialization
    json_file = tmp_path / "data" / "model.json"
    model = SampleModel(name="test", count=42)
    written_json = write_json_file(json_file, model, atomic=True)
    assert written_json.is_file()
    assert '"name": "test"' in written_json.read_text(encoding="utf-8")
    assert '"count": 42' in written_json.read_text(encoding="utf-8")

    # 3. YAML file with list serialization
    yaml_file = tmp_path / "configs" / "stack.yaml"
    data = [{"service": "redis", "port": 6379}]
    written_yaml = write_yaml_file(yaml_file, data, atomic=True)
    assert written_yaml.is_file()
    assert "service: redis" in written_yaml.read_text(encoding="utf-8")

    # 4. Binary file
    bin_file = tmp_path / "bin" / "data.bin"
    written_bin = write_bytes_file(bin_file, b"\x00\x01\x02\x03", atomic=True, mode=0o600)
    assert written_bin.is_file()
    assert written_bin.read_bytes() == b"\x00\x01\x02\x03"

    # 4b. Non-atomic binary file
    bin_file_direct = tmp_path / "bin" / "direct.bin"
    written_bin_direct = write_bytes_file(
        bin_file_direct, b"\x04\x05\x06", atomic=False, mode=0o644
    )
    assert written_bin_direct.is_file()
    assert written_bin_direct.read_bytes() == b"\x04\x05\x06"

    # 5. General write_file auto dispatch
    auto_json = tmp_path / "auto.json"
    written_auto_json = write_file(auto_json, {"key": "val"})
    assert written_auto_json.is_file()
    assert '"key": "val"' in written_auto_json.read_text(encoding="utf-8")

    auto_yaml = tmp_path / "auto.yaml"
    written_auto_yaml = write_file(auto_yaml, {"key": "val"})
    assert written_auto_yaml.is_file()
    assert "key: val" in written_auto_yaml.read_text(encoding="utf-8")


def test_format_location_canonical_syntax() -> None:
    """Test format_location adhering to filename.ext:n-n canonical location standard."""
    assert format_location("src/main.py", 10, 20) == "src/main.py:10-20"
    assert format_location("src/main.py", 15, 15) == "src/main.py:15"
    assert format_location("src/main.py", 15) == "src/main.py:15"
    assert format_location("src/main.py") == "src/main.py"


def test_format_output_serializers() -> None:
    """Test format_output dispatcher and direct format_json / format_yaml helpers."""
    data = {"status": "ok", "code": 200}
    json_str = format_output(data, "json")
    assert isinstance(json_str, str)
    assert '"status": "ok"' in json_str
    assert format_json(data) == json_str

    yaml_str = format_output(data, "yaml")
    assert isinstance(yaml_str, str)
    assert "status: ok" in yaml_str
    assert format_yaml(data) == yaml_str

    ser_str = format_serialized({"key": "val"}, format_type="yaml")
    assert "key: val" in ser_str

    ser_json_file = write_serialized_file(
        "out_ser.json", [{"a": 1}], format_type="json", atomic=False
    )
    assert ser_json_file.exists()
    ser_json_file.unlink(missing_ok=True)


def test_rich_formatters() -> None:
    """Test format_status_badge, format_link, format_duration, format_latency, format_severity, format_code_span, format_key_value_pairs."""
    # 1. Status badge
    assert format_status_badge(True) == "[green]Active[/green]"
    assert format_status_badge(False) == "[red]Disabled[/red]"
    assert format_status_badge(True, label="Connected") == "[green]Connected[/green]"
    assert format_status_badge("warn", label="Warning State") == "[yellow]Warning State[/yellow]"

    # 2. Hyperlinks
    assert (
        format_link("http://localhost:16686")
        == "[link=http://localhost:16686]http://localhost:16686[/link]"
    )
    assert (
        format_link("http://localhost:16686", "Jaeger")
        == "[link=http://localhost:16686]Jaeger[/link]"
    )

    # 3. Durations & Latency
    assert format_duration(0.0005) == "500µs"
    assert format_duration(0.05) == "50.0ms"
    assert format_duration(2.5) == "2.50s"
    assert format_latency(12.34) == "12.3ms"

    # 4. Severity & Code span
    assert format_severity("CRITICAL") == "[bold red]CRITICAL[/bold red]"
    assert format_severity("high") == "[red]HIGH[/red]"
    assert format_severity("medium") == "[yellow]MEDIUM[/yellow]"
    assert format_severity("low") == "[cyan]LOW[/cyan]"
    assert format_severity("clean") == "[green]CLEAN[/green]"
    assert format_code_span("my-service") == "[cyan]my-service[/cyan]"

    # 5. Key-value pairs
    pairs = format_key_value_pairs({"key": "val", "count": 5})
    assert pairs == [["key", "val"], ["count", "5"]]


def test_output_pydantic_models() -> None:
    """Test TablePayload, KeyValuePayload, StatusBadge, PanelPayload, MarkdownPayload, SyntaxPayload, RulePayload, ProgressStep."""
    # 1. StatusBadge
    badge = StatusBadge(status=True, label="Online")
    assert badge.render() == "[green]Online[/green]"
    assert str(badge) == "[green]Online[/green]"

    badge_warn = StatusBadge(status="warn", label="Degraded")
    assert badge_warn.render() == "[yellow]Degraded[/yellow]"

    # 2. KeyValuePayload
    kv = KeyValuePayload(title="Summary", items={"Region": "us-east-1", "Pods": 4})
    tbl_payload = kv.to_table_payload()
    assert tbl_payload.title == "Summary"
    assert len(tbl_payload.rows) == 2

    # 3. TablePayload & TableColumn
    table_p = TablePayload(
        title="Services",
        columns=[
            TableColumn(header="Name", style="cyan"),
            TableColumn(header="Port", justify="right"),
        ],
        rows=[["api", 8080], ["redis", 6379]],
    )
    rich_table = table_p.render()
    assert rich_table.title == "Services"

    # 4. format_output with TablePayload and BaseModel list
    formatted_table = format_output(table_p, "table")
    assert formatted_table.title == "Services"

    models_list = [SampleModel(name="Worker 1", count=10), SampleModel(name="Worker 2", count=20)]
    auto_table = format_output(models_list, "table", title="Workers")
    assert auto_table.title == "Workers"

    # 5. print_table directly with TablePayload and KeyValuePayload
    buf = io.StringIO()
    test_console = get_console(file=buf, color_system=None)
    print_table(table_p, console=test_console)
    print_table(kv, console=test_console)
    output = buf.getvalue()
    assert "Services" in output
    assert "Worker" not in output
    assert "Summary" in output

    # 6. PanelPayload, MarkdownPayload, SyntaxPayload, RulePayload, ProgressStep
    buf2 = io.StringIO()
    test_console2 = get_console(file=buf2, color_system=None)

    panel_p = PanelPayload(content="Important text", title="Notice", subtitle="Footer")
    assert panel_p.render() is not None
    print_panel(panel_p, console=test_console2)

    md_p = MarkdownPayload(content="# Markdown Title\nSome body text.")
    assert md_p.render() is not None
    print_markdown(md_p, console=test_console2)

    syn_p = SyntaxPayload(code="x = 42", language="python")
    assert syn_p.render() is not None
    print_syntax(syn_p, console=test_console2)
    print_syntax_panel(syn_p, title="Python Code", console=test_console2)

    rule_p = RulePayload(title="Section Divider", style="green")
    assert rule_p.render() is not None
    print_section(rule_p, console=test_console2)

    step = ProgressStep(description="Syncing...", completed=50.0, total=100.0)
    assert step.completed == 50.0

    output2 = buf2.getvalue()
    assert "Important text" in output2
    assert "Markdown Title" in output2
    assert "Section Divider" in output2


def test_progress_tracking_and_context() -> None:
    """Test track_progress generator and progress_context manager."""
    buf = io.StringIO()
    c = get_console(file=buf, color_system=None)

    items = [1, 2, 3]
    collected = list(track_progress(items, description="Looping", console=c))
    assert collected == [1, 2, 3]

    with progress_context("Testing progress", total=50.0, console=c) as update_fn:
        update_fn("Step 1", 25.0)
        update_fn("Step 2", 50.0)


def test_dry_run_printers() -> None:
    """Test print_dry_run_command, print_dry_run_result, and render_dry_run_result."""
    buf = io.StringIO()
    c = get_console(file=buf, color_system=None)

    print_dry_run_command(["git", "checkout", "main"], cwd="/app", delegated=False, console=c)
    print_dry_run_command("docker build -t app .", delegated=True, console=c)

    res_model = CommandDryRunResult(command="k8s apply", action="deploy", target="prod")
    print_dry_run_result(res_model, console=c)
    print_dry_run_result('{"raw": "json"}', console=c)
    print_dry_run_result({"dict_key": "val"}, console=c)

    res_rendered = render_dry_run_result(
        "tf apply", action="infra", target="vpc", details={"tier": 1}, console=c
    )
    assert res_rendered.command == "tf apply"

    output = buf.getvalue()
    assert "git checkout main" in output
    assert "docker build -t app ." in output
    assert "k8s apply" in output
    assert "tf apply" in output


def test_output_formatter_extended_coverage() -> None:
    """Test extended formatter branches for Table formatting, KeyValuePayloads, and fallbacks."""
    kv = KeyValuePayload(title="Metrics", items={"QPS": 100})
    t1 = render_table(kv)
    assert t1.title == "Metrics"

    t2 = render_table("Table", [("Col1", 20), ("Col2", "center"), ("Col3",)], [["A", "B", "C"]])
    assert t2 is not None

    table_p = TablePayload(title="Payload", columns=["C1"], rows=[["V1"]])
    t3 = format_output(table_p, "table")
    assert t3.title == "Payload"

    t4 = format_output(kv, "table")
    assert t4.title == "Metrics"

    raw_fallback = format_output("fallback string", "unknown_fmt")
    assert "fallback string" in raw_fallback


def test_format_output_table_payload_and_pydantic_list() -> None:
    """Test format_output with to_table_payload and Pydantic model lists."""
    from pydantic import BaseModel

    from devops_cli.output.formatter import format_output, render_table
    from devops_cli.output.models import TableColumn, TablePayload

    class DummyModel(BaseModel):
        name: str
        count: int

    items = [DummyModel(name="test1", count=10), DummyModel(name="test2", count=20)]
    table_rendered = format_output(items, format_type="table", title="Dummy Items")
    assert table_rendered is not None

    class PayloadContainer:
        def to_table_payload(self) -> TablePayload:
            return TablePayload(
                title="Container Table",
                columns=[TableColumn(header="Col1")],
                rows=[["val1"]],
            )

    container = PayloadContainer()
    container_table = format_output(container, format_type="table")
    assert container_table is not None

    direct_table = render_table(container)
    assert direct_table is not None


def test_rich_imports_confined_to_output_submodule() -> None:
    """Verify that all direct imports of the 'rich' package are strictly confined to src/devops_cli/output/."""
    import ast

    src_dir = Path(__file__).resolve().parent.parent / "src" / "devops_cli"
    output_dir = src_dir / "output"

    violations: list[str] = []
    for py_file in src_dir.rglob("*.py"):
        if py_file.is_relative_to(output_dir):
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "rich" or alias.name.startswith("rich."):
                        violations.append(f"{py_file.relative_to(src_dir)}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module == "rich" or (node.module and node.module.startswith("rich.")):
                    violations.append(
                        f"{py_file.relative_to(src_dir)}: from {node.module} import ..."
                    )

    assert not violations, "Direct 'rich' imports found outside 'output' submodule:\n" + "\n".join(
        violations
    )
