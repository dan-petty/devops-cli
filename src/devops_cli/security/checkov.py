"""Checkov IaC Static Policy and Security Compliance Scanner.

Integrates with Checkov CLI to perform static compliance audits across
Terraform, CloudFormation, Kubernetes, and Dockerfile manifests.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, ClassVar, TypeGuard

import yaml
from yaml.constructor import SafeConstructor

from devops_cli.ai.review_schema import Finding
from devops_cli.config.constants import (
    CONST_DOCKER_DEFAULT_TAG,
    CONST_DOCKERFILE_ESCAPE_CHARACTERS,
    CONST_DOCKERFILE_ESCAPE_DIRECTIVE,
    CONST_DOCKERFILE_FROM_RE,
    CONST_DOCKERFILE_HEREDOC_INSTRUCTIONS,
    CONST_DOCKERFILE_HEREDOC_RE,
    CONST_DOCKERFILE_ONBUILD_INSTRUCTION,
    CONST_DOCKERFILE_PARSER_DIRECTIVE_RE,
    CONST_DOCKERFILE_SCRATCH_IMAGE,
    CONST_DOCKERFILE_USER_RE,
    CONST_DOCKERFILE_VARIABLE_RE,
    CONST_K8S_NESTED_RESOURCE_KEYS,
    CONST_K8S_POD_CONTAINER_KEYS,
    CONST_K8S_POD_SPEC_PATHS,
    CONST_K8S_PRIVILEGED_LINE_RE,
    CONST_YAML_BOOL_TAG,
)
from devops_cli.config.defaults import DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS
from devops_cli.core.repo import find_repo_root, is_ignored_by_git
from devops_cli.security.base import BaseSecurityScanner, ScanOutcome
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)

# libyaml's loader composes several times faster than the pure-Python one, with the same nodes
# and line marks; PyYAML built without libyaml has only the latter.
_YAML_LOADER: type[yaml.SafeLoader] | type[yaml.CSafeLoader] = getattr(
    yaml, "CSafeLoader", yaml.SafeLoader
)


def _build_latest_tag_finding(rel_str: str, idx: int) -> Finding:
    """Construct finding for base image using :latest tag."""
    return Finding(
        severity="MEDIUM",
        location=f"{rel_str}:{idx}",
        title="Use of ':latest' tag in base image",
        description="The base image pulls `latest`, by name or by a missing tag, unpinned.",
        fix="Pin an explicit SHA256 digest or immutable version tag.",
    )


def _build_privileged_container_finding(rel_str: str, idx: int) -> Finding:
    """Construct finding for privileged container configuration."""
    return Finding(
        severity="CRITICAL",
        location=f"{rel_str}:{idx}",
        title="Privileged container execution allowed",
        description="SecurityContext allows container root access.",
        fix="Set privileged: false and drop unnecessary capabilities.",
    )


def _floats_on_latest(image: str) -> bool:
    """Whether an image reference visibly pulls `latest`: no digest, and no tag or the tag `latest`.

    A registry port also follows a colon, but only the last path component names the tag and
    digest, so only a `$VAR` there can hide them; one in the registry or path cannot.
    """
    last = CONST_DOCKERFILE_VARIABLE_RE.sub("$", image).rsplit("/", 1)[-1]
    if "@" in last:
        return False
    name, _, tag = last.partition(":")
    if "$" in tag or (not tag and "$" in name):
        return False
    return tag in ("", CONST_DOCKER_DEFAULT_TAG)


def _escape_character(lines: list[str]) -> str:
    """The line-continuation character: a backslash, or what a leading `# escape=` sets."""
    for line in lines:
        directive = CONST_DOCKERFILE_PARSER_DIRECTIVE_RE.match(line)
        if directive is None:
            break
        if (
            directive["name"].lower() == CONST_DOCKERFILE_ESCAPE_DIRECTIVE
            and directive["value"] in CONST_DOCKERFILE_ESCAPE_CHARACTERS
        ):
            return str(directive["value"])
    return CONST_DOCKERFILE_ESCAPE_CHARACTERS[0]


def _heredoc_terminators(instruction: str) -> list[tuple[str, bool]]:
    """Each heredoc a RUN, COPY or ADD opens, in order: its terminator and whether `<<-` lets
    the terminator be indented with tabs."""
    words = instruction.split()
    if words[0].upper() == CONST_DOCKERFILE_ONBUILD_INSTRUCTION:
        words = words[1:]
    if not words or words[0].upper() not in CONST_DOCKERFILE_HEREDOC_INSTRUCTIONS:
        return []
    matches = [CONST_DOCKERFILE_HEREDOC_RE.match(word) for word in words[1:]]
    return [(match["word"], match["chomp"] == "-") for match in matches if match]


def _dockerfile_instructions(lines: list[str]) -> list[tuple[int, str]]:
    """Each instruction as Docker reads it: its first line number and its text.

    A line ending in the escape character continues on the next, skipping comment and blank
    lines between. A heredoc's body (`RUN python3 - <<EOF` up to `EOF`) is not instructions,
    so its `from x import y` is no FROM.
    """
    continuation = re.compile(re.escape(_escape_character(lines)) + r"[ \t]*$")
    instructions: list[tuple[int, str]] = []
    heredocs: list[tuple[str, bool]] = []
    text, start = "", 0
    for idx, line in enumerate(lines, start=1):
        if heredocs:
            terminator, tab_indented = heredocs[0]
            if (line.lstrip("\t") if tab_indented else line) == terminator:
                heredocs.pop(0)
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not text:
            start = idx
        joined = continuation.search(line)
        text += line[: joined.start()] if joined else line
        if joined is None:
            instructions.append((start, text.strip()))
            heredocs = _heredoc_terminators(text)
            text = ""
    if text.strip():
        instructions.append((start, text.strip()))
    return instructions


def _floating_base_image_lines(instructions: list[tuple[int, str]]) -> list[int]:
    """Line numbers of FROM instructions whose pulled image floats on `latest`.

    `scratch` and an earlier stage's name pull nothing this check can pin.
    """
    stages: set[str] = {CONST_DOCKERFILE_SCRATCH_IMAGE}
    floating: list[int] = []
    for idx, instruction in instructions:
        match = CONST_DOCKERFILE_FROM_RE.match(instruction)
        if match is None:
            continue
        image = match["image"]
        if image.lower() not in stages and _floats_on_latest(image):
            floating.append(idx)
        if match["alias"]:
            stages.add(match["alias"].lower())
    return floating


def _check_dockerfile_fallback(f: Path, rel_str: str) -> list[Finding]:
    """Scan a Dockerfile for base images floating on `latest` and a missing USER directive."""
    try:
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        logger.debug("Failed reading %s during fallback scan: %s", f, exc)
        return []
    instructions = _dockerfile_instructions(lines)
    findings = [
        _build_latest_tag_finding(rel_str, idx) for idx in _floating_base_image_lines(instructions)
    ]
    if lines and not any(CONST_DOCKERFILE_USER_RE.match(text) for _, text in instructions):
        findings.append(
            Finding(
                severity="HIGH",
                location=f"{rel_str}:1",
                title="Container runs as root user",
                description="No explicit USER directive defined in Dockerfile.",
                fix="Specify a non-root USER (e.g., USER 1000:1000).",
            )
        )
    return findings


def _mapping_value(node: yaml.Node | None, key: str) -> yaml.Node | None:
    """The value under `key` when `node` is a YAML mapping, else None."""
    if not isinstance(node, yaml.MappingNode):
        return None
    return next(
        (
            value
            for name, value in node.value
            if isinstance(name, yaml.ScalarNode) and name.value == key
        ),
        None,
    )


def _node_at(node: yaml.Node | None, path: tuple[str, ...]) -> yaml.Node | None:
    """Follow a path of mapping keys down from `node`."""
    for key in path:
        node = _mapping_value(node, key)
    return node


def _sequence_items(node: yaml.Node | None) -> list[yaml.Node]:
    """The items of a YAML sequence node, or none for any other node."""
    return list(node.value) if isinstance(node, yaml.SequenceNode) else []


def _is_yaml_true(node: yaml.Node | None) -> TypeGuard[yaml.ScalarNode]:
    """Whether a node is a YAML 1.1 boolean true, as `true`, `yes` or `on` in any case."""
    return (
        isinstance(node, yaml.ScalarNode)
        and node.tag == CONST_YAML_BOOL_TAG
        and SafeConstructor.bool_values.get(node.value.lower(), False)
    )


def _resources(document: yaml.Node | None) -> list[yaml.Node | None]:
    """The document, and each resource a `List` keeps in `items` or a Template in `objects`.

    Composed YAML shares an aliased node rather than copying it, so the walk visits each node
    once: a few anchors fanned out through `items` would otherwise take exponential time, and
    a cycle would never end. It keeps its own stack, so nesting depth costs no recursion.
    """
    found: list[yaml.Node | None] = []
    seen: set[int] = set()
    stack: list[yaml.Node | None] = [document]
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        found.append(node)
        stack.extend(
            reversed(
                [
                    item
                    for key in CONST_K8S_NESTED_RESOURCE_KEYS
                    for item in _sequence_items(_mapping_value(node, key))
                ]
            )
        )
    return found


def _privileged_container_lines(document: yaml.Node | None) -> list[int]:
    """Lines where a container in a pod spec of the document's resources sets
    `securityContext.privileged`."""
    containers = [
        container
        for resource in _resources(document)
        for path in CONST_K8S_POD_SPEC_PATHS
        for key in CONST_K8S_POD_CONTAINER_KEYS
        for container in _sequence_items(_node_at(resource, (*path, key)))
        if isinstance(container, yaml.MappingNode)
    ]
    flags = [_node_at(container, ("securityContext", "privileged")) for container in containers]
    return sorted({flag.start_mark.line + 1 for flag in flags if _is_yaml_true(flag)})


def _check_k8s_fallback(f: Path, rel_str: str) -> list[Finding]:
    """Scan a YAML file for privileged containers in the pod spec of any workload kind.

    Each document is read as YAML, so every kind's pod spec and every container list is
    checked. A file that will not parse, such as a Helm template, or that nests deeper than the
    composer or the walk can recurse, is matched line by line.
    """
    try:
        content = f.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.debug("Failed reading %s during k8s fallback: %s", f, exc)
        return []
    try:
        documents = list(yaml.compose_all(content, Loader=_YAML_LOADER))
        lines = sorted({line for doc in documents for line in _privileged_container_lines(doc)})
    except yaml.YAMLError, RecursionError:
        lines = [
            idx
            for idx, line in enumerate(content.splitlines(), start=1)
            if CONST_K8S_PRIVILEGED_LINE_RE.match(line)
        ]
    return [_build_privileged_container_finding(rel_str, idx) for idx in lines]


def _run_native_fallback_iac_checks(target_path: Path) -> list[Finding]:
    """Fallback static checks for Dockerfiles and Kubernetes when checkov is not installed."""
    findings: list[Finding] = []
    resolved = target_path.resolve()
    rel_root = resolved if resolved.is_dir() else resolved.parent
    repo_root = find_repo_root(rel_root)
    target_files = [resolved] if resolved.is_file() else list(resolved.rglob("*"))

    for f in target_files:
        if not f.is_file() or f.is_symlink() or (repo_root and is_ignored_by_git(repo_root, f)):
            continue
        if not f.resolve().is_relative_to(rel_root):
            continue
        rel_str = str(f.relative_to(rel_root)) if f.is_relative_to(rel_root) else f.name

        if f.name.lower() == "dockerfile" or f.name.lower().endswith(".dockerfile"):
            findings.extend(_check_dockerfile_fallback(f, rel_str))
        elif f.suffix.lower() in (".yaml", ".yml") and not f.name.startswith("."):
            findings.extend(_check_k8s_fallback(f, rel_str))

    return findings


def _parse_checkov_check(check: dict[str, Any]) -> Finding:
    """Transform a single Checkov failed check dict into a structured Finding model."""
    check_id = check.get("check_id", "CKV_UNKNOWN")
    check_name = check.get("check_name", "IaC Policy Violation")
    file_path = check.get("file_path", "")
    file_line_range = check.get("file_line_range", [1, 1])
    start_line = file_line_range[0] if file_line_range else 1
    guideline = check.get("guideline", "")

    severity = "HIGH"
    if "CRITICAL" in check_name.upper():
        severity = "CRITICAL"
    elif "LOW" in check_name.upper():
        severity = "LOW"

    loc = f"{file_path.lstrip('/')}:{start_line}" if file_path else f":{start_line}"
    return Finding(
        severity=severity,
        location=loc,
        title=f"[{check_id}] {check_name}",
        description=check.get("check_result", {}).get("evaluated_keys", "") or check_name,
        fix=guideline or "Review Checkov policy remediation guidance.",
    )


def _parse_checkov_results(results_data: Any) -> list[Finding]:
    """Parse raw Checkov CLI JSON output into a list of normalized Finding models."""
    results = results_data if isinstance(results_data, list) else [results_data]
    findings: list[Finding] = []
    for res in results:
        failed_checks = res.get("results", {}).get("failed_checks", [])
        for check in failed_checks:
            findings.append(_parse_checkov_check(check))
    return findings


class CheckovScanner(BaseSecurityScanner):
    """Declarative security scanner adapter for Checkov IaC analyzer."""

    name: str = "checkov"
    binary_name: str = "checkov"
    gating: ClassVar[bool] = True
    has_builtin_patterns: ClassVar[bool] = True

    def build_command(
        self,
        target_path: Path,
        framework: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Build argument command list for invoking Checkov."""
        cmd = [
            self.binary_name,
            "-d" if target_path.is_dir() else "-f",
            str(target_path),
            "-o",
            "json",
        ]
        if framework:
            cmd.extend(["--framework", framework])
        return cmd

    def parse_output(self, data: Any, target_path: Path) -> list[Finding]:
        """Parse raw Checkov output data into Finding models."""
        return _parse_checkov_results(data)

    def fallback_scan(self, target_path: Path) -> list[Finding]:
        """Execute native fallback inspection for Dockerfiles and K8s manifests."""
        return _run_native_fallback_iac_checks(target_path)


@trace_span("security.checkov")
def run_checkov_scan(
    target_path: Path,
    framework: str | None = None,
    timeout: float = DEFAULT_MCP_TOOL_SHORT_TIMEOUT_SECONDS,
) -> ScanOutcome:
    """Execute Checkov IaC security scanner on target_path and return scan outcome."""
    scanner = CheckovScanner()
    return scanner.scan(target_path, timeout=timeout, framework=framework)
