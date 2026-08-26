# `devops mcp`

FastMCP server and Model Context Protocol integrations.

## Commands

## `devops mcp serve`

**Launch FastMCP server to expose devops-cli tools to MCP clients.**

```bash
devops mcp serve [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--transport`, `-t` | `string` | `stdio` | Transport protocol for FastMCP server (stdio | sse). |
| `--host`, `-h` | `string` | `127.0.0.1` | Host interface for SSE transport. |
| `--port`, `-p` | `integer` | `8000` | Port number for SSE transport. |
| `--allow-remote` | `boolean` | - | Permit binding SSE transport to non-loopback network interfaces. |

---

## `devops mcp tools`

**List all registered FastMCP tools and descriptions.**

```bash
devops mcp tools
```

---
