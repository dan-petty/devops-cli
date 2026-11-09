"""The failure taxonomy and runner capabilities in staging context (#3258).

Derives failure classes, action rules, runner image tools, NOT_IN_RUNNER entries, and pod
security settings from repository files at the staged commit.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable
from typing import Any, Final

import yaml

from devops_cli.exceptions import RoadmapStageError

FAILURE_TAXONOMY_PATH: Final[str] = "src/devops_cli/roadmap/failure.py"
RUNNER_TOOLS_PATH: Final[str] = "src/devops_cli/roadmap/runner_tools.py"
RUNNER_DOCKERFILE_PATH: Final[str] = "Dockerfile"
RUNNER_POD_MANIFEST_PATH: Final[str] = "k8s/devops/cronjob-runner.yaml"

_FAILURE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:retry|retries|review|reviews|stop|stops|tier|tiers|failure|failures)\b",
    re.IGNORECASE,
)

_TOOL_OR_COMMAND_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:"
    r"devops|kubectl|kustomize|helm|argo|argocd|cloudflared|kubectl-argo-rollouts|k9s|minikube|"
    r"docker|kube-linter|popeye|pluto|kubeconform|tflint|gitleaks|osv-scanner|golangci-lint|"
    r"semgrep|actionlint|shellcheck|bwrap|trivy|uv|python|python3|gh|node|openspec|pytest|ruff|"
    r"mypy|bandit|deptry|ast-grep|zizmor|pre-commit|curl|jq|promtool"
    r")\b",
    re.IGNORECASE,
)


def should_include_failure_taxonomy(text: str) -> bool:
    """Whether the issue or plan text cites retry, review, stop, tier or failure."""
    return bool(_FAILURE_PATTERN.search(text))


def should_include_runner_capabilities(text: str) -> bool:
    """Whether the issue or plan text cites a command or tool name."""
    return bool(_TOOL_OR_COMMAND_PATTERN.search(text))


def _extract_failure_classes(tree: ast.Module) -> list[str]:
    classes: list[str] = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == "FailureClass"):
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name):
                    classes.append(target.id.lower())
    return classes


def _extract_action_by_class(tree: ast.Module) -> list[tuple[str, str]]:
    actions: list[tuple[str, str]] = []
    for node in tree.body:
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
            continue
        if node.target.id != "ACTION_BY_CLASS" or not (
            isinstance(node.value, ast.Call) and node.value.args
        ):
            continue
        arg = node.value.args[0]
        if not isinstance(arg, ast.Dict):
            continue
        for k, v in zip(arg.keys, arg.values, strict=False):
            k_name = k.attr.lower() if isinstance(k, ast.Attribute) else ""
            v_name = v.attr.lower() if isinstance(v, ast.Attribute) else ""
            if k_name and v_name:
                actions.append((k_name, v_name))
    return actions


def _extract_failure_taxonomy(source_text: str) -> str:
    """Extract FailureClass values and ACTION_BY_CLASS from failure.py source."""
    tree = ast.parse(source_text)
    classes = _extract_failure_classes(tree)
    actions = _extract_action_by_class(tree)

    class_lines = [f"- `{cls_name}`" for cls_name in classes]
    action_lines = [f"- `{cls_name}`: `{action}`" for cls_name, action in actions]

    return (
        "### Failure taxonomy\n\n"
        "#### Failure classes\n"
        + "\n".join(class_lines)
        + "\n\n#### Action by class\n"
        + "\n".join(action_lines)
    )


def build_failure_taxonomy_context(read_file: Callable[[str], str | None]) -> str:
    """Build the failure taxonomy section read from failure.py at the staged commit."""
    content = read_file(FAILURE_TAXONOMY_PATH)
    if content is None:
        raise RoadmapStageError(f"Staged source moved or missing: {FAILURE_TAXONOMY_PATH}")
    return _extract_failure_taxonomy(content)


def _extract_runner_tools_list(node: ast.AST) -> list[str]:
    if not (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "RUNNER_TOOLS"
        and isinstance(node.value, ast.Tuple)
    ):
        return []
    tools: list[str] = []
    for elt in node.value.elts:
        if isinstance(elt, ast.Call) and elt.args:
            arg = elt.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                tools.append(arg.value)
    return tools


def _extract_dict_exclusions(dict_node: ast.Dict) -> dict[str, str]:
    exclusions: dict[str, str] = {}
    for k, v in zip(dict_node.keys, dict_node.values, strict=False):
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
            continue
        if isinstance(v, ast.Constant) and isinstance(v.value, str):
            exclusions[k.value] = v.value
        elif isinstance(v, ast.Name):
            exclusions[k.value] = v.id
        elif isinstance(v, ast.Call):
            exclusions[k.value] = "exclusion rule"
        else:
            exclusions[k.value] = ""
    return exclusions


def _extract_runner_tools(source_text: str) -> tuple[list[str], dict[str, str]]:
    """Extract tool names and NOT_IN_RUNNER exclusions from runner_tools.py."""
    tree = ast.parse(source_text)
    tools: list[str] = []
    not_in_runner: dict[str, str] = {}

    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "RUNNER_TOOLS":
                tools.extend(_extract_runner_tools_list(node))
            elif node.target.id == "NOT_IN_RUNNER" and isinstance(node.value, ast.Dict):
                not_in_runner.update(_extract_dict_exclusions(node.value))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "NOT_IN_RUNNER"
                    and isinstance(node.value, ast.Dict)
                ):
                    not_in_runner.update(_extract_dict_exclusions(node.value))

    return tools, not_in_runner


def _extract_dockerfile_tools(dockerfile_text: str) -> list[str]:
    """Extract apt installed tools from the runner stage of Dockerfile."""
    packages: list[str] = []
    in_runner = False
    standard_pkgs = ("git", "ca-certificates", "curl", "jq")
    for line in dockerfile_text.splitlines():
        if line.startswith("FROM ") and " AS runner" in line:
            in_runner = True
            continue
        if not in_runner:
            continue
        if line.startswith("FROM "):
            break
        if "apt-get install" in line:
            for part in line.split():
                if part in standard_pkgs:
                    packages.append(part)
    return packages or list(standard_pkgs)


def _extract_pod_security(manifest_text: str) -> dict[str, Any]:
    """Extract pod and container security settings from cronjob-runner.yaml."""
    data = yaml.safe_load(manifest_text)
    settings: dict[str, Any] = {}
    try:
        pod_spec = data["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        pod_sec = pod_spec.get("securityContext", {})
        if "seccompProfile" in pod_sec:
            settings["seccompProfile"] = pod_sec["seccompProfile"].get("type", "RuntimeDefault")
        if "runAsNonRoot" in pod_sec:
            settings["runAsNonRoot"] = str(pod_sec["runAsNonRoot"]).lower()

        containers = pod_spec.get("containers", [])
        if containers:
            c_sec = containers[0].get("securityContext", {})
            if "allowPrivilegeEscalation" in c_sec:
                settings["allowPrivilegeEscalation"] = str(
                    c_sec["allowPrivilegeEscalation"]
                ).lower()
            if "readOnlyRootFilesystem" in c_sec:
                settings["readOnlyRootFilesystem"] = str(c_sec["readOnlyRootFilesystem"]).lower()
            if "capabilities" in c_sec and "drop" in c_sec["capabilities"]:
                settings["capabilities.drop"] = ", ".join(c_sec["capabilities"]["drop"])
    except KeyError, TypeError:
        pass
    return settings


def build_runner_capabilities_context(read_file: Callable[[str], str | None]) -> str:
    """Build the runner capabilities section read from repo files at the staged commit."""
    tools_content = read_file(RUNNER_TOOLS_PATH)
    if tools_content is None:
        raise RoadmapStageError(f"Staged source moved or missing: {RUNNER_TOOLS_PATH}")

    dockerfile_content = read_file(RUNNER_DOCKERFILE_PATH)
    if dockerfile_content is None:
        raise RoadmapStageError(f"Staged source moved or missing: {RUNNER_DOCKERFILE_PATH}")

    manifest_content = read_file(RUNNER_POD_MANIFEST_PATH)
    if manifest_content is None:
        raise RoadmapStageError(f"Staged source moved or missing: {RUNNER_POD_MANIFEST_PATH}")

    tools, not_in_runner = _extract_runner_tools(tools_content)
    pkg_list = _extract_dockerfile_tools(dockerfile_content)
    pod_sec = _extract_pod_security(manifest_content)

    tools_line = ", ".join(f"`{t}`" for t in tools)
    pkg_line = ", ".join(f"`{p}`" for p in pkg_list)
    not_in_runner_lines = [
        f"- `{prog}`: {reason}" if reason else f"- `{prog}`"
        for prog, reason in sorted(not_in_runner.items())
    ]
    sec_lines = [f"- `{k}`: `{v}`" for k, v in sorted(pod_sec.items())]

    return (
        "### Runner capabilities\n\n"
        "#### Image tools\n"
        f"- Installed packages: {pkg_line}\n"
        f"- Runner tools: {tools_line}\n\n"
        "#### Excluded tools (NOT_IN_RUNNER)\n"
        + "\n".join(not_in_runner_lines)
        + "\n\n#### Pod security settings\n"
        + "\n".join(sec_lines)
    )


def collect_stage_facts_context(
    text: str,
    read_file: Callable[[str], str | None],
) -> str:
    """Collect failure taxonomy and runner capabilities context sections when triggered."""
    sections: list[str] = []
    if should_include_failure_taxonomy(text):
        sections.append(build_failure_taxonomy_context(read_file))
    if should_include_runner_capabilities(text):
        sections.append(build_runner_capabilities_context(read_file))
    return "\n\n".join(sections)
