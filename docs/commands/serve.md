# `devops serve`

FastAPI REST and OpenAPI service engine.

## Commands

## `devops serve`

**FastAPI REST & OpenAPI Service Engine for remote automation, health probes, and metrics.**

```bash
devops serve [OPTIONS]
```

**Options:**

| Option / Flag | Type | Default | Description |
|---|---|---|---|
| `--host`, `-h` | `string` | `127.0.0.1` | Network interface host to bind the HTTP server. |
| `--port`, `-p` | `integer` | `8000` | TCP port to listen on. |
| `--reload`, `-r` | `boolean` | - | Enable auto-reload on code changes (development mode). |
| `--workers`, `-w` | `integer` | `1` | Number of worker processes. |
| `--log-level`, `-l` | `string` | `info` | Logging level (debug, info, warning, error). |
| `--docs`, `--no-docs` | `boolean` | `True` | Enable or disable Swagger UI (/docs) and ReDoc (/redoc). |

---
