"""AI client, persona utilities, response formatting, and reasoning streaming engine."""

from __future__ import annotations

from typing import Any


def __getattr__(name: str) -> Any:
    if name in {"AIClientError", "LLMClient", "LLMResponse", "model_request_sync", "model_request"}:
        import devops_cli.ai.client

        return getattr(devops_cli.ai.client, name)
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
        "KnowledgeBaseStats",
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
        "ResponseCacheStats",
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
    if name in {"duckduckgo_search_tool", "web_fetch_tool", "tavily_search_tool"}:
        import devops_cli.ai.common_tools

        return getattr(devops_cli.ai.common_tools, name)
    if name in {"tool_from_langchain", "LangChainToolset"}:
        import devops_cli.ai.ext_langchain

        return getattr(devops_cli.ai.ext_langchain, name)
    if name in {
        "Advisor",
        "AgentOverride",
        "Band",
        "CacheBustWarning",
        "CacheMark",
        "ClampOversizedMessages",
        "ClearToolResults",
        "CodeMode",
        "Coder",
        "CompactionReceipt",
        "ContextUsage",
        "DEFAULT_MACROSCOPE_GUIDANCE",
        "DEFAULT_PLANNING_GUIDANCE",
        "DEFAULT_PLAYWRIGHT_GUIDANCE",
        "DEFAULT_RESEARCHER_INSTRUCTIONS",
        "DeduplicateFileReads",
        "DynamicWorkflow",
        "FallbackCompaction",
        "FileSystem",
        "InMemoryPlanStore",
        "LLM_API_KEY_ENV_PATTERNS",
        "LocalFileStore",
        "MINIMUM_EFFORT_FLOOR",
        "Macroscope",
        "MacroscopeIssue",
        "MacroscopeReview",
        "ModelOption",
        "MountDir",
        "OSAccess",
        "OverflowStore",
        "Passthrough",
        "PlanEvent",
        "PlanEventEmitter",
        "PlanItem",
        "Planning",
        "PlanStore",
        "PlaywrightBrowser",
        "RepoContext",
        "ReportContextUsage",
        "Researcher",
        "Shell",
        "SlidingWindowCompaction",
        "Spill",
        "SqlitePlanStore",
        "SubAgent",
        "SubAgents",
        "Summarize",
        "SummarizingCompaction",
        "TieredCompaction",
        "ToolOutputLimits",
        "ToolSearch",
        "TranscriptHandleProvider",
        "Truncate",
        "TruncationStrategy",
        "WarnNearLimits",
        "WarnOnCacheBusts",
        "WorkflowAgent",
        "clamp_effort",
        "coder_agent",
        "compact_now",
        "indented_json",
        "is_pinned",
        "json_lines",
        "pin",
        "reinject_pinned",
        "researcher_agent",
    }:
        import devops_cli.ai.harness

        return getattr(devops_cli.ai.harness, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AIClientError",
    "Advisor",
    "AgentOverride",
    "Band",
    "CacheBustWarning",
    "CacheMark",
    "CachedLLMResponse",
    "ClampOversizedMessages",
    "ClearToolResults",
    "CodeMode",
    "Coder",
    "CompactionReceipt",
    "CONST_CLAUDE_MD_FILENAME",
    "CONST_COPILOT_INSTRUCTIONS_PATH",
    "ContextUsage",
    "DEFAULT_AGENT_FILES",
    "DEFAULT_MACROSCOPE_GUIDANCE",
    "DEFAULT_PLANNING_GUIDANCE",
    "DEFAULT_PLAYWRIGHT_GUIDANCE",
    "DEFAULT_RESEARCHER_INSTRUCTIONS",
    "DeduplicateFileReads",
    "DynamicWorkflow",
    "ExtractedToolCall",
    "FallbackCompaction",
    "FileSystem",
    "FormattedLLMResponse",
    "InMemoryPlanStore",
    "KnowledgeBaseStats",
    "LLMClient",
    "LLMResponse",
    "LLMResponseCache",
    "LLM_API_KEY_ENV_PATTERNS",
    "LangChainToolset",
    "LocalFileStore",
    "MINIMUM_EFFORT_FLOOR",
    "Macroscope",
    "MacroscopeIssue",
    "MacroscopeReview",
    "ModelBundleManifest",
    "ModelOption",
    "MountDir",
    "OSAccess",
    "OverflowStore",
    "Passthrough",
    "PlanEvent",
    "PlanEventEmitter",
    "PlanItem",
    "Planning",
    "PlanStore",
    "PlaywrightBrowser",
    "ProjectMetadata",
    "RepoContext",
    "ReportContextUsage",
    "Researcher",
    "ResponseCacheStats",
    "Shell",
    "SlidingWindowCompaction",
    "Spill",
    "SqlitePlanStore",
    "SubAgent",
    "SubAgents",
    "Summarize",
    "SummarizingCompaction",
    "ThinkingStreamProcessor",
    "TieredCompaction",
    "ToolOutputLimits",
    "ToolSearch",
    "TranscriptHandleProvider",
    "Truncate",
    "TruncationStrategy",
    "WarnNearLimits",
    "WarnOnCacheBusts",
    "WorkflowAgent",
    "bundle_ollama_models",
    "clamp_effort",
    "coder_agent",
    "compact_now",
    "duckduckgo_search_tool",
    "extract_think_blocks",
    "extract_tool_invocations",
    "fix_llm_response",
    "generate_agents_md",
    "generate_instruction_content",
    "generate_pointer_stub",
    "get_knowledge_base_dir",
    "get_knowledge_base_stats",
    "get_llm_response_cache",
    "indented_json",
    "is_pinned",
    "json_lines",
    "list_knowledge_base_articles",
    "load_kb_article",
    "model_request",
    "model_request_sync",
    "parse_project_metadata",
    "pin",
    "reinject_pinned",
    "repair_json_string",
    "researcher_agent",
    "reset_llm_response_cache",
    "scaffold_agent_instructions",
    "strip_think_blocks",
    "tavily_search_tool",
    "tool_from_langchain",
    "web_fetch_tool",
]
