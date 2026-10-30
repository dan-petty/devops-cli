"""Dynamic FastMCP tool generation from Typer/Click CLI command metadata."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from enum import Enum
from functools import cache
from pathlib import Path, PurePath
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from pydantic import Field

from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.command_resolver import module_click_command
from devops_cli.docs.generator import _clean_text
from devops_cli.main import _COMMAND_SPECS

_IGNORED_PARAM_NAMES: frozenset[str] = frozenset({"help", "install_completion", "show_completion"})
_JSON_PARAM_NAMES: frozenset[str] = frozenset({"format", "output_format", "json"})
_INTEGER_ID_PARAM_NAMES: frozenset[str] = frozenset(
    {"number", "pr_number", "issue_number", "run_id"}
)
# The options of a command that its MCP tool publishes. A command lists an option here when the
# other options are for a person at the command line. A URL option is input from the model that
# calls the tool, so the tool does not publish it. The tool queries the service that the
# configuration names.
_PATH_PARAM_RESTRICTIONS: dict[tuple[str, ...], dict[str, Any]] = {
    ("telemetry", "profile"): {
        "allowed": frozenset({"trace_id"}),
        "required": frozenset({"trace_id"}),
    },
    ("valkey", "ping"): {"allowed": frozenset(), "required": frozenset()},
    ("valkey", "stats"): {"allowed": frozenset(), "required": frozenset()},
    ("valkey", "info"): {"allowed": frozenset({"section"}), "required": frozenset()},
    ("valkey", "get"): {"allowed": frozenset({"key"}), "required": frozenset()},
    ("valkey", "set"): {
        "allowed": frozenset({"key", "value", "ex", "dry_run"}),
        "required": frozenset(),
    },
    ("valkey", "flush"): {
        "allowed": frozenset({"all_databases", "dry_run"}),
        "required": frozenset(),
    },
    ("ai", "prewarm"): {
        "allowed": frozenset(
            {"model", "keep_alive", "all_nodes", "evict", "output_format", "json_output"}
        ),
        "required": frozenset(),
    },
    # No `output`, `document` or `code`: a path that the model chose would make the command write
    # a file or read one (#2704). The tool prints its report and ranks the built-in corpus.
    ("ai", "benchmark"): {
        "allowed": frozenset(
            {
                "models",
                "provider",
                "benchmark_type",
                "tasks_filter",
                "concurrency",
                "format_type",
                "dry_run",
                "explain",
                "samples",
            }
        ),
        "required": frozenset(),
    },
    ("ai", "gateway", "status"): {"allowed": frozenset({"provider"}), "required": frozenset()},
    ("ai", "gateway", "routes"): {"allowed": frozenset({"provider"}), "required": frozenset()},
    ("ai", "gateway", "probe-backend"): {
        "allowed": frozenset({"backend"}),
        "required": frozenset(),
    },
    ("k8s", "logs"): {
        "allowed": frozenset(
            {
                "pod",
                "query_arg",
                "query",
                "container",
                "namespace",
                "follow",
                "tail",
                "limit",
                "since",
                "dry_run",
            }
        ),
        "required": frozenset(),
    },
    ("vault", "status"): {"allowed": frozenset({"dry_run"}), "required": frozenset()},
}


@cache
def resolve_click_command(path: tuple[str, ...]) -> Any:
    """Resolve Click command object corresponding to a command path tuple."""
    top_name = path[0]
    spec = _COMMAND_SPECS.get(top_name)
    if not spec:
        raise LookupError(f"Unknown root command '{top_name}'")
    top_cmd = module_click_command(spec[0])
    if top_cmd is None:
        raise LookupError(f"Could not load module for '{top_name}'")
    curr = top_cmd
    curr_name = top_name
    for seg in path[1:]:
        if not hasattr(curr, "resolve_command"):
            raise LookupError(f"Command '{curr_name}' has no subcommands")
        ctx = curr.make_context(curr_name, [seg], resilient_parsing=True)
        sub_name, sub_cmd, _ = curr.resolve_command(ctx, [seg])
        if sub_cmd is None:
            raise LookupError(f"Unknown subcommand '{seg}' under '{curr_name}'")
        curr = sub_cmd
        curr_name = sub_name
    return curr


def reset_click_command_cache() -> None:
    """Clear the cached Click command resolutions."""
    resolve_click_command.cache_clear()


def _is_sequence_param(param: Any) -> bool:
    """Determine whether parameter accepts multiple values."""
    return bool(getattr(param, "multiple", False) or getattr(param, "nargs", 1) != 1)


def _deduce_parameter_type(param: Any) -> Any:
    """Map Click parameter type to appropriate Python type annotation."""
    type_name = type(param.type).__name__
    if "Choice" in type_name or hasattr(param.type, "choices"):
        choices = tuple(param.type.choices)
        py_type: Any = Literal.__getitem__(choices)
    elif "Bool" in type_name or getattr(param, "is_flag", False):
        py_type = bool
    elif "Int" in type_name:
        py_type = int
    elif "Float" in type_name:
        py_type = float
    else:
        py_type = str

    if _is_sequence_param(param):
        return list[py_type]
    return py_type


def _normalize_default(default_val: Any) -> Any:
    """Convert default values into primitive JSON-serializable types.

    Absolute paths or paths within user home are sanitized to empty strings to avoid
    environment-dependent schema leakage and maintain deterministic documentation.
    """
    if default_val is None:
        return None
    if isinstance(default_val, (Path, PurePath)):
        return "" if default_val.is_absolute() else str(default_val)
    if isinstance(default_val, Enum):
        return default_val.value
    return default_val


def _build_parameter_field(param: Any, default_val: Any, is_required: bool = False) -> Any:
    """Construct Pydantic Field instance for Click parameter."""
    field_kwargs: dict[str, Any] = {
        "description": _clean_text(getattr(param, "help", None) or ""),
    }
    type_name = type(param.type).__name__
    is_seq = _is_sequence_param(param)
    if not is_seq:
        if "IntRange" in type_name or hasattr(param.type, "min") or hasattr(param.type, "max"):
            if getattr(param.type, "min", None) is not None:
                field_kwargs["ge"] = param.type.min
            if getattr(param.type, "max", None) is not None:
                field_kwargs["le"] = param.type.max
        if param.name in _INTEGER_ID_PARAM_NAMES and "ge" not in field_kwargs:
            field_kwargs["ge"] = 1
            field_kwargs["strict"] = True
    if not is_required:
        field_kwargs["default"] = default_val
    return Field(**field_kwargs)


def _introspect_command_parameters(
    click_cmd: Any, format_json: bool, path: tuple[str, ...] = ()
) -> tuple[list[inspect.Parameter], dict[str, Any]]:
    """Generate inspect.Parameter list and typing annotations for a Click command."""
    parameters: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    restrictions = _PATH_PARAM_RESTRICTIONS.get(path)
    for p in click_cmd.params:
        if p.name in _IGNORED_PARAM_NAMES:
            continue
        if format_json and p.name in _JSON_PARAM_NAMES:
            continue
        if restrictions and p.name not in restrictions["allowed"]:
            continue
        py_type = _deduce_parameter_type(p)
        default_val = _normalize_default(getattr(p, "default", None))
        is_required = bool(p.required or (restrictions and p.name in restrictions["required"]))
        field = _build_parameter_field(p, default_val, is_required)
        ann: Any
        if is_required:
            param_default = inspect.Parameter.empty
            ann = Annotated.__getitem__((py_type, field))
        else:
            param_default = default_val
            ann_type = py_type if default_val is not None else py_type | None
            ann = Annotated.__getitem__((ann_type, field))
        annotations[p.name] = ann
        parameters.append(
            inspect.Parameter(
                p.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=param_default,
                annotation=ann,
            )
        )
    annotations["return"] = str
    return parameters, annotations


def _append_argument_tokens(argv: list[str], param: Any, val: Any) -> None:
    """Append positional argument values to CLI token list."""
    if isinstance(val, (list, tuple)):
        argv.extend(str(v) for v in val)
    elif str(val) != "" or param.required:
        argv.append(str(val))


def _append_option_tokens(argv: list[str], param: Any, val: Any) -> None:
    """Append option flag and values to CLI token list."""
    flag = param.opts[0]
    type_name = type(param.type).__name__
    if "Bool" in type_name or getattr(param, "is_flag", False):
        if val is True:
            argv.append(flag)
        elif val is False and getattr(param, "secondary_opts", None):
            argv.append(param.secondary_opts[0])
    elif getattr(param, "multiple", False):
        if isinstance(val, (list, tuple)):
            for v in val:
                argv.extend([flag, str(v)])
    else:
        if str(val) != "" or param.required:
            argv.extend([flag, str(val)])


def _validate_arg_hyphen(name: str, value: Any) -> None:
    """Reject tool argument values starting with a hyphen to prevent CLI flag injection."""
    if isinstance(value, str) and value.startswith("-"):
        from devops_cli.exceptions import ValidationError
        from devops_cli.lang import ERRORS

        raise ValidationError(
            ERRORS.mcp.hyphen_prefixed_argument.format(name=name),
            field=name,
        )
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_arg_hyphen(name, item)


def _validate_all_args(kwargs: dict[str, Any]) -> None:
    """Validate that kwargs values do not contain hyphen-prefixed strings."""
    for k, v in kwargs.items():
        if k != "command" and v is not None:
            _validate_arg_hyphen(k, v)


def _validate_mcp_sandbox_workspace(workspace: str) -> None:
    """Refuse a sandbox workspace through the commands' shared check before any command runs."""
    from devops_cli.config.settings import load_settings
    from devops_cli.sandbox.engine import validate_sandbox_workspace

    exclude_home_dir = load_settings().sandbox.exclude_home_dir
    validate_sandbox_workspace(Path(workspace), exclude_home_dir=exclude_home_dir)


def _check_sandbox_preconditions(path: tuple[str, ...], kwargs: dict[str, Any]) -> None:
    """Run sandbox workspace validation before command dispatch if required."""
    if path in {("docker", "sandbox"), ("sandbox", "deploy")} and (ws := kwargs.get("workspace")):
        _validate_mcp_sandbox_workspace(str(ws))


def _check_model_endpoints(path: tuple[str, ...], kwargs: dict[str, Any]) -> None:
    """Refuse a `model@url` entry of the benchmark tool before any command runs.

    The command reads `model@url` as the server that gets that model's requests. A person types it.
    A model that calls the tool must not choose a server, so the tool takes model names only (#2638).
    """
    if path != ("ai", "benchmark") or not (models := kwargs.get("models")):
        return
    from devops_cli.ai.benchmark.model_spec import parse_model_list, parse_model_spec
    from devops_cli.exceptions import ValidationError
    from devops_cli.lang import ERRORS

    if any(parse_model_spec(entry)[1] is not None for entry in parse_model_list(str(models))):
        raise ValidationError(ERRORS.mcp.model_names_endpoint, field="models")


def _extract_extra_env(path: tuple[str, ...], kwargs: dict[str, Any]) -> dict[str, str] | None:
    """Extract environment variables for sensitive parameters passed out-of-band."""
    if path == ("docker", "sign") and (token := kwargs.get("oidc_token")):
        token_str = str(token)
        if not token_str.startswith("keyring:"):
            return {"COSIGN_IDENTITY_TOKEN": token_str}
    return None


def _should_skip_option(path: tuple[str, ...], param_name: str, kwargs: dict[str, Any]) -> bool:
    """Determine whether an option should be skipped from CLI argv."""
    if path == ("docker", "sign") and param_name == "oidc_token":
        val = kwargs.get("oidc_token")
        return bool(val is not None and not str(val).startswith("keyring:"))
    return False


def _append_options(
    argv: list[str],
    opts: list[Any],
    format_json: bool,
    kwargs: dict[str, Any],
    path: tuple[str, ...] = (),
) -> None:
    """Append option flags and values to argv."""
    for p in opts:
        if p.name in _IGNORED_PARAM_NAMES or _should_skip_option(path, p.name, kwargs):
            continue
        if format_json and p.name in _JSON_PARAM_NAMES:
            continue
        if p.name in kwargs and kwargs[p.name] is not None:
            _append_option_tokens(argv, p, kwargs[p.name])


def _append_format_flags(argv: list[str], click_cmd: Any) -> None:
    """Append format json flag based on command's accepted format flags."""
    all_opts = [opt for p in click_cmd.params for opt in getattr(p, "opts", [])]
    if "--format" in all_opts:
        argv.extend(["--format", "json"])
    elif "--json" in all_opts:
        argv.append("--json")


def _append_command_tokens(argv: list[str], val: Any) -> None:
    """Append trailing command tokens separated by option terminator."""
    argv.append("--")
    if isinstance(val, (list, tuple)):
        argv.extend(str(v) for v in val)
    else:
        argv.append(str(val))


def _build_command_argv(
    path: tuple[str, ...],
    click_cmd: Any,
    format_json: bool,
    kwargs: dict[str, Any],
) -> list[str]:
    """Translate tool keyword arguments into CLI argv tokens."""
    _validate_all_args(kwargs)
    argv: list[str] = list(path)
    params = list(click_cmd.params)
    args = [p for p in params if not any(opt.startswith("-") for opt in getattr(p, "opts", []))]
    opts = [p for p in params if any(opt.startswith("-") for opt in getattr(p, "opts", []))]

    regular_args = [p for p in args if p.name != "command"]
    for p in regular_args:
        if p.name in kwargs and kwargs[p.name] is not None:
            _append_argument_tokens(argv, p, kwargs[p.name])

    _append_options(argv, opts, format_json, kwargs, path)

    command_param = next((p for p in args if p.name == "command"), None)
    if command_param and command_param.name in kwargs and kwargs[command_param.name] is not None:
        _append_command_tokens(argv, kwargs[command_param.name])

    if format_json:
        _append_format_flags(argv, click_cmd)

    return argv


def _create_tool_function(
    path: tuple[str, ...],
    timeout: float,
    format_json: bool,
    tool_name: str,
    click_cmd: Any,
) -> Callable[..., str]:
    """Create executable FastMCP tool function with signature and docstring metadata."""
    parameters, annotations = _introspect_command_parameters(click_cmd, format_json, path)
    sig = inspect.Signature(parameters=parameters, return_annotation=str)

    def tool_fn(*args: Any, **kwargs: Any) -> str:
        from devops_cli.ai.mcp.server import _run_mcp_cmd

        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        _check_sandbox_preconditions(path, bound.arguments)
        _check_model_endpoints(path, bound.arguments)
        argv = _build_command_argv(path, click_cmd, format_json, bound.arguments)
        extra_env = _extract_extra_env(path, bound.arguments)
        if extra_env is not None:
            return _run_mcp_cmd(["uv", "run", "devops", *argv], timeout=timeout, env=extra_env)
        return _run_mcp_cmd(["uv", "run", "devops", *argv], timeout=timeout)

    tool_fn.__name__ = tool_name
    doc_source = click_cmd.help or click_cmd.short_help or f"Execute devops {' '.join(path)}"
    tool_fn.__doc__ = _clean_text(doc_source)
    setattr(tool_fn, "__signature__", sig)
    setattr(tool_fn, "__annotations__", annotations)
    return tool_fn


def generate_mcp_tools(server: FastMCP) -> dict[str, Callable[..., str]]:
    """Register all exposed CLI commands as FastMCP tools onto the server."""
    generated: dict[str, Callable[..., str]] = {}
    for path, timeout, read_only, format_json in CONST_MCP_EXPOSURE_TABLE:
        tool_name = "_".join(path).replace("-", "_")
        click_cmd = resolve_click_command(path)
        tool_fn = _create_tool_function(path, timeout, format_json, tool_name, click_cmd)
        server.tool(
            name=tool_name,
            description=tool_fn.__doc__,
            annotations={"readOnlyHint": read_only},
        )(tool_fn)
        generated[tool_name] = tool_fn
    return generated
