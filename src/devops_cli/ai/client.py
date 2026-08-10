"""Unified LLM client: Ollama, Claude (Anthropic), and OpenAI-compatible APIs."""

from __future__ import annotations

import httpx2

from devops_cli.config import AIConfig
from devops_cli.http import request_timeout


class AIClientError(RuntimeError):
    """Raised when an AI provider request fails with a user-actionable message."""


class LLMClient:
    """Unified chat-completion client across AI providers."""

    def __init__(self, config: AIConfig, api_key: str | None = None) -> None:
        self._config = config
        self._api_key = api_key or ""

    def _connection_error(self, exc: Exception) -> AIClientError:
        provider = self._config.provider
        if provider == "ollama":
            base = self._config.ollama_url
            return AIClientError(
                f"Cannot connect to Ollama at {base}. "
                "Start Ollama, or run: "
                "devops ai config --provider ollama --ollama-url <url>"
            )
        if provider == "claude":
            return AIClientError(
                "Cannot connect to Claude API. Check network access and api_base_url "
                "(devops ai config --provider claude --api-base-url <url>)."
            )
        return AIClientError(
            "Cannot connect to AI provider API. Check network access, api_base_url, and API key."
        )

    # ── public API ────────────────────────────────────────────────────────────

    def chat(self, system: str, user: str) -> str:
        """Send a chat message and return the assistant reply."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama(system, user)
        if p == "claude":
            return self._claude(system, user)
        if p in ("copilot", "openai"):
            return self._openai_compat(system, user)
        raise ValueError(f"Unknown provider: {p!r}. Choose: ollama, claude, copilot, openai")

    def list_models(self) -> list[str]:
        """List available models for the current provider."""
        p = self._config.provider
        if p == "ollama":
            return self._ollama_models()
        if p in ("copilot", "openai"):
            return self._openai_models()
        return [self._config.model]

    # ── Ollama ────────────────────────────────────────────────────────────────

    def _ollama(self, system: str, user: str) -> str:
        base = self._config.ollama_url.rstrip("/")
        try:
            with httpx2.Client(timeout=request_timeout(read=300)) as c:
                r = c.post(
                    f"{base}/api/chat",
                    json={
                        "model": self._config.model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                return str(r.json()["message"]["content"])
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Ollama request failed: {exc}") from exc

    def _ollama_models(self) -> list[str]:
        base = self._config.ollama_url.rstrip("/")
        try:
            with httpx2.Client(timeout=request_timeout()) as c:
                r = c.get(f"{base}/api/tags")
                r.raise_for_status()
                return [m["name"] for m in r.json().get("models", [])]
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Failed to list Ollama models: {exc}") from exc

    # ── Anthropic Claude ──────────────────────────────────────────────────────

    def _claude(self, system: str, user: str) -> str:
        base = self._config.api_base_url or "https://api.anthropic.com"
        try:
            with httpx2.Client(timeout=request_timeout(read=300)) as c:
                r = c.post(
                    f"{base}/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self._config.model,
                        "max_tokens": 8192,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                r.raise_for_status()
                return str(r.json()["content"][0]["text"])
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Claude request failed: {exc}") from exc

    # ── OpenAI-compatible (GitHub Copilot, OpenAI, Azure OpenAI) ─────────────

    def _openai_compat(self, system: str, user: str) -> str:
        try:
            with httpx2.Client(timeout=request_timeout(read=300)) as c:
                r = c.post(
                    f"{self._api_base()}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._config.model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                    },
                )
                r.raise_for_status()
                return str(r.json()["choices"][0]["message"]["content"])
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Provider request failed: {exc}") from exc

    def _openai_models(self) -> list[str]:
        try:
            with httpx2.Client(timeout=request_timeout()) as c:
                r = c.get(
                    f"{self._api_base()}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                r.raise_for_status()
                return [m["id"] for m in r.json().get("data", [])]
        except (httpx2.ConnectError, httpx2.ConnectTimeout) as exc:
            raise self._connection_error(exc) from exc
        except httpx2.HTTPError as exc:
            raise AIClientError(f"Failed to list provider models: {exc}") from exc

    def _api_base(self) -> str:
        if self._config.api_base_url:
            return self._config.api_base_url
        if self._config.provider == "copilot":
            return "https://api.githubcopilot.com"
        return "https://api.openai.com"
