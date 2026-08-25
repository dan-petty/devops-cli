"""AI client, persona utilities, response formatting, and reasoning streaming engine."""

from __future__ import annotations

from devops_cli.ai.client import AIClientError
from devops_cli.ai.instruction_generator import (
    CONST_CLAUDE_MD_FILENAME,
    CONST_COPILOT_INSTRUCTIONS_PATH,
    DEFAULT_AGENT_FILES,
    ProjectMetadata,
    generate_agents_md,
    generate_instruction_content,
    generate_pointer_stub,
    parse_project_metadata,
    scaffold_agent_instructions,
)
from devops_cli.ai.kb import (
    get_knowledge_base_dir,
    get_knowledge_base_stats,
    list_knowledge_base_articles,
    load_kb_article,
)
from devops_cli.ai.model_bundler import ModelBundleManifest, bundle_ollama_models
from devops_cli.ai.response_cache import (
    CachedLLMResponse,
    LLMResponseCache,
    get_llm_response_cache,
    reset_llm_response_cache,
)
from devops_cli.ai.response_repair import (
    ExtractedToolCall,
    FormattedLLMResponse,
    extract_tool_invocations,
    fix_llm_response,
    repair_json_string,
)
from devops_cli.ai.thinking_stream import (
    ThinkingStreamProcessor,
    extract_think_blocks,
    strip_think_blocks,
)

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
