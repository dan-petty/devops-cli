"""Unit tests for the centralized output generation and stream management subsystem."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel
from rich.console import Console

from devops_cli.output.console import (
    get_console,
    get_stderr_console,
    print_error,
    print_info,
    print_muted,
    print_panel,
    print_step,
    print_success,
    print_table,
    print_warning,
    write_stderr,
    write_stdout,
)
from devops_cli.output.file_writer import (
    write_bytes_file,
    write_json_file,
    write_serialized_file,
    write_text_file,
    write_yaml_file,
)
from devops_cli.output.formatter import (
    format_json,
    format_location,
    format_output,
    format_serialized,
    format_yaml,
    render_table,
)


class SampleModel(BaseModel):
    name: str
    count: int


def test_console_instances() -> None:
    """Test standard console and stderr console instances."""
    c1 = get_console()
    assert isinstance(c1, Console)
    assert c1.is_terminal in (True, False)

    err1 = get_stderr_console()
    assert isinstance(err1, Console)
    assert err1.is_terminal in (True, False)


def test_write_stdout_and_stderr() -> None:
    """Test raw stream writing to stdout and stderr."""
    with patch("sys.stdout.write") as mock_stdout, patch("sys.stdout.flush"):
        write_stdout("hello world")
        mock_stdout.assert_called_once_with("hello world")

    with patch("sys.stderr.write") as mock_stderr, patch("sys.stderr.flush"):
        write_stderr("error diagnostic")
        mock_stderr.assert_called_once_with("error diagnostic")


def test_styled_print_helpers() -> None:
    """Test styled printing functions (success, error, warning, info, muted, step)."""
    buf = io.StringIO()
    test_console = Console(file=buf, color_system=None)

    print_success("Operation completed", console=test_console)
    print_error("Failed to connect", console=test_console)
    print_warning("High latency detected", console=test_console)
    print_info("Starting background worker", console=test_console)
    print_muted("Checking cache", console=test_console)
    print_step("Deploy stack", "k8s-prod", console=test_console)

    output = buf.getvalue()
    assert "✓ Operation completed" in output
    assert "✗ Failed to connect" in output
    assert "! High latency detected" in output
    assert "ℹ Starting background worker" in output
    assert "Checking cache" in output
    assert "➔ Deploy stack (k8s-prod)" in output


def test_print_panel_and_table() -> None:
    """Test panel and table rendering helpers."""
    buf = io.StringIO()
    test_console = Console(file=buf, color_system=None)

    print_panel("Important Notice", title="Alert", console=test_console)
    table = render_table("Status Overview", ["Component", "Status"], [["API", "Healthy"]])
    print_table(table, console=test_console)

    output = buf.getvalue()
    assert "Important Notice" in output
    assert "Alert" in output
    assert "Status Overview" in output
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
