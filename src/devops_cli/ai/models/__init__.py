"""AI models and provider integration package for devops-cli."""

from typing import Any

_OLLAMA_EXPORTS: frozenset[str] = frozenset(
    {
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
    }
)


def __getattr__(name: str) -> Any:
    if name in _OLLAMA_EXPORTS:
        import devops_cli.ai.models.ollama as _ollama

        val = getattr(_ollama, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
