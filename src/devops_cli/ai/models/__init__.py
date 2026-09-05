"""AI models and provider integration package for devops-cli."""

from __future__ import annotations

from devops_cli.ai.models.ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    ModelProfileSpec,
    ModelSettings,
    OllamaModel,
    OllamaProvider,
    OpenAIChatModel,
    OpenAIJsonSchemaTransformer,
    OpenAIModelProfile,
    cohere_model_profile,
    create_ollama_model,
    create_ollama_provider,
    deepseek_model_profile,
    get_recommended_output_mode,
    google_model_profile,
    harmony_model_profile,
    is_ollama_cloud,
    meta_model_profile,
    mistral_model_profile,
    normalize_ollama_base_url,
    qwen_model_profile,
)

__all__ = [
    "DEFAULT_OLLAMA_BASE_URL",
    "ModelProfileSpec",
    "ModelSettings",
    "OllamaModel",
    "OllamaProvider",
    "OpenAIChatModel",
    "OpenAIJsonSchemaTransformer",
    "OpenAIModelProfile",
    "cohere_model_profile",
    "create_ollama_model",
    "create_ollama_provider",
    "deepseek_model_profile",
    "get_recommended_output_mode",
    "google_model_profile",
    "harmony_model_profile",
    "is_ollama_cloud",
    "meta_model_profile",
    "mistral_model_profile",
    "normalize_ollama_base_url",
    "qwen_model_profile",
]
