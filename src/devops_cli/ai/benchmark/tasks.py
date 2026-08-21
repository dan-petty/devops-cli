"""Standard built-in benchmark tasks, evaluation rubrics, and reference criteria."""

from __future__ import annotations

from devops_cli.models.benchmark import BenchmarkTask

BENCHMARK_TASKS: list[BenchmarkTask] = [
    BenchmarkTask(
        id="sec-ssrf-remediation",
        title="Zero-Trust SSRF Validation & Webhook Dispatcher Remediation",
        category="security",
        prompt=(
            "Review and remediate the following Python HTTP webhook dispatcher against "
            "Server-Side Request Forgery (SSRF) and DNS rebinding attacks.\n\n"
            "```python\n"
            "import httpx\n\n"
            "def dispatch_webhook(url: str, payload: dict) -> int:\n"
            "    # Sends a webhook notification\n"
            "    with httpx.Client() as client:\n"
            "        resp = client.post(url, json=payload, timeout=10.0)\n"
            "        return resp.status_code\n"
            "```\n\n"
            "Provide the complete hardened Python 3.14+ implementation using `httpx` or "
            "standard library `ipaddress`/`urllib.parse`."
        ),
        expected_solution=(
            "1. URL parsing via `urllib.parse.urlparse` checking scheme is strictly "
            "'http' or 'https'.\n"
            "2. Host resolution to IP addresses with `socket.getaddrinfo` to prevent "
            "DNS rebinding.\n"
            "3. Checking all resolved IPs using `ipaddress.ip_address` to reject "
            "private/loopback/link-local ranges (e.g. 10.0.0.0/8, 172.16.0.0/12, "
            "192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1, fc00::/7).\n"
            "4. Configurable explicit timeout and redirect disabling or safe redirect "
            "validation.\n"
            "5. Proper exception handling for DNS resolution failures and network timeouts."
        ),
        evaluation_rubric=(
            "- Accuracy (0-10): Correct IP and URL parsing logic without syntax errors.\n"
            "- Security (0-10): Completely blocks 127.0.0.1, localhost, AWS metadata "
            "169.254.169.254, RFC1918 private IPs, IPv6 mapped IPv4.\n"
            "- Completeness (0-10): Handles DNS rebinding (pinning IP in transport or "
            "pre-resolving), redirect protection.\n"
            "- Clarity (0-10): Clean Python type annotations, docstring, defensiveness."
        ),
        weight=1.5,
    ),
    BenchmarkTask(
        id="k8s-pod-security-standards",
        title="Kubernetes Deployment Hardening for Restricted Pod Security Standards",
        category="kubernetes",
        prompt=(
            "Harden the following vulnerable Kubernetes Deployment manifest to comply with the "
            "Kubernetes Restricted Pod Security Standard (PSS/PSA):\n\n"
            "```yaml\n"
            "apiVersion: apps/v1\n"
            "kind: Deployment\n"
            "metadata:\n"
            "  name: payment-api\n"
            "  namespace: production\n"
            "spec:\n"
            "  replicas: 3\n"
            "  selector:\n"
            "    matchLabels:\n"
            "      app: payment-api\n"
            "  template:\n"
            "    metadata:\n"
            "      labels:\n"
            "        app: payment-api\n"
            "    spec:\n"
            "      containers:\n"
            "      - name: api\n"
            "        image: payment-api:v1.2.0\n"
            "        ports:\n"
            "        - containerPort: 8080\n"
            "```\n\n"
            "Output the complete, production-ready YAML manifest."
        ),
        expected_solution=(
            "1. `spec.template.spec.securityContext` configured with:\n"
            "   - `runAsNonRoot: true`\n"
            "   - `runAsUser: 10001` (or non-zero UID)\n"
            "   - `runAsGroup: 10001`\n"
            "   - `seccompProfile.type: RuntimeDefault`\n"
            "2. `container.securityContext` configured with:\n"
            "   - `allowPrivilegeEscalation: false`\n"
            "   - `readOnlyRootFilesystem: true`\n"
            "   - `capabilities.drop: ['ALL']`\n"
            "3. Resource requests and limits defined (cpu, memory).\n"
            "4. Liveness and readiness probes configured.\n"
            "5. Temporary writable emptyDir volume mounted for `/tmp` if needed."
        ),
        evaluation_rubric=(
            "- Accuracy (0-10): Valid Kubernetes YAML syntax and schema adherence.\n"
            "- Security (0-10): Meets all Restricted PSS constraints (drop ALL capabilities, "
            "readOnlyRootFilesystem, runAsNonRoot, seccomp RuntimeDefault, "
            "allowPrivilegeEscalation false).\n"
            "- Completeness (0-10): Probes, resource constraints, emptyDir mounts included.\n"
            "- Clarity (0-10): Clear structure and YAML formatting."
        ),
        weight=1.2,
    ),
    BenchmarkTask(
        id="arch-pydantic-v2-migration",
        title="Modern Python 3.14+ & Pydantic v2 Architectural Migration",
        category="architecture",
        prompt=(
            "Refactor this legacy dictionary-based configuration loader to modern Python 3.14+ "
            "using Pydantic v2 (`pydantic.BaseModel`, `Field`, `model_validator`, "
            "strict typing):\n\n"
            "```python\n"
            "class ServerConfig:\n"
            "    def __init__(self, data: dict):\n"
            "        self.host = data.get('host', '127.0.0.1')\n"
            "        self.port = int(data.get('port', 8080))\n"
            "        self.ssl_enabled = bool(data.get('ssl_enabled', False))\n"
            "        self.cert_path = data.get('cert_path')\n"
            "        if self.ssl_enabled and not self.cert_path:\n"
            "            raise Exception('cert_path required when ssl is on')\n"
            "```\n\n"
            "Ensure immutability (frozen), type validation, environment variable parsing "
            "capability, and clean error messages."
        ),
        expected_solution=(
            "1. Inherits from `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`.\n"
            "2. Type annotations with modern Python syntax (`str`, `int`, `bool`, `Path | None`).\n"
            "3. Validation: `Field(ge=1, le=65535)` on port.\n"
            "4. `@model_validator(mode='after')` verifying `cert_path is not None` when "
            "`ssl_enabled is True` with `ValueError`.\n"
            "5. Clean default values and documentation docstrings."
        ),
        evaluation_rubric=(
            "- Accuracy (0-10): Proper Pydantic v2 idioms (model_validator, ConfigDict, Field).\n"
            "- Security (0-10): Port boundary enforcement, robust type safety, zero silent "
            "failures.\n"
            "- Completeness (0-10): Immutability, validators, modern union types.\n"
            "- Clarity (0-10): Idiomatic, readable code."
        ),
        weight=1.0,
    ),
    BenchmarkTask(
        id="ci-concurrency-triage",
        title="GitHub Actions Workflow Race Condition & Multi-Job Triage",
        category="ci_cd",
        prompt=(
            "Analyze the following GitHub Actions workflow snippet that exhibits intermittent "
            "deployment race conditions and duplicate concurrent deployments to staging:\n\n"
            "```yaml\n"
            "name: Deploy Staging\n"
            "on:\n"
            "  push:\n"
            "    branches: [ 'feat/*', 'release/*' ]\n"
            "jobs:\n"
            "  deploy:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "    - uses: actions/checkout@v4\n"
            "    - run: ./deploy.sh staging\n"
            "```\n\n"
            "Identify the concurrency issues and provide a corrected, robust workflow with proper "
            "concurrency groups, cancel-in-progress semantics, and minimum permission principles "
            "(least privilege)."
        ),
        expected_solution=(
            "1. Add `concurrency` block keyed by workflow and branch/ref:\n"
            "   `concurrency: { group: ${{ github.workflow }}-${{ github.ref }}, "
            "cancel-in-progress: true }`.\n"
            "2. Add top-level `permissions` block enforcing least privilege (e.g. "
            "`contents: read`, `id-token: write`).\n"
            "3. Action version pinning or secure SHA references.\n"
            "4. Explicit error handling and timeout bounds (`timeout-minutes`)."
        ),
        evaluation_rubric=(
            "- Accuracy (0-10): Correct GitHub Actions syntax and concurrency expression.\n"
            "- Security (0-10): Permissions least privilege, timeout guards.\n"
            "- Completeness (0-10): Explains both the race condition cause and full remediation.\n"
            "- Clarity (0-10): High signal-to-noise ratio in analysis."
        ),
        weight=1.1,
    ),
]


def get_benchmark_tasks(categories: list[str] | None = None) -> list[BenchmarkTask]:
    """Retrieve benchmark tasks optionally filtered by category name."""
    if not categories:
        return list(BENCHMARK_TASKS)
    cat_set = {c.lower() for c in categories}
    return [t for t in BENCHMARK_TASKS if t.category.lower() in cat_set or t.id.lower() in cat_set]
