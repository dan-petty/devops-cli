"""The failure taxonomy and runner capabilities in staging context (#3258).

The failure classes, the action rules, the runner tools and `NOT_IN_RUNNER` come from the installed
modules: they describe the runner image, and the runner image is the devops-cli image for every
repository (#4628). The Dockerfile packages and the pod security settings come from the staged
commit, and only when that commit holds `runner_tools.py`, because only a devops-cli commit
describes the runner image.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Final

import yaml

from devops_cli.roadmap.failure import ACTION_BY_CLASS, FailureClass
from devops_cli.roadmap.runner_tools import NOT_IN_RUNNER, tool_names

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


def build_failure_taxonomy_context() -> str:
    """Build the failure taxonomy section from the installed `failure` module."""
    class_lines = [f"- `{failure_class}`" for failure_class in FailureClass]
    action_lines = [f"- `{cls}`: `{action}`" for cls, action in ACTION_BY_CLASS.items()]
    return (
        "### Failure taxonomy\n\n"
        "#### Failure classes\n"
        + "\n".join(class_lines)
        + "\n\n#### Action by class\n"
        + "\n".join(action_lines)
    )


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


def _image_facts(read_file: Callable[[str], str | None]) -> tuple[str, str]:
    """The packages line and the pod security subsection of a devops-cli commit. Each is empty
    when the commit lacks `runner_tools.py` or the file of the fact."""
    if read_file(RUNNER_TOOLS_PATH) is None:
        return "", ""
    packages = ""
    dockerfile = read_file(RUNNER_DOCKERFILE_PATH)
    if dockerfile is not None:
        pkg_line = ", ".join(f"`{p}`" for p in _extract_dockerfile_tools(dockerfile))
        packages = f"- Installed packages: {pkg_line}\n"
    security = ""
    manifest = read_file(RUNNER_POD_MANIFEST_PATH)
    if manifest is not None:
        sec_lines = [f"- `{k}`: `{v}`" for k, v in sorted(_extract_pod_security(manifest).items())]
        security = "\n\n#### Pod security settings\n" + "\n".join(sec_lines)
    return packages, security


def build_runner_capabilities_context(read_file: Callable[[str], str | None]) -> str:
    """Build the runner capabilities section: the runner tools and `NOT_IN_RUNNER` of the installed
    module, and the image facts of a devops-cli commit."""
    packages, security = _image_facts(read_file)
    tools_line = ", ".join(f"`{t}`" for t in tool_names())
    not_in_runner_lines = [
        f"- `{prog}`: {reason}" for prog, reason in sorted(NOT_IN_RUNNER.items())
    ]
    return (
        "### Runner capabilities\n\n"
        "#### Image tools\n"
        f"{packages}"
        f"- Runner tools: {tools_line}\n\n"
        "#### Excluded tools (NOT_IN_RUNNER)\n" + "\n".join(not_in_runner_lines) + security
    )


def collect_stage_facts_context(
    text: str,
    read_file: Callable[[str], str | None],
) -> str:
    """Collect failure taxonomy and runner capabilities context sections when triggered."""
    sections: list[str] = []
    if should_include_failure_taxonomy(text):
        sections.append(build_failure_taxonomy_context())
    if should_include_runner_capabilities(text):
        sections.append(build_runner_capabilities_context(read_file))
    return "\n\n".join(sections)
