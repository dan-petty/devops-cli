"""The path parameters of the MCP tools: which ones the guard confines, and which are no file.

`PATH_CONFINEMENTS` names the path parameters that `_check_path_confinement` resolves under the
work tree of the server process, so a model that calls a tool reaches no path outside it.
`NOT_A_FILE_PATH` names a parameter whose name holds a path keyword and whose value is no
filesystem path, with the reason. `audit_path_parameters` fails on an unconfined parameter, a
reason shorter than `MIN_NOT_A_FILE_REASON` and an entry that matches no published parameter.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final

from devops_cli.core.paths import _PATH_PARAM_KEYWORDS

MIN_NOT_A_FILE_REASON: Final[int] = 30

PATH_CONFINEMENTS: Final[dict[str, frozenset[str]]] = {
    "ai_ast_graph": frozenset({"target_dir"}),
    "ai_ast_parse": frozenset({"file_path"}),
    "ai_diagram": frozenset({"target_dir"}),
    "ai_ingest_library": frozenset({"output_dir"}),
    "ai_ingest_query_library": frozenset({"contracts_dir"}),
    "ai_pack_context": frozenset({"target_path"}),
    "ai_rag_drift": frozenset({"path"}),
    "ai_rag_index": frozenset({"path"}),
    "ai_read": frozenset({"target_path"}),
    "ai_repomap": frozenset({"target_dir"}),
    "ai_test_gen": frozenset({"target_file"}),
    "branches_list": frozenset({"base_dir"}),
    "docker_sandbox": frozenset({"seccomp_profile"}),
    "gh_issues_close": frozenset({"comment_file"}),
    "gh_labels_sync": frozenset({"file"}),
    "gh_pages_verify": frozenset({"root_dir"}),
    "gh_project_audit": frozenset({"template_file"}),
    "gh_project_status": frozenset({"template_file"}),
    "gh_project_sync": frozenset({"template_file"}),
    "gh_views_audit": frozenset({"template_file"}),
    "gh_views_spec": frozenset({"template_file"}),
    "gh_views_sync": frozenset({"template_file"}),
    "k8s_bootstrap": frozenset({"k8s_dir"}),
    "k8s_create_tls_secret": frozenset({"cert_path", "key_path"}),
    "k8s_deploy_stack": frozenset({"k8s_dir"}),
    "k8s_diff_helm": frozenset({"chart_path"}),
    "k8s_enable_tls": frozenset({"tls_dir"}),
    "k8s_lint": frozenset({"target"}),
    "k8s_teardown_stack": frozenset({"k8s_dir"}),
    "k8s_validate": frozenset({"manifest_path"}),
    "repos_list": frozenset({"base_dir"}),
    "repos_sync": frozenset({"base_dir"}),
    "review_branch": frozenset({"repo_path"}),
    "review_export_feedback": frozenset({"reviews_dir"}),
    "review_path": frozenset({"targets"}),
    "review_stats": frozenset({"reviews_dir"}),
    "roadmap_intake": frozenset({"body_file"}),
    "sandbox_deploy": frozenset({"seccomp_profile"}),
    "sandbox_exec": frozenset({"workdir"}),
    "scan_aibom": frozenset({"output_file", "target"}),
    "scan_complexity": frozenset({"target"}),
    "scan_fix": frozenset({"target"}),
    "scan_injection": frozenset({"target"}),
    "scan_sast": frozenset({"target"}),
    "scan_sbom": frozenset({"output_file", "target"}),
    "scan_secrets": frozenset({"target"}),
    "scan_trivy": frozenset({"target"}),
    "scan_uv_audit": frozenset({"directory"}),
    "ssh_audit": frozenset({"key_dir"}),
    "ssh_status": frozenset({"key_dir"}),
    "tf_apply": frozenset({"directory", "plan_file", "var_file"}),
    "tf_cost_breakdown": frozenset({"directory"}),
    "tf_notify_plan": frozenset({"plan_file"}),
    "tf_output": frozenset({"directory"}),
    "tf_plan": frozenset({"directory", "var_file"}),
    "tls_inspect": frozenset({"cert_path"}),
}

NOT_A_FILE_PATH: Final[dict[str, dict[str, str]]] = {
    "ai_ast_graph": {
        "max_files": "The value is a count of files, not a path that the command opens.",
    },
    "ai_failover": {
        "target_provider": "The value names an AI provider, not a path that the command opens.",
        "target_model": "The value names an AI model, not a path that the command opens.",
    },
    "ai_rag_query": {
        "file_filter": "The value is a glob that filters indexed paths, not a file opened on disk.",
    },
    "ai_repomap": {
        "max_files": "The value is a count of files, not a path that the command opens.",
    },
    "security_intel_network": {
        "target": "The value is a host name or an address, not a path that the tool opens.",
    },
    "roadmap_intake": {
        "filed_by": "The value names who files the issue, an enum, not a filesystem path.",
    },
    "tf_plan": {
        "destroy": "The value is a boolean flag; the keyword 'dest' matches its name by substring.",
    },
    "vault_get": {
        "path": "The value selects a Vault secret by its secret path; no filesystem file is opened.",
    },
    "vault_sync": {
        "path": "The value selects a Vault secret by its secret path; no filesystem file is opened.",
    },
}


def confinement_root() -> Path:
    """The work tree of the server process, never a value that a tool argument carries."""
    from devops_cli.core.repo import find_worktree_root

    return find_worktree_root(Path.cwd())


def confine_value(root: Path, name: str, value: Any) -> Any:
    """Resolve one path argument under `root`, and refuse an escape with a named error."""
    if isinstance(value, (list, tuple)):
        return [confine_value(root, name, item) for item in value]
    if not isinstance(value, (str, Path)):
        return value
    from devops_cli.core.paths import safe_resolve_subpath
    from devops_cli.exceptions import ValidationError
    from devops_cli.lang import ERRORS

    try:
        resolved = safe_resolve_subpath(root, str(value), error_cls=ValidationError)
    except ValidationError as exc:
        raise ValidationError(
            ERRORS.mcp.path_outside_work_tree.format(name=name, root=root), field=name
        ) from exc
    return str(resolved)


def _path_like_names(tool: Any) -> set[str]:
    properties = getattr(tool, "parameters", {}).get("properties", {})
    return {
        name
        for name in properties
        if any(keyword in name.lower() for keyword in _PATH_PARAM_KEYWORDS)
    }


def audit_path_parameters(tools: Iterable[Any]) -> list[str]:
    """Return one problem for each path parameter that no entry confines or explains."""
    published: dict[str, set[str]] = {
        tool.name: _path_like_names(tool) for tool in tools if _path_like_names(tool)
    }
    problems: list[str] = []
    for tool_name, names in published.items():
        confined = PATH_CONFINEMENTS.get(tool_name, frozenset())
        reasons = NOT_A_FILE_PATH.get(tool_name, {})
        for name in sorted(names):
            if name in confined:
                continue
            reason = reasons.get(name)
            if reason is None:
                problems.append(
                    f"{tool_name}.{name} is a path-like parameter with no confinement or reason."
                )
            elif len(reason.strip()) < MIN_NOT_A_FILE_REASON:
                problems.append(
                    f"{tool_name}.{name} has a reason shorter than {MIN_NOT_A_FILE_REASON} characters."
                )
    for tool_name, confined_names in PATH_CONFINEMENTS.items():
        stale = sorted(confined_names - published.get(tool_name, set()))
        problems.extend(
            f"{tool_name}.{name} is confined but is not a published path." for name in stale
        )
    for tool_name, reasons in NOT_A_FILE_PATH.items():
        stale = sorted(reasons.keys() - published.get(tool_name, set()))
        problems.extend(
            f"{tool_name}.{name} is exempt but is not a published path." for name in stale
        )
    return problems
