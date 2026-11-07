# `devops mcp`

FastMCP server and Model Context Protocol integrations. The tool ai_fetch_page reads a web page through the Crawl4AI service. On a workstation, run `kubectl port-forward -n devops svc/crawl4ai 11235:11235` and set crawl4ai.url to http://127.0.0.1:11235. The token comes from the credential store, never from a tool parameter.

## Commands

## `devops mcp serve`

**Launch FastMCP server to expose devops-cli tools to MCP clients.**

```bash
devops mcp serve [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--transport`, `-t` | `string` | `stdio` | Transport protocol for FastMCP server (stdio | sse | streamable-http). streamable-http serves one endpoint per job role and needs the mcp.token setting. |
| `--host`, `-h` | `string` | `127.0.0.1` | Host interface for the sse and streamable-http transports. |
| `--port`, `-p` | `integer` | `8000` | Port number for the sse and streamable-http transports. |
| `--allow-remote` | `boolean` | - | Permit binding a network transport to non-loopback network interfaces. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---

## `devops mcp tools`

**List all registered FastMCP tools and descriptions.**

```bash
devops mcp tools
```

---

## `devops mcp export-schemas`

**Export FastMCP tool JSON schemas and instructions for MCP clients.**

```bash
devops mcp export-schemas [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--output-dir`, `-o` | `path` | - | Destination directory for tool schema JSON files. |
| `--dry-run` | `boolean` | - | Preview execution plan without mutating external state. |

---
