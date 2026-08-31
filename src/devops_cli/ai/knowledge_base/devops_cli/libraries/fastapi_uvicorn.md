# Code Library: FastAPI & Uvicorn (REST API & ASGI Service Engine)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [fastapi.tiangolo.com](https://fastapi.tiangolo.com/) • [uvicorn.org](https://www.uvicorn.org/) |
| **Public Git Repository** | [github.com/fastapi/fastapi](https://github.com/fastapi/fastapi) • [github.com/encode/uvicorn](https://github.com/encode/uvicorn) |
| **Official PyPI Package** | [pypi.org/project/fastapi](https://pypi.org/project/fastapi/) (`0.141.1`) • [pypi.org/project/uvicorn](https://pypi.org/project/uvicorn/) (`0.52.4`) |
| **DevOps CLI Integration** | [`src/devops_cli/server/`](file:///workspaces/devops-cli/src/devops_cli/server/) • [`src/devops_cli/commands/serve.py`](file:///workspaces/devops-cli/src/devops_cli/commands/serve.py) |

---

## 2. General Information & Architecture

**FastAPI** is a modern, high-performance web framework for building APIs with Python based on standard Python type hints and Pydantic. **Uvicorn** is a lightning-fast ASGI (Asynchronous Server Gateway Interface) web server implementation for Python based on `uvloop` and `httptools`.

In `devops-cli`:
- **Workstation API Engine**: Powers `devops serve`, providing local HTTP endpoints for remote orchestration, IDE sidecars, and background monitoring.
- **Auto-Generated Documentation**: Exposes interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) generated from Pydantic schemas.
- **Health Probes & Metrics**: Implements `/healthz`, `/status`, and Prometheus metrics scraping endpoints (`/metrics`).

---

## 3. Comparable Projects & Tradeoffs

| Framework | Strengths | Weaknesses | Why `devops-cli` Chose FastAPI + Uvicorn |
| :--- | :--- | :--- | :--- |
| **`fastapi` + `uvicorn`** | Async/await native, automatic OpenAPI/Swagger generation, 100% Pydantic data validation, high throughput. | Requires understanding async event loops. | **Selected**: The definitive modern standard for Python microservices and REST APIs. |
| **`flask`** | Simple, mature, huge community. | Synchronous by default, lacks automatic OpenAPI generation, manual Pydantic wiring required. | Rejected: FastAPI offers built-in OpenAPI schemas and async concurrency out of the box. |
| **`django` / `django-ninja`** | Full-featured monolithic framework with ORM and admin. | Massive footprint, unnecessary database overhead for a lightweight CLI service engine. | Rejected: Too heavy for an embedded developer tooling server. |
| **`aiohttp` (Server)** | Pure async HTTP server. | Manual schema validation, lacks integrated Swagger UI documentation out of the box. | Rejected: FastAPI provides superior OpenAPI and Pydantic integration. |

---

## 4. Key Concepts & Core Patterns

1. **`FastAPI` Application**: Central router mounted with CORS middleware, lifespan events, and OpenTelemetry instrumentation:
   ```python
   from fastapi import FastAPI

   app = FastAPI(title="DevOps CLI Service Engine", version="0.2.5")
   ```
2. **Typed Route Handlers**: Uses Pydantic request bodies and query parameters with automatic validation.
3. **ASGI Lifecycle Execution**: `uvicorn.run(app, host="127.0.0.1", port=8000)` manages the asynchronous event loop and graceful shutdown signals (SIGINT/SIGTERM).

---

## 5. Common & Advanced Usage Examples

### REST Endpoint Route Implementation
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()


class HealthResponse(BaseModel):
    status: str
    version: str


@app.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Kubernetes liveness and readiness probe endpoint."""
    return HealthResponse(status="healthy", version="0.2.5")
```

### Launching the REST Service via CLI
```bash
# Launch background service engine on default port 8000
devops serve

# Launch on custom port with automatic hot-reload
devops serve --port 8080 --reload
```

---

## 6. Best Practices & Security Standards

1. **Loopback Binding by Default**: Always bind `devops serve` to `127.0.0.1` unless explicitly instructed to permit non-loopback network interfaces (`--host 0.0.0.0`).
2. **Disable Docs in Production**: Support toggling Swagger UI via `--docs/--no-docs` for hardened environments.
3. **Graceful Signal Handling**: Ensure Uvicorn flushes OpenTelemetry spans and in-memory caches upon receiving SIGTERM.
