"""Dry-run request plan builders for AI model and gateway commands.

A dry run makes zero external requests and returns the ordered PlannedRequest items.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_SERVICE,
    DEFAULT_AI_GATEWAY_URL,
    DEFAULT_AI_PREWARM_KEEP_ALIVE,
    DEFAULT_AI_TEST_PROMPT,
    DEFAULT_LLM_NAMESPACE,
)
from devops_cli.config.settings import load_settings
from devops_cli.dry_run.requests import PlannedRequest


def plan_ai_agents(repo: Path | str = Path("."), template: bool = False) -> list[PlannedRequest]:
    """Plan agent instruction file generation requests."""
    if template:
        return []
    settings = load_settings()
    provider = settings.ai.provider
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        target = f"{endpoint.rstrip('/')}/api/chat"
    else:
        base = settings.ai.api_base_url or "https://api.openai.com/v1"
        target = f"{base.rstrip('/')}/chat/completions"

    return [
        PlannedRequest(
            method="POST",
            target=target,
            stdin='{"messages": [{"role": "system", "content": "<agent-instruction-prompt>"}]}',
        )
    ]


def plan_ai_benchmark(
    models: Sequence[str] | None = None,
    servers: Sequence[str] | None = None,
    benchmark_type: str = "tasks",
) -> list[PlannedRequest]:
    """Plan AI model benchmark execution requests."""
    settings = load_settings()
    target_models = list(models) if models else [settings.ai.model]
    target_servers = (
        list(servers) if servers else (settings.ai.get_ollama_urls or ["http://localhost:11434"])
    )
    requests: list[PlannedRequest] = []

    is_embedding = benchmark_type.strip().lower() in ("embedding", "embed")
    method = "POST"
    path = "/api/embeddings" if is_embedding else "/api/chat"

    for server in target_servers:
        srv = server.rstrip("/")
        for m in target_models:
            requests.append(
                PlannedRequest(
                    method=method,
                    target=f"{srv}{path}",
                    stdin=f'{{"model": "{m}", "prompt": "<benchmark-evaluation-input>"}}',
                )
            )
    return requests


def plan_ai_chaos_model(
    mode: str = "all",
    primary_provider: str = "openai",
    primary_model: str = "gpt-4o",
    fallback_provider: str = "ollama",
    fallback_model: str = "deepseek-coder:6.7b",
) -> list[PlannedRequest]:
    """Plan model dependency chaos fault injection and fallback requests."""
    return [
        PlannedRequest(
            method="POST",
            target=f"{primary_provider}/{primary_model}",
            stdin='{"prompt": "<chaos-test-prompt>"}',
        ),
        PlannedRequest(
            method="POST",
            target=f"{fallback_provider}/{fallback_model}",
            stdin='{"prompt": "<chaos-test-prompt>"}',
            condition=f"on {primary_provider} simulated {mode} fault",
        ),
    ]


def plan_ai_chat(
    persona: str = "architect",
    model: str | None = None,
) -> list[PlannedRequest]:
    """Plan interactive chat completion request."""
    settings = load_settings()
    provider = settings.ai.provider
    chosen_model = model or settings.ai.model
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        target = f"{endpoint.rstrip('/')}/api/chat"
    else:
        base = settings.ai.api_base_url or "https://api.openai.com/v1"
        target = f"{base.rstrip('/')}/chat/completions"

    return [
        PlannedRequest(
            method="POST",
            target=target,
            stdin=f'{{"model": "{chosen_model}", "persona": "{persona}", "messages": "<chat-turn>"}}',
        )
    ]


def plan_ai_gateway_connect(
    context: str | None = None,
    namespace: str = DEFAULT_LLM_NAMESPACE,
    service: str = DEFAULT_AI_GATEWAY_SERVICE,
) -> list[PlannedRequest]:
    """Plan discovering LLM gateway NodePort and probing its health."""
    from devops_cli.config.commands import build_kubectl_cmd

    k8s_argv = tuple(
        build_kubectl_cmd(
            ["get", "service", service, "-n", namespace, "-o", "json"],
            context=context,
        )
    )
    return [
        PlannedRequest(
            method="kubectl",
            target=f"services/{namespace}/{service}",
            argv=k8s_argv,
        ),
        PlannedRequest(
            method="GET",
            target="http://<node-ip>:<node-port>/health/liveliness",
        ),
        PlannedRequest(
            method="GET",
            target="http://<node-ip>:<node-port>/model/info",
        ),
    ]


def plan_ai_gateway_load(window: str = "1h") -> list[PlannedRequest]:
    """Plan Prometheus query for gateway pool load metrics."""
    settings = load_settings()
    prom_url = (settings.prometheus.url or "http://prometheus.monitoring:9090").rstrip("/")
    return [
        PlannedRequest(
            method="GET",
            target=f"{prom_url}/api/v1/query",
            stdin=f"query=litellm_deployment_total_requests_total&window={window}",
        )
    ]


def plan_ai_gateway_probe_backend(
    backend: str,
    backend_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan direct probe request to inference backend."""
    target = (backend_url or f"http://{backend}.local").rstrip("/") + "/health"
    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def _resolve_gateway_base(gateway_url: str | None) -> str:
    settings = load_settings()
    raw = gateway_url or settings.ai.gateway_url or DEFAULT_AI_GATEWAY_URL
    return raw.removesuffix("/v1").rstrip("/")


def plan_ai_gateway_routes(gateway_url: str | None = None) -> list[PlannedRequest]:
    """Plan model info query to LLM gateway."""
    base = _resolve_gateway_base(gateway_url)
    return [
        PlannedRequest(
            method="GET",
            target=f"{base}/model/info",
        )
    ]


def plan_ai_gateway_status(gateway_url: str | None = None) -> list[PlannedRequest]:
    """Plan health status probe to LLM gateway."""
    base = _resolve_gateway_base(gateway_url)
    return [
        PlannedRequest(
            method="GET",
            target=f"{base}/health",
        )
    ]


def plan_ai_gateway_tune(
    model: str = "devops-default",
    gateway_url: str | None = None,
) -> list[PlannedRequest]:
    """Plan gateway hardware capacity and latency sweep requests."""
    base = _resolve_gateway_base(gateway_url)
    return [
        PlannedRequest(
            method="POST",
            target=f"{base}/chat/completions",
            repeat=f"concurrency sweep for model group '{model}'",
        )
    ]


def plan_ai_models() -> list[PlannedRequest]:
    """Plan listing available models from configured AI provider."""
    settings = load_settings()
    provider = settings.ai.provider
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        target = f"{endpoint.rstrip('/')}/api/tags"
    else:
        base = settings.ai.api_base_url or "https://api.openai.com/v1"
        target = f"{base.rstrip('/')}/models"

    return [
        PlannedRequest(
            method="GET",
            target=target,
        )
    ]


def plan_ai_pipeline(
    prompt: str,
    personas: Sequence[str],
    stage_context_tokens: int | None = None,
) -> list[PlannedRequest]:
    """Plan multi-agent pipeline prompt execution requests."""
    settings = load_settings()
    provider = settings.ai.provider
    if provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        target = f"{endpoint.rstrip('/')}/api/chat"
    else:
        base = settings.ai.api_base_url or "https://api.openai.com/v1"
        target = f"{base.rstrip('/')}/chat/completions"

    return [
        PlannedRequest(
            method="POST",
            target=target,
            stdin=(
                f'{{"persona": "{p}", "prompt": "<stage-context>", "stage_context_tokens": {stage_context_tokens}}}'
                if stage_context_tokens is not None
                else f'{{"persona": "{p}", "prompt": "<stage-context>"}}'
            ),
            repeat=f"for persona '{p}'",
        )
        for p in personas
    ]


def plan_ai_preload() -> list[PlannedRequest]:
    """Plan preloading configured model into VRAM across all configured Ollama servers."""
    settings = load_settings()
    servers = settings.ai.get_ollama_urls or ["http://localhost:11434"]
    model = settings.ai.model
    return [
        PlannedRequest(
            method="POST",
            target=f"{s.rstrip('/')}/api/generate",
            stdin=f'{{"model": "{model}", "keep_alive": -1}}',
        )
        for s in servers
    ]


def plan_ai_prewarm(
    model: str | None = None,
    keep_alive: str | int = DEFAULT_AI_PREWARM_KEEP_ALIVE,
    urls: Sequence[str] | None = None,
) -> list[PlannedRequest]:
    """Plan prewarming or evicting models across target Ollama servers."""
    settings = load_settings()
    target_model = model or settings.ai.model
    target_servers = (
        list(urls) if urls else (settings.ai.get_ollama_urls or ["http://localhost:11434"])
    )
    return [
        PlannedRequest(
            method="POST",
            target=f"{s.rstrip('/')}/api/generate",
            stdin=f'{{"model": "{target_model}", "keep_alive": "{keep_alive}"}}',
        )
        for s in target_servers
    ]


def plan_ai_prompt_eval(
    producer: str = "devsecops",
    dataset: Path | str | None = None,
) -> list[PlannedRequest]:
    """Plan review verdict evaluation and run recording requests."""
    settings = load_settings()
    requests: list[PlannedRequest] = []
    if settings.valkey.url:
        requests.append(
            PlannedRequest(
                method="valkey",
                target=f"SET devops:ai:run:prompt-eval:{producer}",
            )
        )
    return requests


def plan_ai_test(
    prompt: str = DEFAULT_AI_TEST_PROMPT,
    url: str | None = None,
) -> list[PlannedRequest]:
    """Plan sending a test prompt to verify AI provider connectivity."""
    settings = load_settings()
    provider = settings.ai.provider
    if url:
        target = f"{url.rstrip('/')}/api/chat"
    elif provider == "ollama":
        endpoint = (settings.ai.get_ollama_urls or ["http://localhost:11434"])[0]
        target = f"{endpoint.rstrip('/')}/api/chat"
    else:
        base = settings.ai.api_base_url or "https://api.openai.com/v1"
        target = f"{base.rstrip('/')}/chat/completions"

    return [
        PlannedRequest(
            method="POST",
            target=target,
            stdin=f'{{"prompt": "{prompt}"}}',
        )
    ]
