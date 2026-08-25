"""DevOps CLI centralized output generation, stream management, and formatting subsystem."""

from __future__ import annotations

from devops_cli.output.console import (
    get_console,
    get_stderr_console,
    print_dry_run_command,
    print_dry_run_result,
    print_error,
    print_info,
    print_muted,
    print_panel,
    print_step,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
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

__all__ = [
    "format_json",
    "format_location",
    "format_output",
    "format_serialized",
    "format_yaml",
    "get_console",
    "get_stderr_console",
    "print_dry_run_command",
    "print_dry_run_result",
    "print_error",
    "print_info",
    "print_muted",
    "print_panel",
    "print_step",
    "print_success",
    "print_table",
    "print_warning",
    "render_dry_run_result",
    "render_table",
    "write_bytes_file",
    "write_json_file",
    "write_serialized_file",
    "write_stderr",
    "write_stdout",
    "write_text_file",
    "write_yaml_file",
]
