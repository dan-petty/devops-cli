"""The path parameters that an MCP tool confines, and the parameters that are no file path.

A tool publishes no option for a path that the command reads or writes, unless the path resolves
under a root that the server sets (SECURITY.md rule 11). The confinement table names each kept
path parameter. The exemption table names each text parameter whose name looks like a path and
that the command does not open, with the reason. The audit in
`tests/ai/mcp/test_path_confinement.py` fails on a published path-like parameter that neither
table names, so a new tool cannot escape the rule in silence.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from devops_cli.core.paths import safe_resolve_subpath
from devops_cli.exceptions import ValidationError
from devops_cli.lang import ERRORS

PATH_CONFINEMENTS: Final[Mapping[str, frozenset[str]]] = {
    "ai_ast_graph": frozenset({"target_dir"}),
    "ai_ast_parse": frozenset({"file_path"}),
    "ai_diagram": frozenset({"target_dir"}),
    "ai_ingest_query_library": frozenset({"contracts_dir"}),
    "ai_pack_context": frozenset({"target_path"}),
    "ai_rag_drift": frozenset({"path"}),
    "ai_rag_index": frozenset({"path"}),
    "ai_read": frozenset({"target_path"}),
    "ai_repomap": frozenset({"target_dir"}),
    "ai_test_gen": frozenset({"target_file"}),
    "branches_list": frozenset({"base_dir"}),
    "docker_sandbox": frozenset({"seccomp_profile"}),
    "gh_labels_sync": frozenset({"file"}),
    "gh_issues_close": frozenset({"comment_file"}),
    "gh_pages_verify": frozenset({"root_dir"}),
    "gh_project_audit": frozenset({"template_file"}),
    "gh_project_status": frozenset({"template_file"}),
    "gh_project_sync": frozenset({"template_file"}),
    "gh_views_audit": frozenset({"template_file"}),
    "gh_views_spec": frozenset({"template_file"}),
    "gh_views_sync": frozenset({"template_file"}),
    "k8s_bootstrap": frozenset({"k8s_dir"}),
    "k8s_deploy_stack": frozenset({"k8s_dir"}),
    "k8s_diff_helm": frozenset({"chart_path"}),
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
    "scan_aibom": frozenset({"target"}),
    "scan_complexity": frozenset({"target"}),
    "scan_fix": frozenset({"target"}),
    "scan_injection": frozenset({"target"}),
    "scan_sast": frozenset({"target"}),
    "scan_sbom": frozenset({"target"}),
    "scan_secrets": frozenset({"target"}),
    "scan_trivy": frozenset({"target"}),
    "scan_uv_audit": frozenset({"directory"}),
    "tf_apply": frozenset({"directory", "plan_file", "var_file"}),
    "tf_cost_breakdown": frozenset({"directory"}),
    "tf_notify_plan": frozenset({"plan_file"}),
    "tf_output": frozenset({"directory"}),
    "tf_plan": frozenset({"directory", "var_file"}),
    "tls_inspect": frozenset({"cert_path"}),
}

NOT_A_FILE_PATH: Final[Mapping[str, Mapping[str, str]]] = {
    "ai_failover": {
        "target_model": "The target model of a fallback route is a model name, not a file.",
        "target_provider": "The target provider of a fallback route is a provider name, not a file.",
    },
    "ai_rag_query": {
        "file_filter": "A file filter is a glob pattern for the search, not a path the server opens.",
    },
    "roadmap_intake": {
        "filed_by": "The filed_by value names the actor that files the candidate, not a file.",
    },
    "sandbox_exec": {
        "workdir": "The workdir is a directory inside the sandbox container, not a host file path.",
    },
    "security_intel_network": {
        "target": "The target is a host name or an IP address for threat intelligence, not a file.",
    },
    "vault_get": {
        "path": "A Vault secret path selects a secret from Vault, and the server opens no file.",
    },
    "vault_sync": {
        "path": "A Vault secret path selects a secret from Vault, and the server opens no file.",
    },
}


def _check(parameter: str, value: Any, root: Path) -> None:
    if not isinstance(value, (str, Path)):
        return
    try:
        safe_resolve_subpath(root, value, error_cls=ValidationError)
    except ValidationError as exc:
        raise ValidationError(
            ERRORS.mcp.path_outside_root.format(name=parameter, root=root),
            field=parameter,
        ) from exc


def confine_tool_paths(tool_name: str, arguments: dict[str, Any]) -> None:
    """Check that each kept path argument resolves under the work tree."""
    parameters = PATH_CONFINEMENTS.get(tool_name)
    if not parameters:
        return
    root = Path.cwd().resolve()
    for parameter in parameters:
        value = arguments.get(parameter)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            for item in value:
                _check(parameter, item, root)
        else:
            _check(parameter, value, root)
