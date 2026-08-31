# Code Library: PydanticAI (Type-Safe Multi-Agent Framework)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [ai.pydantic.dev](https://ai.pydantic.dev/) |
| **Public Git Repository** | [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) |
| **Official PyPI Package** | [pypi.org/project/pydantic-ai](https://pypi.org/project/pydantic-ai/) (`2.35.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/agents/`](file:///workspaces/devops-cli/src/devops_cli/ai/agents/) • [`src/devops_cli/ai/review/`](file:///workspaces/devops-cli/src/devops_cli/ai/review/) |

---

## 2. General Information & Architecture

**PydanticAI** is a typed agent framework built by the Pydantic team designed for production-grade software engineering, deterministic tool execution, and multi-persona workflows. It combines Pydantic's data validation with LLM orchestration, model-agnostic provider abstractions, dependency injection, and native Model Context Protocol (MCP) tool integration.

In `devops-cli`:
- **Persona Architecture**: Review personas (`devsecops`, `architect`, `auditor`, `qa`, `pm`) operate as specialized `PydanticAgent` instances.
- **Dynamic Toolsets**: `FunctionToolset` and `MCPToolset` dynamically expose local filesystem scanners, AST analyzers, and remote Kubernetes controllers to agent stages.
- **Usage & Budget Tracking**: `AgentUsage` tracks token consumption across agent pipelines with strict maximum turn budgets.

---

## 3. Comparable Projects & Tradeoffs

| Framework | Strengths | Weaknesses | Why `devops-cli` Chose PydanticAI |
| :--- | :--- | :--- | :--- |
| **`pydantic-ai`** | 100% Pydantic v2 type safety, structured outputs, zero prompt boilerplate, native MCP client support, lightweight async lifecycle. | Newer framework compared to LangChain. | **Selected**: Cleanest software engineering design, zero legacy prompt templating hacks, perfect alignment with Pydantic codebase. |
| **`langchain` / `langgraph`** | Enormous ecosystem of integrations. | Heavyweight, complex abstract class chains, fragile token routing, frequent breaking API deprecations. | Rejected: Bloated dependencies and complex monkey-patching patterns. |
| **`crewai`** | High-level role-playing multi-agent abstractions. | Opinionated loop abstractions, relies heavily on LangChain internals, difficult to type-check strictly. | Rejected: Lacks pure functional toolset isolation and strict Mypy compatibility. |
| **`autogen`** (Microsoft) | Conversational multi-agent framework. | High LLM chatter/token consumption, hard to constrain to strict deterministic pipelines. | Rejected: Harder to enforce strict zero-drift verification gates. |

---

## 4. Key Concepts & Core Patterns

1. **`PydanticAgent`**: Core agent class coordinating LLM inference, system instructions, tool execution, and structured result parsing.
2. **`MCPToolset`**: Seamless integration connecting remote or in-process Model Context Protocol servers:
   ```python
   async with MCPToolset(server_url="http://localhost:8000/sse") as mcp:
       agent = PydanticAgent(name="DevSecOps", toolsets=[mcp])
       result = await agent.run("Audit Kubernetes security policies")
   ```
3. **`AgentTool`**: Strongly typed tool definitions with runtime parameter schema validation and path traversal safety checks.
4. **Structured Agent Returns**: Models define explicit output schemas (`result_type=ReviewOutputModel`) ensuring LLMs return valid typed instances.

---

## 5. Common & Advanced Usage Examples

### Instantiating a Multi-Tool Review Agent
```python
from devops_cli.ai.agents import PydanticAgent, AgentTool, FunctionToolset
from devops_cli.models.review import Finding


async def analyze_dependencies(ctx, package_name: str) -> str:
    """Audit installed package for known vulnerabilities."""
    return f"Package {package_name} verified clean (0 CVEs)."


toolset = FunctionToolset()
toolset.register_tool(
    AgentTool(
        name="analyze_dependencies",
        description="Audit package vulnerabilities",
        func=analyze_dependencies,
        parameters={"package_name": {"type": "string"}},
    )
)

agent = PydanticAgent(
    name="Architect",
    system_prompt="You are a principal software architect evaluating system modularity.",
    toolsets=[toolset],
)
```

### MCP Client Sampling & Custom TLS Configuration
```python
import httpx
from devops_cli.ai.agents import PydanticAgent, MCPToolset

# Custom HTTP client with homelab TLS certificates
http_client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))

async with MCPToolset(
    url="http://localhost:8000/sse",
    http_client=http_client,
    client_info={"name": "DevOpsCLI", "version": "0.2.5"},
) as mcp:
    agent = PydanticAgent(
        name="SecurityReviewer",
        model="claude-3-5-sonnet",
        toolsets=[mcp],
    )
    # Enable MCP sampling so the connected MCP server can request completions
    agent.set_mcp_sampling_model("claude-3-5-sonnet")
    result = await agent.run("Review Kubernetes ingress security")
```

---

## 6. Best Practices & Security Standards

1. **Path Traversal Guards**: Always sanitize file paths passed as agent tool arguments using `_check_path_traversal()` to prevent directory escapes.
2. **Bounded Max Turns**: Always configure `max_turns` (default 5–10) to prevent runaway LLM agent execution loops.
3. **Pure Markdown Prompt Tasks**: Load system prompts exclusively from `.md` files under `src/devops_cli/ai/prompts/` via `load_task_prompt()`. Never write multi-line inline prompt strings.
