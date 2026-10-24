"""LLM Gateway configuration rendering, context length alignment, and unified diffing."""

from __future__ import annotations

import contextlib
import difflib
import re
from pathlib import Path
from typing import Any, Final

import yaml

_WEIGHT_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*weight:\s*\d+\s*$")
_MAX_TOKENS_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^(\s*max_input_tokens:\s*)(\d+)(\s*)$")
_API_BASE_RE: Final[re.Pattern[str]] = re.compile(r"api_base:\s*https?://([^.]+)\.")
# The LiteLLM config file k8s/llm/gateway/config.yaml: its sections are top-level keys, and each
# model_list entry starts at an indent of two.
_SECTION_HEADER_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z0-9_-]+:")
_ENTRY_START_RE: Final[re.Pattern[str]] = re.compile(r"^\s{2}-\s+")


def _extract_container_context_length(container: dict[str, Any]) -> int | None:
    """Extract integer OLLAMA_CONTEXT_LENGTH value from container env list."""
    for env_var in container.get("env", []):
        if env_var.get("name") == "OLLAMA_CONTEXT_LENGTH":
            with contextlib.suppress(ValueError, TypeError):
                return int(env_var["value"])
    return None


def load_tier_context_lengths(profiles_manifest: Path) -> dict[str, int]:
    """Extract OLLAMA_CONTEXT_LENGTH for each DaemonSet from the profiles manifest."""
    content = profiles_manifest.read_text(encoding="utf-8")
    tier_lengths: dict[str, int] = {}
    for doc in yaml.safe_load_all(content):
        if not isinstance(doc, dict) or doc.get("kind") != "DaemonSet":
            continue
        name = doc.get("metadata", {}).get("name")
        if not name:
            continue
        containers = doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for container in containers:
            val = _extract_container_context_length(container)
            if val is not None:
                tier_lengths[str(name)] = val
    return tier_lengths


def _match_service_to_tier(
    sname: str,
    vram: str | None,
    speed: str | None,
    tier_lengths: dict[str, int],
) -> int | None:
    """Resolve a service's context length by matching name or vram/speed selectors."""
    if sname in tier_lengths:
        return tier_lengths[sname]
    if vram:
        slow_key = f"ollama-{vram}-slow"
        if speed == "slow" and slow_key in tier_lengths:
            return tier_lengths[slow_key]
        standard_key = f"ollama-{vram}"
        if standard_key in tier_lengths:
            return tier_lengths[standard_key]
    return None


def load_service_context_lengths(
    services_manifest: Path, tier_lengths: dict[str, int]
) -> dict[str, int]:
    """Map service names to their corresponding tier context length."""
    content = services_manifest.read_text(encoding="utf-8")
    service_lengths: dict[str, int] = {}
    for doc in yaml.safe_load_all(content):
        if not isinstance(doc, dict) or doc.get("kind") != "Service":
            continue
        sname = doc.get("metadata", {}).get("name")
        if not sname:
            continue
        selector = doc.get("spec", {}).get("selector", {})
        vram = selector.get("llm.devops.io/vram-gib")
        speed = selector.get("llm.devops.io/speed-tier")
        matched = _match_service_to_tier(str(sname), vram, speed, tier_lengths)
        if matched is not None:
            service_lengths[str(sname)] = matched
    return service_lengths


def _process_deployment_block(block_lines: list[str], service_lengths: dict[str, int]) -> list[str]:
    """Process a single deployment entry: remove weight and update max_input_tokens."""
    svc = None
    for line in block_lines:
        match = _API_BASE_RE.search(line)
        if match:
            svc = match.group(1)
            break

    result: list[str] = []
    for line in block_lines:
        if _WEIGHT_LINE_RE.match(line):
            continue
        match_tok = _MAX_TOKENS_LINE_RE.match(line)
        if match_tok and svc and svc in service_lengths:
            prefix, _, suffix = match_tok.groups()
            result.append(f"{prefix}{service_lengths[svc]}{suffix}")
            continue
        result.append(line)
    return result


def render_gateway_config(config_content: str, service_lengths: dict[str, int]) -> str:
    """Render the gateway's LiteLLM config text: remove weights and align max_input_tokens."""
    lines = config_content.splitlines(keepends=True)
    output_lines: list[str] = []
    in_model_list = False
    current_block: list[str] = []

    for line in lines:
        if line.strip().startswith("model_list:"):
            in_model_list = True
            output_lines.append(line)
            continue
        if in_model_list:
            if _SECTION_HEADER_RE.match(line):
                in_model_list = False
                output_lines.extend(_process_deployment_block(current_block, service_lengths))
                current_block = []
                output_lines.append(line)
                continue
            if _ENTRY_START_RE.match(line):
                output_lines.extend(_process_deployment_block(current_block, service_lengths))
                current_block = [line]
                continue
            current_block.append(line)
        else:
            output_lines.append(line)

    if current_block:
        output_lines.extend(_process_deployment_block(current_block, service_lengths))

    return "".join(output_lines)


def diff_gateway_config(
    current_content: str, rendered_content: str, filename: str = "config.yaml"
) -> str:
    """Generate a unified diff between current and rendered gateway configuration."""
    if current_content == rendered_content:
        return ""
    diff_lines = list(
        difflib.unified_diff(
            current_content.splitlines(keepends=True),
            rendered_content.splitlines(keepends=True),
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
    )
    return "".join(diff_lines)


__all__ = [
    "diff_gateway_config",
    "load_service_context_lengths",
    "load_tier_context_lengths",
    "render_gateway_config",
]
