"""AI client, persona utilities, response formatting, and reasoning streaming engine."""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "AIClientError":
        from devops_cli.ai.client import AIClientError

        return AIClientError
    if name in {
        "CONST_CLAUDE_MD_FILENAME",
        "CONST_COPILOT_INSTRUCTIONS_PATH",
        "DEFAULT_AGENT_FILES",
        "ProjectMetadata",
        "generate_agents_md",
        "generate_instruction_content",
        "generate_pointer_stub",
        "parse_project_metadata",
        "scaffold_agent_instructions",
    }:
        import devops_cli.ai.instruction_generator

        return getattr(devops_cli.ai.instruction_generator, name)
    if name in {
        "get_knowledge_base_dir",
        "get_knowledge_base_stats",
        "list_knowledge_base_articles",
        "load_kb_article",
    }:
        import devops_cli.ai.kb

        return getattr(devops_cli.ai.kb, name)
    if name in {"ModelBundleManifest", "bundle_ollama_models"}:
        import devops_cli.ai.model_bundler

        return getattr(devops_cli.ai.model_bundler, name)
    if name in {
        "CachedLLMResponse",
        "LLMResponseCache",
        "get_llm_response_cache",
        "reset_llm_response_cache",
    }:
        import devops_cli.ai.response_cache

        return getattr(devops_cli.ai.response_cache, name)
    if name in {
        "ExtractedToolCall",
        "FormattedLLMResponse",
        "extract_tool_invocations",
        "fix_llm_response",
        "repair_json_string",
    }:
        import devops_cli.ai.response_repair

        return getattr(devops_cli.ai.response_repair, name)
    if name in {
        "ThinkingStreamProcessor",
        "extract_think_blocks",
        "strip_think_blocks",
    }:
        import devops_cli.ai.thinking_stream

        return getattr(devops_cli.ai.thinking_stream, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AIClientError",
    "CONST_CLAUDE_MD_FILENAME",
    "CONST_COPILOT_INSTRUCTIONS_PATH",
    "CachedLLMResponse",
    "DEFAULT_AGENT_FILES",
    "ExtractedToolCall",
    "FormattedLLMResponse",
    "LLMResponseCache",
    "ModelBundleManifest",
    "ProjectMetadata",
    "ThinkingStreamProcessor",
    "bundle_ollama_models",
    "extract_think_blocks",
    "extract_tool_invocations",
    "fix_llm_response",
    "generate_agents_md",
    "generate_instruction_content",
    "generate_pointer_stub",
    "get_knowledge_base_dir",
    "get_knowledge_base_stats",
    "get_llm_response_cache",
    "list_knowledge_base_articles",
    "load_kb_article",
    "parse_project_metadata",
    "repair_json_string",
    "reset_llm_response_cache",
    "scaffold_agent_instructions",
    "strip_think_blocks",
]
