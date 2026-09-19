"""Default industrial average pricing catalog for popular commercial and open-source models."""

from __future__ import annotations

from devops_cli.ai.spend.models import ModelPricing

DEFAULT_INDUSTRIAL_MODEL_PRICING: dict[str, ModelPricing] = {
    # ── OpenAI ───────────────────────────────────────────────────────────────
    "gpt-4o": ModelPricing(prompt_usd_per_million=2.50, completion_usd_per_million=10.00),
    "gpt-4o-2024-08-06": ModelPricing(
        prompt_usd_per_million=2.50, completion_usd_per_million=10.00
    ),
    "gpt-4o-mini": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.60),
    "gpt-4o-mini-2024-07-18": ModelPricing(
        prompt_usd_per_million=0.15, completion_usd_per_million=0.60
    ),
    "gpt-4-turbo": ModelPricing(prompt_usd_per_million=10.00, completion_usd_per_million=30.00),
    "gpt-4": ModelPricing(prompt_usd_per_million=30.00, completion_usd_per_million=60.00),
    "gpt-3.5-turbo": ModelPricing(prompt_usd_per_million=0.50, completion_usd_per_million=1.50),
    "o1": ModelPricing(prompt_usd_per_million=15.00, completion_usd_per_million=60.00),
    "o1-mini": ModelPricing(prompt_usd_per_million=3.00, completion_usd_per_million=12.00),
    "o1-preview": ModelPricing(prompt_usd_per_million=15.00, completion_usd_per_million=60.00),
    "o3-mini": ModelPricing(prompt_usd_per_million=1.10, completion_usd_per_million=4.40),
    # ── Anthropic Claude ─────────────────────────────────────────────────────
    "claude-3-7-sonnet-20250219": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-7-sonnet": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-5-sonnet-20241022": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-5-sonnet": ModelPricing(
        prompt_usd_per_million=3.00, completion_usd_per_million=15.00
    ),
    "claude-3-5-haiku": ModelPricing(prompt_usd_per_million=0.80, completion_usd_per_million=4.00),
    "claude-3-5-haiku-20241022": ModelPricing(
        prompt_usd_per_million=0.80, completion_usd_per_million=4.00
    ),
    "claude-3-opus": ModelPricing(prompt_usd_per_million=15.00, completion_usd_per_million=75.00),
    "claude-3-sonnet": ModelPricing(prompt_usd_per_million=3.00, completion_usd_per_million=15.00),
    "claude-3-haiku": ModelPricing(prompt_usd_per_million=0.25, completion_usd_per_million=1.25),
    # ── Google Gemini ────────────────────────────────────────────────────────
    "gemini-1.5-flash": ModelPricing(prompt_usd_per_million=0.075, completion_usd_per_million=0.30),
    "gemini-1.5-pro": ModelPricing(prompt_usd_per_million=1.25, completion_usd_per_million=5.00),
    "gemini-2.0-flash": ModelPricing(prompt_usd_per_million=0.10, completion_usd_per_million=0.40),
    "gemini-2.0-pro": ModelPricing(prompt_usd_per_million=1.25, completion_usd_per_million=5.00),
    # ── DeepSeek (Industrial Cloud Average: DeepInfra / Together / Fireworks) ─
    "deepseek-chat": ModelPricing(prompt_usd_per_million=0.14, completion_usd_per_million=0.28),
    "deepseek-v3": ModelPricing(prompt_usd_per_million=0.14, completion_usd_per_million=0.28),
    "deepseek-reasoner": ModelPricing(prompt_usd_per_million=0.55, completion_usd_per_million=2.19),
    "deepseek-r1": ModelPricing(prompt_usd_per_million=0.55, completion_usd_per_million=2.19),
    "deepseek-coder": ModelPricing(prompt_usd_per_million=0.14, completion_usd_per_million=0.28),
    # ── Meta Llama 3 / 3.1 / 3.2 / 3.3 (Industrial Hosted Average) ───────────
    "llama-3.1-8b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "llama-3.1-70b": ModelPricing(prompt_usd_per_million=0.70, completion_usd_per_million=0.90),
    "llama-3.1-405b": ModelPricing(prompt_usd_per_million=2.50, completion_usd_per_million=5.00),
    "llama-3.2-1b": ModelPricing(prompt_usd_per_million=0.05, completion_usd_per_million=0.10),
    "llama-3.2-3b": ModelPricing(prompt_usd_per_million=0.08, completion_usd_per_million=0.15),
    "llama-3.3-70b": ModelPricing(prompt_usd_per_million=0.70, completion_usd_per_million=0.90),
    "llama3:8b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "llama3:70b": ModelPricing(prompt_usd_per_million=0.70, completion_usd_per_million=0.90),
    "llama3.1:8b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "llama3.1:70b": ModelPricing(prompt_usd_per_million=0.70, completion_usd_per_million=0.90),
    # ── Qwen 2.5 & Qwen 2.5 Coder (Industrial Hosted Average) ────────────────
    "qwen2.5-coder:7b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "qwen2.5-coder:14b": ModelPricing(prompt_usd_per_million=0.25, completion_usd_per_million=0.50),
    "qwen2.5-coder:32b": ModelPricing(prompt_usd_per_million=0.40, completion_usd_per_million=0.80),
    "qwen-2.5-coder-7b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "qwen-2.5-coder-14b": ModelPricing(
        prompt_usd_per_million=0.25, completion_usd_per_million=0.50
    ),
    "qwen-2.5-coder-32b": ModelPricing(
        prompt_usd_per_million=0.40, completion_usd_per_million=0.80
    ),
    "qwen2.5:7b": ModelPricing(prompt_usd_per_million=0.15, completion_usd_per_million=0.30),
    "qwen2.5:14b": ModelPricing(prompt_usd_per_million=0.25, completion_usd_per_million=0.50),
    "qwen2.5:32b": ModelPricing(prompt_usd_per_million=0.40, completion_usd_per_million=0.80),
    "qwen2.5:72b": ModelPricing(prompt_usd_per_million=0.70, completion_usd_per_million=1.00),
    # ── Mistral & Codestral ──────────────────────────────────────────────────
    "mistral-small": ModelPricing(prompt_usd_per_million=0.20, completion_usd_per_million=0.60),
    "mistral-large": ModelPricing(prompt_usd_per_million=2.00, completion_usd_per_million=6.00),
    "codestral": ModelPricing(prompt_usd_per_million=0.20, completion_usd_per_million=0.60),
    "mixtral-8x7b": ModelPricing(prompt_usd_per_million=0.24, completion_usd_per_million=0.48),
    "mixtral-8x22b": ModelPricing(prompt_usd_per_million=0.90, completion_usd_per_million=0.90),
    # ── Default Fallbacks ────────────────────────────────────────────────────
    "ollama": ModelPricing(prompt_usd_per_million=0.25, completion_usd_per_million=0.50),
    "default": ModelPricing(prompt_usd_per_million=0.50, completion_usd_per_million=1.00),
}
