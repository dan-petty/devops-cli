# Knowledge Base: FastAPI & Uvicorn (REST Engine & OpenAPI Service)

## 1. Overview & Purpose

FastAPI is a modern, high-performance web framework for building APIs with Python based on standard Python type hints and Pydantic v2. Uvicorn is a lightning-fast ASGI web server implementation. In the `devops-cli` ecosystem, FastAPI and Uvicorn power the local workstation REST engine (`devops serve` / `src/devops_cli/server`), exposing OpenAPI interactive documentation, workstation health probes, child workspace discovery, and Prometheus metrics.

---

## 2. Usage Information & Architecture

- **Application Factory Pattern**: `src/devops_cli/server/app.py` exposes `create_app()` constructing the FastAPI instance with CORS middleware, OpenTelemetry request tracing, process timing headers (`X-Process-Time`), and version headers (`X-DevOps-Version`).
- **Endpoint Structure**:
  - `GET /`: Service metadata, documentation links, and uptime.
  - `GET /health`, `GET /healthz`: Health and liveness probes.
  - `GET /api/v1/status`: Workstation toolchain availability (`uv`, `docker`, `kubectl`, `helm`, `minikube`, `tofu`, `ollama`, `gh`), Python runtime, and OTel status.
  - `GET /api/v1/workspaces`: Bounded child repository discovery (2-level traversal).
  - `GET /api/v1/config`: Sanitized configuration inspector with automatic secret redaction.
  - `GET /api/v1/telemetry`: OpenTelemetry collector connectivity probe.
  - `GET /metrics`: Prometheus metrics scrape endpoint.
- **OpenAPI & Interactive Docs**:
  - `/docs`: Interactive Swagger UI.
  - `/redoc`: ReDoc API documentation.
  - `/openapi.json`: Exportable OpenAPI v3.1 schema.
- **CLI Subcommand**: `devops serve` launches the Uvicorn server with options `--host`, `--port`, `--reload`, `--workers`, `--log-level`, and `--docs/--no-docs`.

---

## 3. Common & Advanced Commands

### DevOps CLI REST Server Commands
```bash
# Launch DevOps CLI REST service on default port 8000
devops serve

# Launch on specific port with reload enabled
devops serve --host 127.0.0.1 --port 8080 --reload

# Launch in production mode without Swagger docs and 4 worker processes
devops serve --no-docs --workers 4 --log-level warning
```

### Direct HTTP Invocations via `curl`
```bash
# Query health probe
curl -s http://localhost:8000/health | jq .

# Inspect workstation toolchain status
curl -s http://localhost:8000/api/v1/status | jq .

# List discovered workspaces
curl -s http://localhost:8000/api/v1/workspaces | jq .

# Scrape Prometheus metrics series
curl -s http://localhost:8000/metrics

# Download raw OpenAPI schema definition
curl -s http://localhost:8000/openapi.json > openapi.json
```

---

## 4. Best Practice Guidance

1. **Strict Type Annotations**: All FastAPI route functions and dependency injections must declare complete type annotations (`mypy --strict`).
2. **Pydantic Response Models**: Always use Pydantic models for request and response serialization (`response_model=HealthResponse`) to ensure schema validation and automatic OpenAPI generation.
3. **Bounded Filesystem Scanning**: Never use recursive `.rglob("*")` inside API handlers; always use bounded 2-level traversal (`Path.iterdir()`) with directory skip lists (`.git`, `.venv`, `node_modules`).
4. **Non-Blocking Handlers**: Use standard `async def` route handlers for asynchronous I/O and synchronous `def` handlers when delegating to CPU-bound functions.

---

## 5. Security Recommendations & Zero-Trust Policies

- **Token Redaction**: The `/api/v1/config` endpoint must always mask secrets (`<masked-github-token>`, `<masked-ai-key>`).
- **Default Bind Address**: Default binding is `127.0.0.1` (localhost) to prevent accidental public exposure of workstation status APIs.
- **CORS Policies**: Explicitly define permitted CORS origins; never allow wildcard origins (`"*"`) in authenticated environments.

---

## 6. General Standards & Reference Guidelines

- **Version Alignment**: FastAPI `>=0.110.0`, Uvicorn `>=0.30.0`, Pydantic `>=2.10.0`.
- **Custom Headers**: Standard headers `X-Process-Time` (latency in seconds) and `X-DevOps-Version` (installed CLI semver).
