"""Throughput sweep against LLM gateway backends, run inside the gateway pod.

The inference backends admit traffic only from the gateway, so `devops ai gateway tune` runs this
module's source in an ephemeral Python container attached to the gateway pod, where it shares the
pod's network identity. It therefore uses the standard library alone: that container has none of
this project's dependencies installed.

Each deployment is measured on its own, directly through its OpenAI-compatible chat API, so the
gateway's routing does not decide which backend a request reaches. Two passes separate what the
server can do from what the model chooses to do:

- Capacity: fixed-length replies (`ignore_eos`, honoured by vLLM) at rising concurrency, as
  completion tokens per second.
- Cost: natural-length replies, as completion tokens per request.

Every request starts with a unique prefix. Identical prompts would let vLLM's prefix cache skip
prompt processing, which real review pages never get, and overstate its throughput.
"""

from __future__ import annotations

import json
import re
import statistics
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

Post = Callable[[str, dict[str, Any], float], dict[str, Any]]
Get = Callable[[str, float], tuple[int, str]]

# Provider prefixes of LiteLLM model strings whose backends speak the OpenAI chat API.
_PREFIXES = ("openai/", "ollama_chat/", "ollama/", "hosted_vllm/")


def chat_target(model: str, api_base: str) -> tuple[str, str]:
    """Return the chat completions URL and the backend's own model name for a deployment.

    vLLM's api_base already ends in /v1; Ollama's is the server root, where the OpenAI-compatible
    API lives under /v1.
    """
    name = next((model[len(p) :] for p in _PREFIXES if model.startswith(p)), model)
    base = api_base.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return f"{base}/chat/completions", name


def _server_root(api_base: str) -> str:
    base = api_base.rstrip("/")
    return base.removesuffix("/v1")


def _get_text(url: str, timeout: float) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310  # nosec B310
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except OSError, ValueError:
        return 0, ""


_VLLM_CACHE = re.compile(r"^vllm:cache_config_info\{(?P<labels>[^}]*)\}", re.MULTILINE)


def engine_info(api_base: str, get: Get = _get_text, timeout: float = 10.0) -> dict[str, Any]:
    """Identify the serving engine and, for vLLM, its KV-cache capacity in tokens."""
    root = _server_root(api_base)
    status, text = get(f"{root}/metrics", timeout)
    match = _VLLM_CACHE.search(text) if status == 200 else None
    if match:
        labels = dict(re.findall(r'(\w+)="([^"]*)"', match.group("labels")))
        blocks, size = labels.get("num_gpu_blocks", ""), labels.get("block_size", "")
        tokens = int(blocks) * int(size) if blocks.isdigit() and size.isdigit() else None
        return {"engine": "vllm", "kv_cache_tokens": tokens}
    status, _ = get(f"{root}/api/version", timeout)
    return {"engine": "ollama" if status == 200 else "unknown", "kv_cache_tokens": None}


def _post_json(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
    # The URL is a backend api_base from the gateway's own configuration, always http(s).
    request = urllib.request.Request(  # noqa: S310
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310  # nosec B310
        result: dict[str, Any] = json.load(response)
        return result


def run_level(
    url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    *,
    concurrency: int,
    total: int,
    timeout: float,
    fixed_length: bool = False,
    post: Post = _post_json,
) -> dict[str, Any]:
    """Send ``total`` requests, ``concurrency`` at a time; report rate, tokens and latency.

    ``fixed_length`` asks the server to ignore end-of-sequence and always generate
    ``max_tokens``, so the level measures the server rather than the model's verbosity.
    """
    base: dict[str, Any] = {"model": model, "max_tokens": max_tokens, "temperature": 0}
    if fixed_length:
        base["ignore_eos"] = True

    def one(_: int) -> tuple[float, int | None, str | None]:
        content = f"Request {uuid.uuid4().hex}.\n{prompt}"
        body = {**base, "messages": [{"role": "user", "content": content}]}
        start = time.monotonic()
        try:
            usage = post(url, body, timeout).get("usage") or {}
        except (OSError, ValueError) as exc:
            return time.monotonic() - start, None, f"{type(exc).__name__}: {exc}"[:200]
        return time.monotonic() - start, int(usage.get("completion_tokens") or 0), None

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        outcomes = list(pool.map(one, range(total)))
    wall = time.monotonic() - start

    succeeded = [(latency, tokens) for latency, tokens, _ in outcomes if tokens is not None]
    return {
        "concurrency": concurrency,
        "requests": total,
        "errors": total - len(succeeded),
        "wall_seconds": round(wall, 3),
        "requests_per_second": round(len(succeeded) / wall, 4) if wall > 0 else 0.0,
        "p50_latency_seconds": (
            round(statistics.median(latency for latency, _ in succeeded), 3) if succeeded else None
        ),
        "completion_tokens": sum(tokens for _, tokens in succeeded),
        "last_error": next((error for *_, error in reversed(outcomes) if error), None),
    }


def measure(
    deployments: list[dict[str, Any]],
    levels: list[int],
    rounds: int,
    prompt: str,
    max_tokens: int,
    timeout: float = 300.0,
    post: Post = _post_json,
    get: Get = _get_text,
) -> list[dict[str, Any]]:
    """Measure each deployment in turn: its engine, capacity at every level, then its cost."""
    results: list[dict[str, Any]] = []
    for deployment in deployments:
        url, name = chat_target(deployment["model"], deployment["api_base"])
        engine = engine_info(deployment["api_base"], get)
        capacity = [
            run_level(
                url,
                name,
                prompt,
                max_tokens,
                concurrency=level,
                total=level * rounds,
                timeout=timeout,
                fixed_length=True,
                post=post,
            )
            for level in levels
        ]
        cost = run_level(
            url, name, prompt, max_tokens, concurrency=1, total=rounds, timeout=timeout, post=post
        )
        results.append(
            {
                "deployment_id": deployment["deployment_id"],
                "engine": engine,
                "capacity": capacity,
                "cost": cost,
            }
        )
    return results


def main(spec_json: str) -> None:
    """Entry point for the gateway pod: print the sweep's results as JSON."""
    print(json.dumps(measure(**json.loads(spec_json))))
