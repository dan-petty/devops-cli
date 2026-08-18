"""Automated documentation generation engine for devops-cli."""

from __future__ import annotations

import asyncio
import re
from dataclasses import asdict, dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any

import click
import typer

from devops_cli.config.env import EnvVarSpec, get_all_env_var_specs

_RICH_TAG_RE = re.compile(
    r"\[/?(?:bold|dim|green|cyan|yellow|red|magenta|blue|italic|underline)[^\]]*\]"
)

_IGNORED_PARAM_NAMES = {"help", "install_completion", "show_completion"}


def _clean_text(text: str | None) -> str:
    """Remove rich markup tags and normalize whitespace."""
    if not text:
        return ""
    cleaned = _RICH_TAG_RE.sub("", text)
    return cleaned.strip()


def _format_type(param_type: Any) -> str:
    """Format a Click/Typer parameter type into a human-readable string."""
    if isinstance(param_type, click.Choice) or getattr(param_type, "choices", None):
        choices = "|".join(str(c) for c in getattr(param_type, "choices", []))
        return f"choice ({choices})"
    if isinstance(param_type, click.Path) or "Path" in type(param_type).__name__:
        return "path"
    if isinstance(param_type, click.types.BoolParamType) or "Bool" in type(param_type).__name__:
        return "boolean"
    if isinstance(param_type, click.types.IntParamType) or "Int" in type(param_type).__name__:
        return "integer"
    if isinstance(param_type, click.types.FloatParamType) or "Float" in type(param_type).__name__:
        return "float"
    if isinstance(param_type, click.types.StringParamType) or "String" in type(param_type).__name__:
        return "string"
    type_name = getattr(param_type, "name", str(param_type)).lower()
    return type_name or "string"


@dataclass
class ParamDoc:
    """Documentation model for a command parameter (argument or option)."""

    name: str
    kind: str  # "argument", "option", or "flag"
    flags: list[str]
    type_name: str
    description: str
    default: str | None
    required: bool
    envvar: str | None = None
    hidden: bool = False


@dataclass
class CommandDoc:
    """Documentation model for a CLI command or subcommand."""

    name: str
    full_path: str
    summary: str
    description: str
    usage: str
    params: list[ParamDoc] = field(default_factory=list)
    subcommands: list[CommandDoc] = field(default_factory=list)
    is_group: bool = False
    hidden: bool = False


@dataclass
class CommandGroupDoc:
    """Documentation model for a top-level command group."""

    name: str
    module_path: str
    summary: str
    description: str
    commands: list[CommandDoc] = field(default_factory=list)


@dataclass
class MCPToolDoc:
    """Documentation model for a FastMCP tool."""

    name: str
    description: str
    parameters: list[dict[str, Any]] = field(default_factory=list)


class DocGenerator:
    """Introspects devops-cli commands, environment variables, and MCP tools."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()

    def introspect_param(self, param: Any) -> ParamDoc:
        """Extract documentation metadata from a click/typer Parameter."""
        raw_opts = list(getattr(param, "opts", []) or [])
        sec_opts = list(getattr(param, "secondary_opts", []) or [])
        is_option = any(opt.startswith("-") for opt in raw_opts)

        flags: list[str] = []
        if is_option:
            flags = raw_opts + sec_opts
            kind = "flag" if getattr(param, "is_flag", False) else "option"
        else:
            flags = [f"<{param.name}>"]
            kind = "argument"

        raw_envvar = getattr(param, "envvar", None)
        envvar = raw_envvar if isinstance(raw_envvar, str) else None

        desc = _clean_text(getattr(param, "help", None) or "")
        type_str = _format_type(param.type)
        default_val = getattr(param, "default", None)
        default_str: str | None = None
        if default_val is not None and not (kind == "flag" and default_val is False):
            if isinstance(default_val, Path):
                try:
                    rel_to_root = default_val.resolve().relative_to(self.root_dir.resolve())
                    default_str = str(rel_to_root)
                except (ValueError, AttributeError):
                    try:
                        rel_to_home = default_val.resolve().relative_to(Path.home().resolve())
                        default_str = f"~/{rel_to_home}"
                    except (ValueError, AttributeError):
                        default_str = str(default_val)

            else:
                default_str = str(default_val)
                home_str = str(Path.home().resolve())
                root_str = str(self.root_dir.resolve())
                if root_str and root_str in default_str:
                    default_str = default_str.replace(root_str, ".").lstrip("./")
                elif home_str and home_str in default_str:
                    default_str = default_str.replace(home_str, "~")

        return ParamDoc(
            name=param.name or "",
            kind=kind,
            flags=flags,
            type_name=type_str,
            description=desc,
            default=default_str,
            required=bool(getattr(param, "required", False)),
            envvar=envvar,
            hidden=bool(getattr(param, "hidden", False)),
        )

    def introspect_command(
        self, cmd: Any, parent_path: str = "devops", override_name: str | None = None
    ) -> CommandDoc:
        """Extract documentation metadata from a click/typer Command or Group recursively."""

        cmd_name = override_name or cmd.name or ""
        full_path = f"{parent_path} {cmd_name}".strip() if cmd_name else parent_path
        help_text = _clean_text(cmd.help or "")
        short_help = _clean_text(cmd.short_help or "")
        summary = short_help or (help_text.split("\n\n")[0] if help_text else "")

        params: list[ParamDoc] = []
        for param in cmd.params:
            if param.name in _IGNORED_PARAM_NAMES or getattr(param, "hidden", False):
                continue
            params.append(self.introspect_param(param))

        cmd_subcommands_dict = getattr(cmd, "commands", None)
        is_group = bool(cmd_subcommands_dict)
        subcommands: list[CommandDoc] = []
        if is_group and isinstance(cmd_subcommands_dict, dict):
            for sub_name, sub_obj in cmd_subcommands_dict.items():
                if getattr(sub_obj, "hidden", False):
                    continue
                subcommands.append(
                    self.introspect_command(sub_obj, parent_path=full_path, override_name=sub_name)
                )

        # Build usage representation
        usage_parts = [full_path]
        args = [p for p in params if p.kind == "argument"]
        opts = [p for p in params if p.kind in ("option", "flag")]
        if opts:
            usage_parts.append("[OPTIONS]")
        for arg in args:
            usage_parts.append(arg.flags[0] if arg.flags else f"<{arg.name}>")
        if is_group and subcommands:
            usage_parts.append("COMMAND [ARGS]...")
        usage = " ".join(usage_parts)

        return CommandDoc(
            name=cmd_name,
            full_path=full_path,
            summary=summary,
            description=help_text,
            usage=usage,
            params=params,
            subcommands=subcommands,
            is_group=is_group,
            hidden=bool(getattr(cmd, "hidden", False)),
        )

    def introspect_all_groups(self) -> list[CommandGroupDoc]:
        """Introspect all command groups declared in main._COMMAND_SPECS."""
        from devops_cli.main import _COMMAND_SPECS

        groups: list[CommandGroupDoc] = []
        for name, (module_path, summary) in _COMMAND_SPECS.items():
            try:
                module = import_module(module_path)
                app_obj = getattr(module, "app", None)
                if app_obj is None:
                    continue
                click_cmd = typer.main.get_command(app_obj)
                doc = self.introspect_command(click_cmd, parent_path="devops", override_name=name)
                desc = doc.description or summary
                commands_list = doc.subcommands if doc.is_group else [doc]

                groups.append(
                    CommandGroupDoc(
                        name=name,
                        module_path=module_path,
                        summary=summary or doc.summary,
                        description=desc,
                        commands=commands_list,
                    )
                )
            except Exception as exc:
                # Keep resilient if an individual module cannot be imported
                groups.append(
                    CommandGroupDoc(
                        name=name,
                        module_path=module_path,
                        summary=summary,
                        description=f"Error introspecting module: {exc}",
                        commands=[],
                    )
                )
        return groups

    def introspect_env_vars(self) -> list[EnvVarSpec]:
        """Collect all environment variable specifications."""
        return get_all_env_var_specs()

    def introspect_mcp_tools(self) -> list[MCPToolDoc]:
        """Collect all registered FastMCP tools."""
        try:
            from devops_cli.ai.mcp.server import mcp

            async def _get_tools() -> list[MCPToolDoc]:
                tools = await mcp.list_tools()
                result: list[MCPToolDoc] = []
                for tool in tools:
                    params_list: list[dict[str, Any]] = []
                    input_schema = (
                        getattr(tool, "parameters", None)
                        or getattr(tool, "inputSchema", None)
                        or {}
                    )
                    if isinstance(input_schema, dict):
                        props = input_schema.get("properties", {})
                        reqs = set(input_schema.get("required", []))
                        for prop_name, prop_data in props.items():
                            params_list.append(
                                {
                                    "name": prop_name,
                                    "type": prop_data.get("type", "string"),
                                    "description": prop_data.get("description", ""),
                                    "default": prop_data.get("default", None),
                                    "required": prop_name in reqs,
                                }
                            )
                    result.append(
                        MCPToolDoc(
                            name=tool.name,
                            description=tool.description or "",
                            parameters=params_list,
                        )
                    )
                return result

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                future = asyncio.run_coroutine_threadsafe(_get_tools(), loop)
                return future.result()
            return asyncio.run(_get_tools())
        except Exception:
            return []

    def render_cli_reference_markdown(self, groups: list[CommandGroupDoc]) -> str:
        """Render complete CLI Reference documentation in Markdown format."""
        lines: list[str] = [
            "# DevOps CLI Reference",
            "",
            "Complete command-line reference for `devops-cli`, automatically generated from "
            "CLI command specifications.",
            "",
            "## Command Groups",
            "",
        ]

        for group in groups:
            anchor = group.name.replace("_", "-")
            lines.append(f"- [`devops {group.name}`](#devops-{anchor}) — {group.summary}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for group in groups:
            lines.append(f"## devops {group.name}")
            lines.append("")
            lines.append(f"{group.summary}")
            lines.append("")
            if group.description and group.description != group.summary:
                lines.append(f"{group.description}")
                lines.append("")

            if not group.commands:
                lines.append("*No subcommands available.*")
                lines.append("")
                continue

            for cmd in group.commands:
                self._render_command_markdown(cmd, lines, level=3)

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def _render_command_markdown(self, cmd: CommandDoc, lines: list[str], level: int = 3) -> None:
        """Render a single command or recursive subcommands into Markdown lines."""
        heading = "#" * level
        lines.append(f"{heading} `{cmd.full_path}`")
        lines.append("")
        if cmd.summary:
            lines.append(f"**{cmd.summary}**")
            lines.append("")
        if cmd.description and cmd.description != cmd.summary:
            lines.append(f"{cmd.description}")
            lines.append("")

        lines.append("```bash")
        lines.append(cmd.usage)
        lines.append("```")
        lines.append("")

        args = [p for p in cmd.params if p.kind == "argument"]
        opts = [p for p in cmd.params if p.kind in ("option", "flag")]

        if args:
            lines.append("**Arguments:**")
            lines.append("")
            lines.append("| Argument | Type | Required | Description |")
            lines.append("|---|---|---|---|")
            for arg in args:
                flag_str = f"`{arg.flags[0]}`" if arg.flags else f"`{arg.name}`"
                req_str = "Yes" if arg.required else "No"
                lines.append(
                    f"| {flag_str} | `{arg.type_name}` | {req_str} | {arg.description or '-'} |"
                )
            lines.append("")

        if opts:
            lines.append("**Options:**")
            lines.append("")
            lines.append("| Option / Flag | Type | Default | Description |")
            lines.append("|---|---|---|---|")
            for opt in opts:
                flags_str = ", ".join(f"`{f}`" for f in opt.flags)
                default_str = f"`{opt.default}`" if opt.default is not None else "-"
                env_str = f" *(Env: `{opt.envvar}`)*" if opt.envvar else ""
                desc = f"{opt.description or '-'}{env_str}"
                lines.append(f"| {flags_str} | `{opt.type_name}` | {default_str} | {desc} |")
            lines.append("")

        if cmd.subcommands:
            for sub in cmd.subcommands:
                self._render_command_markdown(sub, lines, level=level + 1)

    def render_command_group_markdown(self, group: CommandGroupDoc) -> str:
        """Render documentation for a single command group."""
        lines: list[str] = [
            f"# `devops {group.name}`",
            "",
            f"{group.summary}",
            "",
            "## Commands",
            "",
        ]
        for cmd in group.commands:
            self._render_command_markdown(cmd, lines, level=2)
            lines.append("---")
            lines.append("")
        return "\n".join(lines)

    def render_env_vars_markdown(self, env_specs: list[EnvVarSpec]) -> str:
        """Render Environment Variables documentation in Markdown format."""
        lines: list[str] = [
            "# Configuration Environment Variables",
            "",
            "All configuration options for `devops-cli` can be overridden via environment "
            "variables or loaded from OS Keyring for sensitive secrets.",
            "",
            "| Environment Variable | Config Key | Secret | Description |",
            "|---|---|---|---|",
        ]

        for spec in sorted(env_specs, key=lambda s: s.env_var):
            secret_str = "🔒 Yes" if spec.is_secret else "No"
            opt_key = f"`{spec.option_key}`" if spec.option_key else "*None*"
            desc = spec.description.replace("|", "\\|")
            lines.append(f"| `{spec.env_var}` | {opt_key} | {secret_str} | {desc} |")

        lines.append("")
        lines.append("## Usage Notes")
        lines.append("")
        lines.append(
            "- Secret tokens (`*.token`, `*.api_key`) should be set via "
            "`devops config set <key> <val>` to store them securely in the OS Keyring."
        )
        lines.append(
            "- Environment variable overrides take precedence over values in `config.yaml`."
        )
        lines.append("- Run `devops config output` to inspect all active environment variables.")
        lines.append("")
        return "\n".join(lines)

    def render_mcp_tools_markdown(self, tools: list[MCPToolDoc]) -> str:
        """Render FastMCP tools catalog in Markdown format."""
        lines: list[str] = [
            "# FastMCP Tool Catalog",
            "",
            "The `devops-cli` FastMCP server exposes DevOps automation and AI review capabilities "
            "to Model Context Protocol (MCP) clients and AI agents.",
            "",
            "## Available Tools",
            "",
            "| Tool Name | Description |",
            "|---|---|",
        ]

        for tool in sorted(tools, key=lambda t: t.name):
            anchor = tool.name.replace("_", "-")
            lines.append(f"| [`{tool.name}`](#{anchor}) | {tool.description} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        for tool in sorted(tools, key=lambda t: t.name):
            lines.append(f"### `{tool.name}`")
            lines.append("")
            lines.append(f"{tool.description}")
            lines.append("")
            if tool.parameters:
                lines.append("**Parameters:**")
                lines.append("")
                lines.append("| Parameter | Type | Required | Default | Description |")
                lines.append("|---|---|---|---|---|")
                for p in tool.parameters:
                    req_str = "Yes" if p.get("required") else "No"
                    def_val = p.get("default")
                    def_str = f"`{def_val}`" if def_val is not None else "-"
                    p_desc = p.get("description", "-") or "-"
                    lines.append(
                        f"| `{p['name']}` | `{p['type']}` | {req_str} | {def_str} | {p_desc} |"
                    )
                lines.append("")
            else:
                lines.append("*No parameters required.*")
                lines.append("")

        return "\n".join(lines)

    def render_readme_matrix(self, groups: list[CommandGroupDoc]) -> str:
        """Render the Complete Command Matrix markdown table for README.md."""
        lines: list[str] = [
            "| Command Group | Subcommand / Usage | Purpose & Features |",
            "|---|---|---|",
        ]

        for group in groups:
            first = True
            group_name = f"**{group.name}**"
            if not group.commands:
                lines.append(f"| {group_name} | `devops {group.name}` | {group.summary} |")
                continue

            for cmd in group.commands:
                prefix = group_name if first else ""
                first = False
                desc = cmd.summary or group.summary
                usage = cmd.usage
                lines.append(f"| {prefix} | `{usage}` | {desc} |")

        return "\n".join(lines)

    def _find_readme(self, readme_path: Path | None = None) -> Path:
        """Locate project README.md."""
        if readme_path:
            return readme_path.resolve()
        return (self.root_dir / "README.md").resolve()

    def sync_readme(self, readme_path: Path | None = None) -> bool:
        """Synchronize the Complete Command Matrix table in README.md."""
        target = self._find_readme(readme_path)
        if not target.exists():
            return False

        content = target.read_text(encoding="utf-8")
        groups = self.introspect_all_groups()
        matrix_table = self.render_readme_matrix(groups)

        start_marker = "<!-- COMMAND_MATRIX_START -->"
        end_marker = "<!-- COMMAND_MATRIX_END -->"

        if start_marker in content and end_marker in content:
            pattern = re.compile(
                rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
                re.DOTALL,
            )
            new_content = pattern.sub(
                f"{start_marker}\n{matrix_table}\n{end_marker}",
                content,
            )
        else:
            # Match existing Complete Command Matrix section
            pattern = re.compile(
                r"(## Complete Command Matrix\s*\n\n)"
                r"(?:<!-- COMMAND_MATRIX_START -->\s*)?\|.*?(?=\n\n---|\n\n## |\Z)",
                re.DOTALL,
            )
            if pattern.search(content):
                new_content = pattern.sub(
                    rf"\g<1>{start_marker}\n{matrix_table}\n{end_marker}",
                    content,
                )
            else:
                return False

        target.write_text(new_content, encoding="utf-8")
        return True

    def check_readme(self, readme_path: Path | None = None) -> tuple[bool, str | None]:
        """Check if Complete Command Matrix table in README.md is in sync."""
        target = self._find_readme(readme_path)
        if not target.exists():
            return False, f"Missing README file: {target}"

        content = target.read_text(encoding="utf-8")
        groups = self.introspect_all_groups()
        matrix_table = self.render_readme_matrix(groups)

        start_marker = "<!-- COMMAND_MATRIX_START -->"
        end_marker = "<!-- COMMAND_MATRIX_END -->"

        if start_marker in content and end_marker in content:
            start_idx = content.find(start_marker) + len(start_marker)
            end_idx = content.find(end_marker)
            current_matrix = content[start_idx:end_idx].strip()
            if current_matrix != matrix_table.strip():
                return (
                    False,
                    f"Out-of-date Command Matrix in {target}: "
                    "README.md table differs from CLI state.",
                )
            return True, None

        # If markers are missing, check if table matches
        pattern = re.compile(
            r"## Complete Command Matrix\s*\n\n"
            r"(?:<!-- COMMAND_MATRIX_START -->\s*)?(\|.*?)(?=\n\n---|\n\n## |\Z)",
            re.DOTALL,
        )

        match = pattern.search(content)
        if match:
            current_table = match.group(1).strip()
            if current_table != matrix_table.strip():
                return (
                    False,
                    f"Out-of-date Command Matrix in {target}: "
                    "table differs from live CLI commands.",
                )
            return True, None

        return False, f"Could not find Command Matrix table or markers in {target}"

    def generate_all_docs(self, output_dir: Path) -> dict[str, str]:
        """Generate all documentation files and return a dict of {rel_path: content}."""
        groups = self.introspect_all_groups()
        env_specs = self.introspect_env_vars()
        mcp_tools = self.introspect_mcp_tools()

        results: dict[str, str] = {}

        # 1. Main CLI Reference
        results["CLI_REFERENCE.md"] = self.render_cli_reference_markdown(groups)

        # 2. Environment Variables
        results["ENV_VARS.md"] = self.render_env_vars_markdown(env_specs)

        # 3. FastMCP Tools
        if mcp_tools:
            results["MCP_TOOLS.md"] = self.render_mcp_tools_markdown(mcp_tools)

        # 4. Individual command group markdown files under commands/
        for group in groups:
            group_doc = self.render_command_group_markdown(group)
            results[f"commands/{group.name}.md"] = group_doc

        return results

    def write_all_docs(self, output_dir: Path, sync_readme_table: bool = True) -> list[Path]:
        """Generate and write all documentation files to disk."""
        docs = self.generate_all_docs(output_dir)
        written: list[Path] = []
        for rel_path, content in docs.items():
            dest = output_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            written.append(dest)

        if sync_readme_table:
            readme_path = self._find_readme()
            if self.sync_readme(readme_path):
                written.append(readme_path)

        return written

    def check_docs(
        self, output_dir: Path, check_readme_table: bool = True
    ) -> tuple[bool, list[str]]:
        """Verify if on-disk docs match current generated docs."""
        docs = self.generate_all_docs(output_dir)
        errors: list[str] = []

        for rel_path, expected_content in docs.items():
            target_path = output_dir / rel_path
            if not target_path.exists():
                errors.append(f"Missing documentation file: {target_path}")
                continue
            actual_content = target_path.read_text(encoding="utf-8")
            if actual_content != expected_content:
                errors.append(
                    f"Out-of-date documentation file: {target_path} differs from generated content."
                )

        if check_readme_table:
            readme_ok, readme_err = self.check_readme()
            if not readme_ok and readme_err:
                errors.append(readme_err)

        return len(errors) == 0, errors

    def to_json_dict(self) -> dict[str, Any]:
        """Export all introspected metadata as structured JSON dictionary."""
        groups = self.introspect_all_groups()
        env_specs = self.introspect_env_vars()
        mcp_tools = self.introspect_mcp_tools()

        return {
            "version": "1.0",
            "groups": [asdict(g) for g in groups],
            "env_vars": [e.model_dump() for e in env_specs],
            "mcp_tools": [asdict(t) for t in mcp_tools],
        }
