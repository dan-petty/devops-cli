"""Automated documentation generation engine for devops-cli."""

from __future__ import annotations

import asyncio
import re
from importlib import import_module
from pathlib import Path
from typing import Any

import click
import typer
from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_MARKDOWN_HEADING_LEVEL
from devops_cli.config.env import EnvVarSpec, get_all_env_var_specs
from devops_cli.output import write_text_file

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


class ParamDoc(BaseModel):
    """Documentation model for a command parameter (argument or option)."""

    name: str
    kind: str  # "argument", "option", or "flag"
    flags: list[str] = Field(default_factory=list)
    type_name: str = "string"
    description: str = ""
    default: str | None = None
    required: bool = False
    envvar: str | None = None
    hidden: bool = False


class CommandDoc(BaseModel):
    """Documentation model for a CLI command or subcommand."""

    name: str
    full_path: str
    summary: str
    description: str
    usage: str
    params: list[ParamDoc] = Field(default_factory=list)
    subcommands: list[CommandDoc] = Field(default_factory=list)
    is_group: bool = False
    hidden: bool = False


class CommandGroupDoc(BaseModel):
    """Documentation model for a top-level command group."""

    name: str
    module_path: str
    summary: str
    description: str
    commands: list[CommandDoc] = Field(default_factory=list)


class MCPToolDoc(BaseModel):
    """Documentation model for a FastMCP tool."""

    name: str
    description: str
    parameters: list[dict[str, Any]] = Field(default_factory=list)


def _extract_mcp_prop_type(prop_data: dict[str, Any]) -> str:
    """Extract human-readable schema type from an MCP property schema, supporting anyOf/oneOf."""
    direct_type = prop_data.get("type")
    if direct_type:
        return str(direct_type)
    variants = prop_data.get("anyOf") or prop_data.get("oneOf") or []
    for sub in variants:
        if isinstance(sub, dict) and sub.get("type") and sub.get("type") != "null":
            return str(sub["type"])
    return "string"


def _parse_mcp_input_schema_parameters(input_schema: Any) -> list[dict[str, Any]]:
    """Extract structured parameter specifications from an MCP tool input schema."""
    if not isinstance(input_schema, dict):
        return []
    props = input_schema.get("properties", {})
    reqs = set(input_schema.get("required", []))
    return [
        {
            "name": prop_name,
            "type": _extract_mcp_prop_type(prop_data) if isinstance(prop_data, dict) else "string",
            "description": prop_data.get("description", "") if isinstance(prop_data, dict) else "",
            "default": prop_data.get("default", None) if isinstance(prop_data, dict) else None,
            "required": prop_name in reqs,
        }
        for prop_name, prop_data in props.items()
    ]


def _mcp_tool_to_doc(tool: Any) -> MCPToolDoc:
    """Convert an instantiated FastMCP tool to an MCPToolDoc documentation model."""
    input_schema = getattr(tool, "parameters", None) or getattr(tool, "inputSchema", None) or {}
    return MCPToolDoc(
        name=tool.name,
        description=tool.description or "",
        parameters=_parse_mcp_input_schema_parameters(input_schema),
    )


def _format_param_default_str(default_val: Any, root_dir: Path) -> str:
    """Format parameter default value with sanitized root and home path representations."""
    if isinstance(default_val, Path):
        try:
            return str(default_val.resolve().relative_to(root_dir.resolve()))
        except ValueError, AttributeError:
            pass
        try:
            return f"~/{default_val.resolve().relative_to(Path.home().resolve())}"
        except ValueError, AttributeError:
            return str(default_val)

    default_str = str(default_val)
    home_str = str(Path.home().resolve())
    root_str = str(root_dir.resolve())
    if root_str and root_str in default_str:
        return default_str.replace(root_str, ".").lstrip("./")
    if home_str and home_str in default_str:
        return default_str.replace(home_str, "~")
    return default_str


def _render_mcp_param_row(p: dict[str, Any]) -> str:
    """Render a single markdown table row for an MCP parameter."""
    req_str = "Yes" if p.get("required") else "No"
    def_val = p.get("default")
    def_str = f"`{def_val}`" if def_val is not None else "-"
    p_desc = p.get("description", "-") or "-"
    p_name = p.get("name", "")
    p_type = p.get("type", "string")
    return f"| `{p_name}` | `{p_type}` | {req_str} | {def_str} | {p_desc} |"


_SENSITIVE_PARAM_KEYWORDS: frozenset[str] = frozenset(
    {"SECRET", "TOKEN", "PASSWORD", "KEY", "AUTH", "CREDENTIAL", "APIKEY", "PASSPHRASE"}
)


class DocGenerator:
    """Introspects Typer / Click CLI trees and generates Markdown documentation."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()

    def introspect_param(self, param: click.Parameter) -> ParamDoc:
        """Extract documentation model from a click Parameter."""
        raw_opts = list(getattr(param, "opts", []))
        sec_opts = list(getattr(param, "secondary_opts", []))
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
            default_str = _format_param_default_str(default_val, self.root_dir)

        is_sensitive = any(
            kw in (param.name or "").upper() or (envvar is not None and kw in envvar.upper())
            for kw in _SENSITIVE_PARAM_KEYWORDS
        )
        if is_sensitive and default_str and default_str not in ("None", "False", "True", "0", ""):
            default_str = "<masked>"

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

    def _introspect_single_group(
        self, name: str, module_path: str, summary: str
    ) -> CommandGroupDoc | None:
        """Introspect a single command module and construct CommandGroupDoc."""
        if not module_path.startswith("devops_cli.commands."):
            return None
        try:
            module = import_module(module_path)
            app_obj = getattr(module, "app", None)
            if app_obj is None:
                return None
            click_cmd = typer.main.get_command(app_obj)
            doc = self.introspect_command(click_cmd, parent_path="devops", override_name=name)
            desc = doc.description or summary
            commands_list = doc.subcommands if doc.is_group else [doc]
            return CommandGroupDoc(
                name=name,
                module_path=module_path,
                summary=summary or doc.summary,
                description=desc,
                commands=commands_list,
            )
        except Exception as exc:
            return CommandGroupDoc(
                name=name,
                module_path=module_path,
                summary=summary,
                description=f"Error introspecting module: {exc}",
                commands=[],
            )

    def introspect_all_groups(self) -> list[CommandGroupDoc]:
        """Introspect all command groups declared in main._COMMAND_SPECS."""
        from devops_cli.main import _COMMAND_SPECS

        groups: list[CommandGroupDoc] = []
        for name, (module_path, summary) in _COMMAND_SPECS.items():
            group_doc = self._introspect_single_group(name, module_path, summary)
            if group_doc is not None:
                groups.append(group_doc)
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
                return [_mcp_tool_to_doc(tool) for tool in tools]

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

    def _render_command_markdown(
        self,
        cmd: CommandDoc,
        lines: list[str],
        level: int = CONST_MARKDOWN_HEADING_LEVEL,
    ) -> None:
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
                    lines.append(_render_mcp_param_row(p))
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

        write_text_file(target, new_content)
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

    def generate_configuration_docs(self) -> str:
        """Programmatically generate Markdown configuration reference from Settings schema."""
        from devops_cli.config.env import OPTION_TO_ENV_VAR
        from devops_cli.config.settings import Settings

        lines: list[str] = [
            "# DevOps CLI Configuration Reference",
            "",
            "This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).",
            "",
            "DevOps CLI supports hierarchical configuration resolution through:",
            "1. **CLI Flags & Arguments** (highest precedence)",
            "2. **Environment Variables** (`DEVOPS_CLI_*`)",
            "3. **Local Project Configuration** (`.devops-cli.yaml`)",
            "4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)",
            "5. **System Defaults**",
            "",
            "---",
            "",
        ]

        sections = [
            (
                "SSH Configuration (`ssh`)",
                "ssh",
                "SSH key generation, rotation, signing, and GitHub registration settings.",
            ),
            (
                "Repositories Configuration (`repos`)",
                "repos",
                "Multi-repository workspace discovery, cloning, and sync settings.",
            ),
            (
                "Workspace Configuration (`workspace`)",
                "workspace",
                "Multi-root VS Code workspace file management and data tier settings.",
            ),
            (
                "Telemetry & Metrics (`telemetry`)",
                "telemetry",
                "OpenTelemetry distributed tracing and Prometheus metric export settings.",
            ),
            (
                "Kubernetes Configuration (`k8s`)",
                "k8s",
                "Kubernetes cluster connection, Minikube, Helm, and Kustomize settings.",
            ),
            (
                "Security Scanner Configuration (`security`)",
                "security",
                "Security scanning engines, vulnerability audits, and policy enforcement.",
            ),
            (
                "AI & LLM Configuration (`ai`)",
                "ai",
                "AI code review, multi-agent pipelines, RAG semantic search, and embeddings.",
            ),
            (
                "Data Storage Tier (`data`)",
                "data",
                "Local artifact caches, review findings, session histories, and log paths.",
            ),
            (
                "OIDC & Authentication (`oidc`)",
                "oidc",
                "OpenID Connect authentication and identity token settings.",
            ),
        ]

        settings = Settings()
        for title, section_key, description in sections:
            section_model = getattr(settings, section_key, None)
            if section_model is None:
                continue

            lines.append(f"## {title}")
            lines.append("")
            lines.append(description)
            lines.append("")
            lines.append("| Option | Type | Default | Environment Variable | Description |")
            lines.append("|---|---|---|---|---|")

            for field_name, field_info in section_model.__class__.model_fields.items():
                opt_key = f"{section_key}.{field_name}"
                env_var = OPTION_TO_ENV_VAR.get(opt_key, "-")
                env_str = f"`{env_var}`" if env_var != "-" else "-"
                type_ann = field_info.annotation
                type_str = getattr(type_ann, "__name__", str(type_ann)).replace("pathlib.", "")
                if "Optional[" in type_str:
                    type_str = type_str.replace("Optional[", "").rstrip("]")
                def_val = getattr(section_model, field_name, None)
                def_str = f"`{def_val}`" if def_val is not None else "-"
                if isinstance(def_val, Path):
                    def_str = f"`{_format_param_default_str(def_val, self.root_dir)}`"
                desc = field_info.description or "-"
                lines.append(f"| `{field_name}` | `{type_str}` | {def_str} | {env_str} | {desc} |")

            lines.append("")

        return "\n".join(lines)

    def generate_error_catalog_docs(self) -> str:
        """Programmatically generate Exit Code and Error Taxonomy catalog from DevOpsCLIError hierarchy."""
        import importlib

        from devops_cli.exceptions.base import DevOpsCLIError

        exception_modules = [
            ("AI & LLM Subsystem", "devops_cli.exceptions.ai"),
            ("Configuration Subsystem", "devops_cli.exceptions.config"),
            ("Git Operations Subsystem", "devops_cli.exceptions.git"),
            ("Kubernetes Subsystem", "devops_cli.exceptions.k8s"),
            ("Network & Egress Subsystem", "devops_cli.exceptions.network"),
            ("Security & Scanner Subsystem", "devops_cli.exceptions.security"),
            ("SSH Key Management", "devops_cli.exceptions.ssh"),
            ("Tool Execution Subsystem", "devops_cli.exceptions.tools"),
            ("Input Validation Subsystem", "devops_cli.exceptions.validation"),
            ("Core & MCP Subsystem", "devops_cli.exceptions.base"),
        ]

        for _, mod_name in exception_modules:
            try:
                importlib.import_module(mod_name)
            except Exception:
                pass

        lines: list[str] = [
            "# DevOps CLI Exit Code & Error Catalog",
            "",
            "This document provides the canonical machine-readable error codes, POSIX exit status codes,",
            "and domain categorization for all exceptions inheriting from `DevOpsCLIError`.",
            "",
            "## Standard Process Exit Codes",
            "",
            "| Exit Code | Constant | Meaning |",
            "|---|---|---|",
            "| `0` | `CONST_EXIT_SUCCESS` | Command completed successfully with zero defects or violations. |",
            "| `1` | `CONST_EXIT_FAILURE` | General operational failure, unhandled runtime defect, or schema violation. |",
            "| `2` | `CONST_EXIT_USAGE` | Invalid CLI arguments, missing parameters, or syntax validation error. |",
            "| `130` | `CONST_EXIT_CANCELLED` | Execution interrupted by user signal (`SIGINT` / `Ctrl+C`). |",
            "",
            "---",
            "",
            "## Subsystem Error Code Matrix",
            "",
            "| Error Code | Exit Code | Domain | Description |",
            "|---|---|---|---|",
        ]

        def get_all_subclasses(cls: type[DevOpsCLIError]) -> list[type[DevOpsCLIError]]:
            subclasses: list[type[DevOpsCLIError]] = []
            for sub in cls.__subclasses__():
                subclasses.append(sub)
                subclasses.extend(get_all_subclasses(sub))
            return subclasses

        all_errs = sorted(get_all_subclasses(DevOpsCLIError), key=lambda c: c.__name__)

        for err_cls in all_errs:
            doc = (err_cls.__doc__ or "").strip().split("\n")[0]
            # Instantiate dummy to get default error_code and exit_code if possible
            try:
                inst = err_cls("error message")
                err_code = getattr(inst, "error_code", err_cls.__name__)
                exit_code = getattr(inst, "exit_code", 1)
            except Exception:
                err_code = getattr(err_cls, "DEFAULT_ERROR_CODE", err_cls.__name__)
                exit_code = getattr(err_cls, "DEFAULT_EXIT_CODE", 1)

            domain = (
                err_cls.__module__.replace("devops_cli.exceptions.", "")
                .replace("devops_cli.exceptions", "core")
                .capitalize()
            )
            lines.append(f"| `{err_code}` | `{exit_code}` | {domain} | {doc or err_cls.__name__} |")

        lines.append("")
        return "\n".join(lines)

    def generate_telemetry_docs(self) -> str:
        """Programmatically generate OpenTelemetry and Prometheus telemetry reference."""
        lines: list[str] = [
            "# DevOps CLI Telemetry & Distributed Tracing Reference",
            "",
            "DevOps CLI instruments all CLI subcommands, background tasks, and AI pipeline stages",
            "with distributed OpenTelemetry traces (`@trace_span`) and in-memory Prometheus metrics (`GLOBAL_METRICS`).",
            "",
            "---",
            "",
            "## Prometheus Metric Instruments",
            "",
            "| Metric Name | Type | Description |",
            "|---|---|---|",
            "| `devops_cli_command_duration_seconds` | Histogram | CLI execution latency waterfall in seconds by subcommand. |",
            "| `devops_cli_command_total` | Counter | Total CLI command invocations partitioned by status and command group. |",
            "| `devops_cli_subprocess_duration_seconds` | Histogram | Subprocess execution latency in seconds across external binaries. |",
            "| `devops_cli_subprocess_total` | Counter | Total external tool executions partitioned by binary and exit status. |",
            "| `devops_cli_ai_llm_requests_total` | Counter | Total AI / LLM completions dispatched by provider and model. |",
            "| `devops_cli_ai_token_usage_total` | Counter | Cumulative input and output token consumption across review stages. |",
            "| `devops_cli_security_findings_total` | Counter | Total security vulnerabilities and anti-patterns flagged by scanner. |",
            "| `devops_cli_cache_hits_total` | Counter | Semantic cache hits for embeddings and AI review prompt hashes. |",
            "| `devops_cli_cache_misses_total` | Counter | Semantic cache misses triggering fresh LLM inference requests. |",
            "",
            "---",
            "",
            "## Distributed Tracing & W3C Context Propagation",
            "",
            "- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.",
            "- **W3C `traceparent` Injection**: Subprocess calls inject standard W3C `traceparent` headers into child process environments.",
            "- **OTLP Exporter**: Spans are emitted to OpenTelemetry Collector via `DEVOPS_CLI_OTEL_ENDPOINT` (`http://localhost:4318/v1/traces`).",
            "",
        ]
        return "\n".join(lines)

    def generate_knowledge_base_index(self) -> str:
        """Programmatically generate Knowledge Base catalog from bundled articles."""
        from devops_cli.ai.kb import get_knowledge_base_stats, list_knowledge_base_articles

        stats = get_knowledge_base_stats()
        devops_cli_articles = sorted(list_knowledge_base_articles("devops_cli"))
        it_domains_articles = sorted(list_knowledge_base_articles("it_domains"))

        lines: list[str] = [
            "# DevOps CLI Knowledge Base Catalog",
            "",
            f"The bundled Knowledge Base provides **{stats.total_articles} operational and architectural manuals**",
            "grounding DevOps CLI subcommands, multi-agent AI reviews, and developer workflows.",
            "",
            "---",
            "",
            "## Division 1: DevOps CLI Information (`devops_cli/`)",
            "",
            f"**Total Articles**: {stats.devops_cli_count} manuals covering internals, configuration, tasks, and libraries.",
            "",
            "| Category | Article File | Topic & Scope |",
            "|---|---|---|",
        ]

        def _format_article_link(art_path: Path) -> str:
            art_posix = art_path.as_posix()
            if "src/devops_cli/ai/knowledge_base/" in art_posix:
                rel_suffix = art_posix.split("src/devops_cli/ai/knowledge_base/", 1)[1]
                return f"../src/devops_cli/ai/knowledge_base/{rel_suffix}"
            return art_path.name

        for art in devops_cli_articles:
            category = art.parent.name
            art_name = art.stem.replace("_", " ").title()
            link_target = _format_article_link(art)
            lines.append(f"| `{category}` | [`{art.name}`]({link_target}) | {art_name} |")

        lines.extend(
            [
                "",
                "---",
                "",
                "## Division 2: Information Technology Domain-Specific (`it_domains/`)",
                "",
                f"**Total Articles**: {stats.it_domains_count} manuals covering {stats.topics_count} IT topics and {stats.tools_count} tool references.",
                "",
                "| Category | Article File | Topic & Scope |",
                "|---|---|---|",
            ]
        )

        for art in it_domains_articles:
            category = art.parent.name
            art_name = art.stem.replace("_", " ").title()
            link_target = _format_article_link(art)
            lines.append(f"| `{category}` | [`{art.name}`]({link_target}) | {art_name} |")

        lines.append("")
        return "\n".join(lines)

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

        # 4. Configuration Reference
        results["CONFIGURATION.md"] = self.generate_configuration_docs()

        # 5. Exit Code & Error Catalog
        results["ERRORS.md"] = self.generate_error_catalog_docs()

        # 6. Telemetry & Distributed Tracing Reference
        results["TELEMETRY.md"] = self.generate_telemetry_docs()

        # 7. Knowledge Base Catalog
        results["KNOWLEDGE_BASE.md"] = self.generate_knowledge_base_index()

        # 8. Individual command group markdown files under commands/
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
            write_text_file(dest, content)
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
            "groups": [g.model_dump() for g in groups],
            "env_vars": [e.model_dump() for e in env_specs],
            "mcp_tools": [t.model_dump() for t in mcp_tools],
        }
