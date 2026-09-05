# Knowledge Base: PydanticAI (Standardized Agent Framework)

## 1. Overview & Purpose

`PydanticAI` is a Python agent framework built by the Pydantic team that uses Pydantic models for structured outputs, dependency injection, and tool validation. In `devops-cli`, `PydanticAI` provides a standardized agent architecture (`devops_cli.ai.pydantic_ai_bridge`), integrating multi-persona reviewers, FastMCP tools, and typed reasoning schemas.

---

## 2. Usage Information & Architecture

- **Type-Safe Agent Execution**: Uses Pydantic schemas to validate LLM responses and arguments passed to agent tools.
- **Model Agnostic**: Integrates with local Ollama backends, Anthropic Claude, OpenAI, and GitHub Copilot.
- **Context & Dependency Injection**: Injects runtime settings, workspace repositories, and token budgets (`DevOpsAgentContext`) into agent runs.
- **Interoperability**: Bridges seamlessly with existing DevOps CLI `LLMClient` and FastMCP tools.

---

## 3. Common & Advanced Commands

### DevOps CLI Agent Integration
```python
from devops_cli.ai.pydantic_ai_bridge import create_pydantic_ai_agent, get_persona_pydantic_agent
from devops_cli.ai.personas import Persona

# Instantiate persona-tailored PydanticAI agent
agent = get_persona_pydantic_agent(Persona.DEVSECOPS)

# Run typed review or reasoning workflow
# result = agent.run_sync("Audit network endpoints in src/devops_cli/security/")
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
