---
applies_to:
  - "pkg:pypi/pydantic-ai@2.59.*"
sources:
  - "https://ai.pydantic.dev/"
  - "https://github.com/pydantic/pydantic-ai"
reviewed: "2026-10-22"
tags:
  - "pydantic-ai"
  - "ai"
  - "agents"
---

# Knowledge Base: PydanticAI (Standardized Agent Framework)

## 1. Overview & Purpose

`PydanticAI` is a Python agent framework built by the Pydantic team that uses Pydantic models for structured outputs, dependency injection, and tool validation. In `devops-cli`, `PydanticAI` provides the agent framework and model types, and `devops_cli.ai.pydantic_ai_bridge` resolves a configured model name to a pydantic-ai `Model` and builds fallback cascades across models.

---

## 2. Usage Information & Architecture

- **Type-Safe Agent Execution**: Uses Pydantic schemas to validate LLM responses and arguments passed to agent tools.
- **Model Agnostic**: Integrates with local Ollama backends, Anthropic Claude, OpenAI, and GitHub Copilot.
- **Endpoint-Safe Model Resolution**: A remote model is sent to the endpoint its settings name. Its provider, and the Ollama provider too, gets a client from `new_async_http_client` that checks each address at the connect against the configured egress level (loopback allowed, any other non-public host needs `ai.allow_private_network`).
- **Fallback Cascades**: `build_fallback_cascade_model` tries the gateway routes and then Ollama in order, through pydantic-ai's `FallbackModel`.

---

## 3. Common & Advanced Commands

### DevOps CLI Model Resolution
```python
from devops_cli.ai.pydantic_ai_bridge import build_fallback_cascade_model, resolve_pydantic_ai_model

# Resolve a configured model name to a pydantic-ai Model on its configured endpoint
model = resolve_pydantic_ai_model("ollama:qwen3-coder:30b")

# Fall back across the gateway routes and then Ollama
cascade = build_fallback_cascade_model()
```

---

## 4. Best Practice Guidance

1. **Strict Output Schemas**: Always define structured Pydantic response models (`output_type`) for agents rather than parsing untyped string output.
2. **Defensive Tool Validation**: Validate tool inputs with Pydantic type annotations to eliminate invalid parameter calls.
3. **Explicit Token Budgeting**: Combine with `tiktoken` context budgeting to ensure agent message histories do not exceed model context limits.

---

## 5. Official References & Published Artifacts

- **Project Homepage**: [ai.pydantic.dev](https://ai.pydantic.dev/)
- **Official GitHub Repo**: [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)
- **DevOps CLI PydanticAI Bridge**: [src/devops_cli/ai/pydantic_ai_bridge.py](../../../../ai/pydantic_ai_bridge.py)
