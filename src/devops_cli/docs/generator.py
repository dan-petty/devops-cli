"""Automated documentation generation engine for devops-cli."""

from __future__ import annotations

import asyncio
import concurrent.futures
import itertools
import re
from pathlib import Path, PurePath
from typing import Any

import click
from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_CONFIG_BACKUP_INFIX,
    CONST_CONFIG_BACKUPS_KEPT,
    CONST_DOC_CREDENTIAL_NAME_WORD_PAIRS,
    CONST_DOC_CREDENTIAL_NAME_WORDS,
    CONST_DOC_CREDENTIAL_NAMING_WORD,
    CONST_DOMAIN_EXCEPTION_MODULES,
    CONST_MARKDOWN_HEADING_LEVEL,
    CONST_PROJECT_CONFIG_CANDIDATES,
    CONST_SETTINGS_SECTION_METADATA,
    CONST_STANDARD_HTML_TAGS,
)
from devops_cli.config.defaults import DEFAULT_OTEL_ENDPOINT
from devops_cli.config.env import (
    ENV_OTEL_EXPORTER_OTLP_ENDPOINT,
    ENV_TELEMETRY_ENABLED,
    ENV_TELEMETRY_ENDPOINT,
    EnvVarSpec,
    get_all_env_var_specs,
)
from devops_cli.core.command_resolver import module_click_command
from devops_cli.output import write_text_file
from devops_cli.telemetry import trace_span

_RICH_TAG_RE = re.compile(
    r"\[/?(?:bold|dim|green|cyan|yellow|red|magenta|blue|italic|underline)[^\]]*\]"
)
_PLACEHOLDER_TAG_RE = re.compile(r"<([a-zA-Z][a-zA-Z0-9_-]*)>")

_IGNORED_PARAM_NAMES = {"help", "install_completion", "show_completion"}


def _escape_angle_brackets(text: str) -> str:
    """Escape placeholder angle brackets like <org> outside inline code spans."""
    if "<" not in text:
        return text
    parts = text.split("`")
    for index in range(0, len(parts), 2):

        def _replace_tag(match: re.Match[str]) -> str:
            tag = match.group(1)
            if tag.lower() in CONST_STANDARD_HTML_TAGS:
                return match.group(0)
            return f"\\<{tag}\\>"

        parts[index] = _PLACEHOLDER_TAG_RE.sub(_replace_tag, parts[index])
    return "`".join(parts)


def _clean_text(text: str | None) -> str:
    """Remove rich markup tags, normalize whitespace, and escape raw angle brackets."""
    if not text:
        return ""
    cleaned = _RICH_TAG_RE.sub("", text)
    return _escape_angle_brackets(cleaned.strip())


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
    # The switches that turn a boolean option off, such as `--root` for `--rootless/--root`.
    off_flags: list[str] = Field(default_factory=list)
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
    usage: str = ""
    params: list[ParamDoc] = Field(default_factory=list)
    commands: list[CommandDoc] = Field(default_factory=list)


class MCPToolDoc(BaseModel):
    """Documentation model for a FastMCP tool."""

    name: str
    description: str
    read_only_hint: bool | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)


def _select_non_null_mcp_variant(prop_data: dict[str, Any]) -> dict[str, Any]:
    """Return the first non-null variant dict when a schema property uses anyOf/oneOf."""
    variants = prop_data.get("anyOf") or prop_data.get("oneOf") or []
    for sub in variants:
        if isinstance(sub, dict) and sub.get("type") != "null":
            return sub
    return prop_data


def _extract_mcp_prop_type(prop_data: dict[str, Any]) -> str:
    """Extract human-readable schema type from an MCP property schema, including items and enums."""
    variant = _select_non_null_mcp_variant(prop_data) if not prop_data.get("type") else prop_data
    base_type = str(variant.get("type") or "string")
    items = variant.get("items")
    if base_type == "array" and isinstance(items, dict):
        return f"array[{_extract_mcp_prop_type(items)}]"
    enum_values = variant.get("enum")
    if isinstance(enum_values, list) and enum_values:
        joined = ", ".join(str(v) for v in enum_values)
        return f"{base_type} ({joined})"
    return base_type


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
    input_schema = (
        getattr(tool, "parameters", None)
        or getattr(tool, "input_schema", None)
        or getattr(tool, "inputSchema", None)
        or {}
    )
    annotations = getattr(tool, "annotations", None)
    raw_hint = getattr(annotations, "read_only_hint", None) if annotations is not None else None
    read_only_hint = raw_hint if isinstance(raw_hint, bool) else None
    return MCPToolDoc(
        name=tool.name,
        description=tool.description or "",
        read_only_hint=read_only_hint,
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


def _option_flags_cell(opt: ParamDoc) -> str:
    """An option's switches: its aliases joined by commas, then its off switches after a slash."""
    groups = [opt.flags, opt.off_flags] if opt.off_flags else [opt.flags]
    return " / ".join(", ".join(f"`{flag}`" for flag in group) for group in groups)


def _names_a_credential(name: str | None) -> bool:
    """Whether a parameter or environment variable name says its value is a credential.

    The name's words, split on `_` and `-`, are matched whole, so MAX_TOKENS and VALKEY_PORT name
    none. A name ending in NAME holds what a credential is called, not the credential.
    """
    words = tuple(word for word in (name or "").upper().replace("-", "_").split("_") if word)
    if not words or words[-1] == CONST_DOC_CREDENTIAL_NAMING_WORD:
        return False
    return not (
        CONST_DOC_CREDENTIAL_NAME_WORDS.isdisjoint(words)
        and CONST_DOC_CREDENTIAL_NAME_WORD_PAIRS.isdisjoint(itertools.pairwise(words))
    )


def _masks_default(param: click.Parameter, envvar: str | None, default_val: Any) -> bool:
    """Whether the reference withholds a parameter's default as a possible credential.

    An option that hides its input, Click's own marker for a secret, always does. Otherwise the
    name or envvar must name a credential, and the default must be something a credential can
    be: a number, a boolean or a path is not.
    """
    if getattr(param, "hide_input", False):
        return True
    if isinstance(default_val, bool | int | float | PurePath):
        return False
    return _names_a_credential(param.name) or _names_a_credential(envvar)


class DocGenerator:
    """Introspects Typer / Click CLI trees and generates Markdown documentation."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()
        self._cached_groups: list[CommandGroupDoc] | None = None

    def introspect_param(self, param: click.Parameter) -> ParamDoc:
        """Extract documentation model from a click Parameter."""
        raw_opts = list(getattr(param, "opts", []))
        sec_opts = list(getattr(param, "secondary_opts", []))
        is_option = any(opt.startswith("-") for opt in raw_opts)

        flags: list[str] = []
        off_flags: list[str] = []
        if is_option:
            flags, off_flags = raw_opts, sec_opts
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

        if default_str and _masks_default(param, envvar, default_val):
            default_str = "<masked>"

        return ParamDoc(
            name=param.name or "",
            kind=kind,
            flags=flags,
            off_flags=off_flags,
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

    def _introspect_leaf_or_group(
        self, click_cmd: Any, name: str, module_path: str, summary: str
    ) -> CommandGroupDoc:
        """Introspect a command as either a leaf command alias or a command group."""
        if hasattr(click_cmd, "commands") and name in click_cmd.commands:
            leaf_cmd = click_cmd.commands[name]
            doc = self.introspect_command(leaf_cmd, parent_path="devops", override_name=name)
            return CommandGroupDoc(
                name=name,
                module_path=module_path,
                summary=summary or doc.summary,
                description=doc.description or summary,
                commands=[doc],
            )
        doc = self.introspect_command(click_cmd, parent_path="devops", override_name=name)
        commands_list = doc.subcommands if doc.is_group else [doc]
        return CommandGroupDoc(
            name=name,
            module_path=module_path,
            summary=summary or doc.summary,
            description=doc.description or summary,
            usage=doc.usage if doc.is_group else "",
            params=doc.params if doc.is_group else [],
            commands=commands_list,
        )

    def _introspect_single_group(
        self, name: str, module_path: str, summary: str
    ) -> CommandGroupDoc | None:
        """Introspect a single command module and construct CommandGroupDoc."""
        if not module_path.startswith("devops_cli.commands."):
            return None
        try:
            click_cmd = module_click_command(module_path)
            if click_cmd is None:
                return None
            return self._introspect_leaf_or_group(click_cmd, name, module_path, summary)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to introspect command group '{name}' ({module_path}): {exc}. "
                "A missing optional dependency now fails the docs stage, by design."
            ) from exc

    def introspect_all_groups(self, force: bool = False) -> list[CommandGroupDoc]:
        """Introspect all command groups declared in main._COMMAND_SPECS."""
        if not force and self._cached_groups is not None:
            return self._cached_groups

        from devops_cli.main import _COMMAND_SPECS

        with trace_span("docs.introspect_groups") as span:
            groups: list[CommandGroupDoc] = []
            for name, (module_path, summary) in _COMMAND_SPECS.items():
                group_doc = self._introspect_single_group(name, module_path, summary)
                if group_doc is not None:
                    groups.append(group_doc)
            span.set_attributes({"group_count": len(groups)})
            self._cached_groups = groups
            return groups

    def introspect_env_vars(self) -> list[EnvVarSpec]:
        """Collect all environment variable specifications."""
        return get_all_env_var_specs()

    def _fetch_mcp_tools(self) -> list[MCPToolDoc]:
        """Query running or dedicated loop for FastMCP tools."""
        try:
            from devops_cli.ai.mcp.server import mcp

            async def _get_tools() -> list[MCPToolDoc]:
                # The registry, not the client-facing listing: `docs/MCP_TOOLS.md` is
                # the published catalogue, and `mcp.list_tools()` runs the domain gate,
                # which would cut the reference to the eager domains alone.
                tools = await asyncio.wait_for(mcp._list_tools(), timeout=10.0)
                return [_mcp_tool_to_doc(tool) for tool in tools]

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                try:
                    fut = pool.submit(asyncio.run, _get_tools())
                    return fut.result(timeout=15.0)
                finally:
                    pool.shutdown(wait=False, cancel_futures=True)
            return asyncio.run(_get_tools())
        except Exception as exc:
            raise RuntimeError(
                f"Failed to introspect FastMCP tools (devops_cli.ai.mcp.server): {exc}. "
                "A missing optional dependency now fails the docs stage, by design."
            ) from exc

    def introspect_mcp_tools(self) -> list[MCPToolDoc]:
        """Collect all registered FastMCP tools."""
        with trace_span("docs.introspect_mcp_tools") as span:
            tools = self._fetch_mcp_tools()
            span.set_attributes({"tool_count": len(tools)})
            return tools

    @staticmethod
    def _append_params_tables(params: list[ParamDoc], lines: list[str]) -> None:
        """Append Arguments and Options markdown tables for a parameter list."""
        args = [p for p in params if p.kind == "argument"]
        opts = [p for p in params if p.kind in ("option", "flag")]

        if args:
            lines.extend(
                [
                    "**Arguments:**",
                    "",
                    "| Argument | Type | Required | Description |",
                    "|---|---|---|---|",
                    *(
                        f"| {f'`{a.flags[0]}`' if a.flags else f'`{a.name}`'} | "
                        f"`{a.type_name}` | {'Yes' if a.required else 'No'} | "
                        f"{a.description or '-'} |"
                        for a in args
                    ),
                    "",
                ]
            )

        if opts:
            lines.extend(
                [
                    "**Options:**",
                    "",
                    "| Option / Flag | Type | Default | Description |",
                    "|---|---|---|---|",
                    *(
                        f"| {_option_flags_cell(o)} | `{o.type_name}` | "
                        f"{f'`{o.default}`' if o.default is not None else '-'} | "
                        f"{o.description or '-'}{f' *(Env: `{o.envvar}`)*' if o.envvar else ''} |"
                        for o in opts
                    ),
                    "",
                ]
            )

    def _append_group_callback_section(self, group: CommandGroupDoc, lines: list[str]) -> None:
        """Append group-level usage and callback parameter tables when the group has options."""
        if not group.params:
            return
        if group.usage:
            lines.extend(["```bash", group.usage, "```", ""])
        self._append_params_tables(group.params, lines)

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
        lines.extend(["", "---", ""])

        for group in groups:
            lines.extend([f"## devops {group.name}", "", f"{group.summary}", ""])
            if group.description and group.description != group.summary:
                lines.extend([f"{group.description}", ""])
            self._append_group_callback_section(group, lines)

            if not group.commands:
                lines.extend(["*No subcommands available.*", ""])
                continue

            for cmd in group.commands:
                self._render_command_markdown(cmd, lines, level=3)

            lines.extend(["---", ""])

        return "\n".join(lines)

    def _render_command_markdown(
        self,
        cmd: CommandDoc,
        lines: list[str],
        level: int = CONST_MARKDOWN_HEADING_LEVEL,
    ) -> None:
        """Render a single command or recursive subcommands into Markdown lines."""
        heading = "#" * level
        lines.extend([f"{heading} `{cmd.full_path}`", ""])
        if cmd.summary:
            lines.extend([f"**{cmd.summary}**", ""])
        if cmd.description and cmd.description != cmd.summary:
            lines.extend([f"{cmd.description}", ""])

        lines.extend(["```bash", cmd.usage, "```", ""])
        self._append_params_tables(cmd.params, lines)

        for sub in cmd.subcommands:
            self._render_command_markdown(sub, lines, level=level + 1)

    def render_command_group_markdown(self, group: CommandGroupDoc) -> str:
        """Render documentation for a single command group."""
        lines: list[str] = [
            f"# `devops {group.name}`",
            "",
            f"{group.summary}",
            "",
        ]
        self._append_group_callback_section(group, lines)
        lines.extend(["## Commands", ""])
        for cmd in group.commands:
            self._render_command_markdown(cmd, lines, level=2)
            lines.extend(["---", ""])
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
            "- A credential (`*.token`, `*.api_key`, `*.password`) goes to the OS keyring with "
            "`devops config set <key>`, which asks for it at a hidden prompt. A multi-line "
            "credential, such as a PEM private key, comes from a file with "
            "`devops config set <key> --from-file key.pem`, or from stdin with `--from-file -`."
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
            "| Tool Name | `readOnlyHint` | Description |",
            "|---|---|---|",
        ]

        for tool in sorted(tools, key=lambda t: t.name):
            anchor = tool.name.replace("_", "-")
            summary = " ".join(tool.description.splitlines()).strip()
            hint_cell = (
                f"`{str(tool.read_only_hint).lower()}`" if tool.read_only_hint is not None else "-"
            )
            lines.append(f"| [`{tool.name}`](#{anchor}) | {hint_cell} | {summary} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        for tool in sorted(tools, key=lambda t: t.name):
            lines.append(f"### `{tool.name}`")
            lines.append("")
            lines.append(f"{tool.description}")
            lines.append("")
            if tool.read_only_hint is not None:
                lines.append(f"**Annotations:** `readOnlyHint: {str(tool.read_only_hint).lower()}`")
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

    @staticmethod
    def render_synced_readme(content: str, matrix_table: str) -> str | None:
        """Substitute or insert Complete Command Matrix table into README content."""
        start_marker = "<!-- COMMAND_MATRIX_START -->"
        end_marker = "<!-- COMMAND_MATRIX_END -->"

        if start_marker in content and end_marker in content:
            pattern = re.compile(
                rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
                re.DOTALL,
            )
            return pattern.sub(
                f"{start_marker}\n\n{matrix_table}\n\n{end_marker}",
                content,
            )

        pattern = re.compile(
            r"(## Complete Command Matrix\s*\n\n)"
            r"(?:<!-- COMMAND_MATRIX_START -->\s*)?\|.*?(?=\n\n---|\n\n## |\Z)",
            re.DOTALL,
        )
        if pattern.search(content):
            return pattern.sub(
                rf"\g<1>{start_marker}\n\n{matrix_table}\n\n{end_marker}",
                content,
            )
        return None

    def sync_readme(
        self,
        readme_path: Path | None = None,
        docs: dict[str, str] | None = None,
    ) -> bool:
        """Synchronize the Complete Command Matrix table in README.md."""
        target = self._find_readme(readme_path)
        if not target.exists():
            return False

        with trace_span("docs.sync_readme", attributes={"readme_path": str(target)}):
            if docs is not None:
                if "README.md" not in docs:
                    return False
                new_content = docs["README.md"]
            else:
                content = target.read_text(encoding="utf-8")
                groups = self.introspect_all_groups()
                matrix_table = self.render_readme_matrix(groups)
                synced = self.render_synced_readme(content, matrix_table)
                if synced is None:
                    return False
                new_content = synced

            write_text_file(target, new_content)
            return True

    @staticmethod
    def _check_readme_matrix_content(
        content: str, matrix_table: str, target: Path
    ) -> tuple[bool, str | None]:
        """Check if markers or heading in content match matrix_table."""
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

    def check_readme(
        self,
        readme_path: Path | None = None,
        docs: dict[str, str] | None = None,
    ) -> tuple[bool, str | None]:
        """Check if Complete Command Matrix table in README.md is in sync."""
        target = self._find_readme(readme_path)
        if not target.exists():
            return False, f"Missing README file: {target}"

        content = target.read_text(encoding="utf-8")
        if docs is not None:
            if "README.md" not in docs:
                return True, None
            if content.strip() != docs["README.md"].strip():
                return (
                    False,
                    f"Out-of-date Command Matrix in {target}: "
                    "README.md table differs from CLI state.",
                )
            return True, None

        groups = self.introspect_all_groups()
        matrix_table = self.render_readme_matrix(groups)
        return self._check_readme_matrix_content(content, matrix_table, target)

    def _format_settings_field_row(
        self,
        field_name: str,
        field_info: Any,
        def_val: Any,
        opt_key: str,
        option_to_env: dict[str, str],
    ) -> str:
        """Render a single configuration field row for CONFIGURATION.md."""
        env_var = option_to_env.get(opt_key, "-")
        env_str = f"`{env_var}`" if env_var != "-" else "-"
        type_ann = field_info.annotation
        type_str = getattr(type_ann, "__name__", str(type_ann)).replace("pathlib.", "")
        if "Optional[" in type_str:
            type_str = type_str.replace("Optional[", "").rstrip("]")
        def_str = f"`{def_val}`" if def_val is not None else "-"
        if isinstance(def_val, Path):
            def_str = f"`{_format_param_default_str(def_val, self.root_dir)}`"
        desc = field_info.description or "-"
        return f"| `{field_name}` | `{type_str}` | {def_str} | {env_str} | {desc} |"

    def generate_configuration_docs(self) -> str:
        """Programmatically generate Markdown configuration reference from Settings schema."""
        from devops_cli.config.env import OPTION_TO_ENV_VAR
        from devops_cli.config.settings import Settings

        candidates_str = (
            ", ".join(f"`{c}`" for c in CONST_PROJECT_CONFIG_CANDIDATES[:-1])
            + f" or `{CONST_PROJECT_CONFIG_CANDIDATES[-1]}`"
        )
        lines: list[str] = [
            "# DevOps CLI Configuration Reference",
            "",
            "This document is automatically generated from `Settings` (`src/devops_cli/config/settings.py`).",
            "",
            "DevOps CLI supports hierarchical configuration resolution through:",
            "1. **CLI Flags & Arguments** (highest precedence)",
            "2. **Environment Variables** (`DEVOPS_CLI_*`)",
            "3. **Local Project Configuration** (the file `DEVOPS_CLI_CONFIG` names, else the "
            f"nearest {candidates_str} from the working directory up to its repository root)",
            "4. **Global User Configuration** (`~/.config/devops-cli/config.yaml`)",
            "5. **System Defaults**",
            "",
            "A `devops review` command reads a tree it does not own. Started in a repository "
            "other than devops-cli's own, it looks for no project configuration, reading only the "
            "file `DEVOPS_CLI_CONFIG` names, and it resolves a relative data path under "
            "`~/.local/share/devops-cli` rather than under that repository, so its default data "
            "directory is `~/.local/share/devops-cli/.data`. What a review keeps -- its sessions, "
            "the feedback dataset, runs, samples, library contracts and AI spend -- every other "
            "command started outside devops-cli's own repository reads and writes there too. "
            "devops-cli's own repository "
            "is the one whose checkout holds the source of the devops-cli that runs, as an "
            "editable install's does; its code already runs, so a review started there, or in "
            "any worktree of it, reads its project configuration and keeps all data under its "
            "main worktree's `.data`, as every other command does. A clone nested in that "
            "checkout is another repository, and an installed devops-cli trusts no repository "
            "this way. An absolute `DEVOPS_CLI_DATA_DIR` or `data.dir` names the data directory "
            "every command uses.",
            "",
            "A command that saves settings, such as `devops config set`, writes the file "
            "`DEVOPS_CLI_CONFIG` names, else the project configuration it finds, else the global "
            "one. It writes the whole file from the settings it loaded. Before it changes the "
            f"file, it copies the file to `<name>{CONST_CONFIG_BACKUP_INFIX}<YYYYMMDD-HHMMSS>` "
            f"in the same directory, with the time in UTC, and keeps the newest "
            f"{CONST_CONFIG_BACKUPS_KEPT} copies. Then it appends a record to the audit log "
            "(`data.audit_log_path`) with the command and the dotted names of the keys that "
            "changed, never a value. A save that changes no byte of the file writes nothing.",
            "",
            "---",
            "",
        ]

        settings = Settings()
        scalar_rows: list[str] = []
        for section_key, top_info in Settings.model_fields.items():
            section_val = getattr(settings, section_key, None)
            if not isinstance(section_val, BaseModel):
                scalar_rows.append(
                    self._format_settings_field_row(
                        section_key, top_info, section_val, section_key, OPTION_TO_ENV_VAR
                    )
                )
                continue

            title, description = CONST_SETTINGS_SECTION_METADATA.get(
                section_key,
                (
                    f"{section_key.replace('_', ' ').title()} Configuration (`{section_key}`)",
                    top_info.description or f"{section_key} configuration settings.",
                ),
            )
            lines.extend(
                [
                    f"## {title}",
                    "",
                    description,
                    "",
                    "| Option | Type | Default | Environment Variable | Description |",
                    "|---|---|---|---|---|",
                    *(
                        self._format_settings_field_row(
                            field_name,
                            field_info,
                            getattr(section_val, field_name, None),
                            f"{section_key}.{field_name}",
                            OPTION_TO_ENV_VAR,
                        )
                        for field_name, field_info in section_val.__class__.model_fields.items()
                    ),
                    "",
                ]
            )

        if scalar_rows:
            lines.extend(
                [
                    "## Top-Level Settings",
                    "",
                    "Top-level workstation and environment settings.",
                    "",
                    "| Option | Type | Default | Environment Variable | Description |",
                    "|---|---|---|---|---|",
                    *scalar_rows,
                    "",
                ]
            )

        return "\n".join(lines)

    @staticmethod
    def _import_all_exception_modules() -> None:
        """Import every module defining DevOpsCLIError subclasses, failing closed on error."""
        import importlib
        import pkgutil

        import devops_cli.exceptions

        module_names = [
            *(
                mod_name
                for _, mod_name, _ in pkgutil.iter_modules(
                    devops_cli.exceptions.__path__, prefix="devops_cli.exceptions."
                )
            ),
            *CONST_DOMAIN_EXCEPTION_MODULES,
        ]
        for mod_name in module_names:
            try:
                importlib.import_module(mod_name)
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to import exception module '{mod_name}': {exc}. "
                    "A missing optional dependency now fails the docs stage, by design."
                ) from exc

    @staticmethod
    def _instantiate_error_for_catalog(err_cls: type[Exception]) -> tuple[str, int]:
        """Instantiate a DevOpsCLIError subclass with dummy required arguments to read its codes."""
        import inspect

        params = list(inspect.signature(err_cls).parameters.values())
        pos_args = [
            "error"
            for p in params
            if p.default is inspect.Parameter.empty
            and p.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        kw_args = {
            p.name: "error"
            for p in params
            if p.default is inspect.Parameter.empty and p.kind == inspect.Parameter.KEYWORD_ONLY
        }
        inst = err_cls(*pos_args, **kw_args)
        return str(getattr(inst, "error_code", err_cls.__name__)), int(
            getattr(inst, "exit_code", 1)
        )

    def generate_error_catalog_docs(self) -> str:
        """Programmatically generate Exit Code and Error Taxonomy catalog from DevOpsCLIError hierarchy."""
        from devops_cli.exceptions.base import DevOpsCLIError

        self._import_all_exception_modules()

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
            "An error code may be shared by a base class and its subclasses; the exception column",
            "names the class each row describes. One code never maps to two exit statuses.",
            "",
            "The Exit Code column is the exception's `exit_code` attribute. Only `devops cloudflare`, "
            "`devops valkey` and `devops sandbox` exit with it today; other commands exit 1 when one "
            "of these exceptions escapes.",
            "",
            "| Exception | Error Code | Exit Code | Domain | Description |",
            "|---|---|---|---|---|",
        ]

        def get_all_subclasses(cls: type[DevOpsCLIError]) -> set[type[DevOpsCLIError]]:
            subclasses: set[type[DevOpsCLIError]] = set()
            for sub in cls.__subclasses__():
                subclasses.add(sub)
                subclasses.update(get_all_subclasses(sub))
            return subclasses

        all_errs = sorted(get_all_subclasses(DevOpsCLIError), key=lambda c: c.__name__)

        for err_cls in all_errs:
            doc = (err_cls.__doc__ or "").strip().split("\n")[0]
            err_code, exit_code = self._instantiate_error_for_catalog(err_cls)
            domain = (
                err_cls.__module__.replace("devops_cli.exceptions.", "")
                .replace("devops_cli.exceptions", "core")
                .capitalize()
            )
            lines.append(
                f"| `{err_cls.__name__}` | `{err_code}` | `{exit_code}` | {domain} | "
                f"{doc or err_cls.__name__} |"
            )

        lines.append("")
        return "\n".join(lines)

    def generate_telemetry_docs(self) -> str:
        """Programmatically generate OpenTelemetry and Prometheus telemetry reference."""
        from devops_cli.telemetry.instruments import INSTRUMENTS

        lines: list[str] = [
            "# DevOps CLI Telemetry & Distributed Tracing Reference",
            "",
            "DevOps CLI instruments all CLI subcommands, background tasks, and AI pipeline stages",
            "with distributed OpenTelemetry traces (`@trace_span`) and OTLP metrics.",
            "",
            "---",
            "",
            "## Prometheus Metric Instruments",
            "",
            "Each command runs as its own short-lived process. An OpenTelemetry SDK `MeterProvider`",
            "with `DELTA` aggregation temporality and `ExponentialBucketHistogramAggregation`",
            "aggregates every counter, histogram, and gauge recording in memory over the command's",
            "run and flushes one OTLP `/v1/metrics` batch when the command finishes (`shutdown()`).",
            "`devops serve --service` is one long process, so it also flushes when each lane batch",
            "ends. One flush runs at a time, so the deltas reach the collector in the order they",
            "were collected.",
            "The collector's `deltatocumulative` processor adds the deltas of each stream (its",
            "resource, scope, metric and attributes) into a running total before Prometheus stores",
            "it. Prometheus names a series by `service.name` (`job`), `service.instance.id`",
            "(`instance`) and the metric's attributes. The `service.instance.id` is the host name,",
            "which every command on the host shares. The standard `OTEL_RESOURCE_ATTRIBUTES` sets",
            "another one: roadmap-service sets `service.instance.id=roadmap-service`, so a new pod",
            "writes the series of the pod before it. A running total that starts again from zero,",
            "for a new pod or for a stream that gets no delta for `max_stale` (`1h` in",
            "`k8s/otel/values.yaml`), is a counter reset to `rate()` and `increase()`.",
            "Prometheus 3 stores each histogram as a",
            "native histogram under the instrument's own name, with no `_bucket`, `_sum` or",
            "`_count` series; query it with `histogram_quantile`, `histogram_avg` and",
            "`histogram_count`.",
            "`devops telemetry connect` points devops-cli at the cluster's collector.",
            "",
            "| Metric Name | Type | Unit | Description |",
            "|---|---|---|---|",
            *(
                f"| `{i.name}` | {i.kind.value.title()} | `{i.unit}` | {i.description}. |"
                for i in INSTRUMENTS
            ),
            "",
            'No process sends local savings in USD. `devops_cli_ai_tokens_total{local="true"}`',
            "counts the tokens that a local model ran, and the AI spend dashboard multiplies them",
            "by the Prometheus recording rule `devops_cli:ai_reference_price_usd_per_token` in",
            "`k8s/monitoring/prometheus-values.yaml`. The rule holds genai-prices' price of the",
            "default reference model for each operation and token type, so the workstation and",
            "the Service are priced at one reference. `ai.reference_model` and",
            "`ai.reference_embedding_model` price only the local ledger that `devops ai cost`",
            "reports.",
            "",
            "---",
            "",
            "## Distributed Tracing & W3C Context Propagation",
            "",
            "- **Root Trace Context**: CLI delegate sets up root spans (`cli.<subcommand>`) with execution metadata.",
            "- **No Argument Values**: The command spans describe the command line with the "
            "command (`cli.command`), its command path (`cli.command_path`, such as `devops config "
            "set`), the number of arguments (`cli.args_count`) and the names of the parameters "
            "(`cli.kwargs_keys`). They do not record the argument values. An argument can be a "
            "credential (`devops config set <key> <value>`), and a secret pattern does not find "
            "all credentials. For this reason, the resource also has no `process.command_line` "
            "and no `process.command_args`. The OpenTelemetry semantic conventions make these two "
            "attributes Opt-In.",
            "- **Subprocess Spans**: Each program that devops-cli runs gets a `subprocess.<program>` "
            "span with the name of the program (`process.executable.name`) and the number of its "
            "arguments (`process.args_count`). By default the span does not record the arguments, "
            "because a command such as `devops uv run` or `devops gh api` passes the arguments of "
            "a person on to the program. To record them for a debugging session, set "
            "`telemetry.capture_command_args` to `true` "
            "(`devops config set telemetry.capture_command_args true`). Then the span holds the "
            "arguments in `process.command_args`, each argument through the secret mask. The "
            "mask does not find all credentials, so set the option back to `false` after the "
            "session. A subprocess span never holds `process.command_line`.",
            "- **Usage Errors**: The message of a usage error quotes the arguments, such as "
            "`Got unexpected extra argument (<value>)` from the parser or a `typer.BadParameter` "
            "that a command raises. Thus the command spans record the class of the error "
            "(`error.type`) and the exit code (`cli.exit_code`), and not the message. The person "
            "sees the error box of Typer, and `devops_cli_command_total` counts the command with "
            "the status `error`.",
            "- **W3C `traceparent` Injection**: Subprocesses, sandbox containers (`devops sandbox "
            "deploy`, `devops docker sandbox`, `devops test sandbox`) and commands run with "
            "`devops sandbox exec` receive the active span as `TRACEPARENT` in their environment "
            "(and `TRACESTATE` when one is set). A container's parent is its `sandbox.deploy` or "
            "`docker.workload_sandbox.run` span, and each exec's is its own `sandbox.exec` span. "
            "With telemetry disabled, nothing is added.",
            "- **OTLP Exporter**: Spans and metrics go to the OpenTelemetry Collector at "
            f"`telemetry.endpoint` (`{ENV_TELEMETRY_ENDPOINT}`). When devops-cli's configuration "
            f"names none, OpenTelemetry's own `{ENV_OTEL_EXPORTER_OTLP_ENDPOINT}` names it, else "
            f"`{DEFAULT_OTEL_ENDPOINT}`. `telemetry.enabled` (`{ENV_TELEMETRY_ENABLED}`) turns "
            "export off. When the configuration cannot load, those two variables alone decide, "
            f"and export stays off unless `{ENV_TELEMETRY_ENABLED}` turns it on.",
            "",
            *self._llm_span_attribute_lines(),
        ]
        return "\n".join(lines)

    @staticmethod
    def _llm_span_attribute_lines() -> list[str]:
        """The LLM span section, naming the GenAI conventions commit the snapshot pins."""
        from devops_cli.telemetry.semconv import load_genai_snapshot

        source = load_genai_snapshot()["source"]
        return [
            "---",
            "",
            "## LLM Span Attributes",
            "",
            "LLM spans follow the OpenTelemetry GenAI semantic conventions, which live in "
            f"`{source['repo']}` and have no tagged release. "
            "`src/devops_cli/telemetry/semconv_genai.json` pins them to commit "
            f"`{source['commit']}`, resolved with weaver {source['weaver']}, and lists their "
            "current attribute keys, metric names and span types.",
            "",
            "- **Inference spans**: `ai.llm.dispatch` and `ai.llm.stream` are CLIENT spans of the "
            "`gen_ai.inference.client` type. Both carry `gen_ai.operation.name` (`chat`), "
            "`gen_ai.provider.name` (`anthropic` for the `claude` provider, other provider ids "
            "unchanged) and `gen_ai.request.model`, plus `server.address` and `server.port` when "
            "one backend host served the request. Only `ai.llm.dispatch` carries the reply's "
            "usage (`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`) and "
            "`gen_ai.response.model`. `ai.llm.stream` carries `gen_ai.request.stream` and "
            "`gen_ai.response.time_to_first_chunk` in seconds. Both carry "
            "`gen_ai.response.finish_reasons` with the reason the provider gave for the reply's "
            "end (`stop`, `length`, `content_filter` or `tool_call`), and leave it out when the "
            "provider gave none.",
            "- **Wrapper spans**: `ai.llm.chat` and `ai.client.chat_structured` are INTERNAL and "
            "set no operation, usage or response keys, so each request is counted once.",
            "- **Gateway slot wait**: A chat call to the LLM gateway first waits in the process "
            "for one of the gateway's backend slots. The wait is an INTERNAL "
            "`ai.llm.gateway_slot` span under the call's `ai.llm.dispatch` or `ai.llm.stream` "
            "span, with `llm.gateway.slots` and `llm.gateway.slot_wait_seconds`, and an "
            "observation of `devops_cli_ai_gateway_slot_wait_seconds`. The call's "
            "`llm.wall_seconds`, its time to first chunk and its spend's duration start once it "
            "holds the slot, so the wait is not counted as inference.",
            "- **Private keys**: Anything the conventions do not define is written under `llm.*`, "
            "such as `llm.request.priority`, `llm.tokens_per_second` and `llm.usage.cost_usd`, "
            "never under `gen_ai.*`.",
            "- **Check**: `tests/test_telemetry_semconv.py` reads every Python file under "
            "`src/devops_cli/`, comments and docstrings included. It fails on a quoted string "
            "starting with `gen_ai.` that is not a current attribute key or metric name in the "
            "snapshot, and on any f-string that builds one.",
            "- **Refresh**: A person moves the pin with "
            "`devops telemetry semconv refresh --commit <sha>`, which needs weaver on PATH and "
            "network access, then fixes what the check reports. The gate never runs weaver.",
            "",
        ]

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
        with trace_span("docs.generate_all", attributes={"output_dir": str(output_dir)}) as span:
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

            # 9. Synced README if README.md exists
            readme_path = self._find_readme()
            if readme_path.exists():
                matrix_table = self.render_readme_matrix(groups)
                synced_readme = self.render_synced_readme(
                    readme_path.read_text(encoding="utf-8"), matrix_table
                )
                if synced_readme is not None:
                    results["README.md"] = synced_readme

            span.set_attributes({"file_count": len(results)})
            return results

    def write_all_docs(
        self,
        output_dir: Path,
        sync_readme_table: bool = True,
        docs: dict[str, str] | None = None,
    ) -> list[Path]:
        """Generate and write all documentation files to disk."""
        with trace_span("docs.write_all", attributes={"output_dir": str(output_dir)}) as span:
            doc_set = docs if docs is not None else self.generate_all_docs(output_dir)
            written: list[Path] = []
            for rel_path, content in doc_set.items():
                if rel_path == "README.md":
                    continue
                dest = output_dir / rel_path
                write_text_file(dest, content)
                written.append(dest)

            if sync_readme_table:
                readme_path = self._find_readme()
                if (docs is None or "README.md" in doc_set) and self.sync_readme(
                    readme_path, docs=doc_set
                ):
                    written.append(readme_path)

            span.set_attributes({"written_count": len(written)})
            return written

    def check_docs(
        self,
        output_dir: Path,
        check_readme_table: bool = True,
        docs: dict[str, str] | None = None,
        check_argv: bool | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify on-disk docs match the generated docs and every devops argv in src and in
        markdown resolves."""
        from devops_cli.docs.markdown_argv_collector import check_documented_argv
        from devops_cli.docs.source_argv_collector import check_source_argv

        doc_set = docs if docs is not None else self.generate_all_docs(output_dir)
        should_check_argv = (docs is None) if check_argv is None else check_argv

        errors: list[str] = []
        if should_check_argv:
            errors.extend(check_source_argv())
            errors.extend(check_documented_argv(self.root_dir))

        for rel_path, expected_content in doc_set.items():
            if rel_path == "README.md":
                continue
            target_path = output_dir / rel_path
            if not target_path.exists():
                errors.append(f"Missing documentation file: {target_path}")
                continue
            actual_content = target_path.read_text(encoding="utf-8")
            if actual_content != expected_content:
                errors.append(
                    f"Out-of-date documentation file: {target_path} differs from generated content."
                )

        if check_readme_table and (docs is None or "README.md" in doc_set):
            readme_ok, readme_err = self.check_readme(docs=doc_set)
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
