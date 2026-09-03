# Code Library: FastMCP (Model Context Protocol Server & Tool Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) • [modelcontextprotocol.io](https://modelcontextprotocol.io/) |
| **Public Git Repository** | [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp) |
| **Official PyPI Package** | [pypi.org/project/fastmcp](https://pypi.org/project/fastmcp/) (`3.4.7`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/mcp/`](file:///workspaces/devops-cli/src/devops_cli/ai/mcp/) • [`src/devops_cli/commands/mcp.py`](file:///workspaces/devops-cli/src/devops_cli/commands/mcp.py) |

---

## 2. General Information & Architecture

**FastMCP** is a high-level Python framework for building Model Context Protocol (MCP) servers. The Model Context Protocol is an open standard created by Anthropic that allows AI assistants (Claude Desktop, Cursor, GitHub Copilot, Antigravity IDE) to securely inspect local resources, query developer tools, and invoke automation commands.

In `devops-cli`:
- **Tool Exporter**: Exposes 45+ CLI operations (`review_path`, `k8s_pods`, `tf_plan`, `scan_uv_audit`, `security_intel_package`) as native MCP tools.
- **Dual Transport Engine**: Supports both standard input/output (`stdio`) for local IDE processes and Server-Sent Events (`sse`) for remote container networking.
- **Dynamic Introspection**: Implements `devops mcp tools` to list all registered tools, arguments, and return types.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose FastMCP |
| :--- | :--- | :--- | :--- |
| **`fastmcp`** | Decorator-based tool registration (`@mcp.tool`), Pydantic schema generation, built-in stdio/SSE server, fast startup. | Focused strictly on MCP protocol. | **Selected**: The most developer-friendly, robust MCP implementation in Python. |
| **`mcp`** (Official SDK) | Low-level reference implementation from Anthropic. | More verbose boilerplate, manual schema wiring, low-level async socket handling. | Rejected: FastMCP wraps the official SDK with ergonomic Pydantic abstractions. |
| **Custom REST Endpoints** | Universal HTTP interface. | Lacks MCP semantic tool negotiation, prompt injection protocol, and IDE extension discovery. | Rejected: Modern AI IDEs require standardized MCP integration. |

---

## 4. Key Concepts & Core Patterns

1. **`FastMCP` Instance**: Central server registry initialized with server name and metadata:
   ```python
   from fastmcp import FastMCP

   mcp = FastMCP("devops-cli")
   ```
2. **`@mcp.tool` Decorator**: Registers typed Python functions as MCP tools, automatically extracting argument descriptions from docstrings and Pydantic schemas.
3. **Lazy Tool Execution**: Internal modules are imported only when the specific tool is called by an AI client to maintain lightning-fast server startup.
4. **Transport Protocols**:
   - `mcp.run(transport="stdio")`: Standard I/O for IDE subprocess launch.
   - `mcp.run(transport="sse", host="127.0.0.1", port=8000)`: HTTP/SSE for remote networks.

---

## 5. Common & Advanced Usage Examples

### Declaring an MCP Tool in DevOps CLI
```python
from fastmcp import FastMCP
from devops_cli.commands.k8s import pods

mcp = FastMCP("devops-cli")


@mcp.tool()
def k8s_pods(namespace: str = "default") -> str:
    """List running pods in a Kubernetes namespace with health status."""
    return f"Pods in namespace '{namespace}' retrieved successfully."
```

### Launching the MCP Server via CLI
```bash
# Launch in stdio mode (used by AI assistants and IDE plugins)
devops mcp serve

# Launch in SSE network mode for containerized agent networks
devops mcp serve --transport sse --port 8000
```

---

## 6. Best Practices & Security Standards

1. **Loopback Binding by Default**: Always bind SSE servers to `127.0.0.1` unless explicitly configured with `--allow-remote`.
2. **Defensive Parameter Sanitization**: Filter and validate all incoming tool arguments to prevent command injection or unauthorized directory traversal.
3. **Zero Secret Leaks**: Ensure MCP tool descriptions and returns never contain plaintext authorization tokens or private SSH keys.
