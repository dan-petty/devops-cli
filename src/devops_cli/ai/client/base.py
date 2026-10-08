"""Base provider mixin protocol and common interfaces."""

from __future__ import annotations

import re

import httpx2

from devops_cli.ai.client.models import AIClientError
from devops_cli.config.settings import AIConfig
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel, configured_level
from devops_cli.http.pool import get_shared_client


def _clean_http_error_body(raw_body: str) -> str:
    """Extract clean error text from HTTP response bodies, stripping HTML markup and title tags."""
    if not raw_body:
        return ""
    clean = raw_body.strip()
    if any(tag in clean.lower() for tag in ("<html", "<!doctype", "<head", "<body", "<div")):
        title_match = re.search(r"<title[^>]*>(.*?)</title>", clean, re.IGNORECASE)
        if title_match:
            title_text = title_match.group(1).strip()
            if title_text:
                return f"({title_text})"
        stripped = re.sub(r"<[^>]+>", " ", clean).strip()
        stripped = " ".join(stripped.split())
        return f"({stripped[:120]})" if stripped else "(HTML error response)"
    return clean[:256].replace("\n", " ")


class BaseLLMProviderMixin:
    """Base mixin declaring common client properties and methods for provider backends."""

    _config: AIConfig
    _api_key: str
    _ollama_thinking_supported: bool | None
    _request_timeout_seconds: float | None

    @property
    def backend_type(self) -> str:
        raise NotImplementedError

    @property
    def backend_host(self) -> str:
        raise NotImplementedError

    def _validate_base_url(self, base_url: str, purpose: str = "API") -> str:
        raise NotImplementedError

    def _request_timeout(self) -> httpx2.Timeout:
        raise NotImplementedError

    def _max_attempts(self) -> int:
        """Attempts per request: the configured `max_retries` plus the first, or five."""
        cfg = getattr(self, "_config", None)
        retries = getattr(cfg, "max_retries", None) if cfg is not None else None
        return int(retries) + 1 if retries is not None and int(retries) >= 0 else 5

    def _egress_level(self) -> EgressLevel:
        """The provider's URL comes from configuration: loopback, or private with the flag."""
        return configured_level(self._config)

    def _create_http_client(self, timeout: httpx2.Timeout | None = None) -> httpx2.Client:
        """Create a client of its own with the standard timeout and the native retry transport.

        The factory builds it at the configured egress level; an error building it is raised,
        never answered with a client that skips the check.
        """
        return new_http_client(
            level=self._egress_level(),
            timeout=timeout or self._request_timeout(),
            http2=True,
            retries=self._max_attempts(),
        )

    def _shared_client(self) -> httpx2.Client:
        """Return the pooled HTTP client for this provider.

        Inference calls were each building their own connection pool, so every request
        paid for a fresh TCP handshake and TLS negotiation -- 247 ms per request against a
        remote endpoint, against 61 ms once the connection is reused.

        The client is shared and deliberately never closed by the caller; per-request
        concerns such as timeouts are passed to the request itself.
        """
        try:
            b_type = self.backend_type
        except Exception:
            b_type = "default"
        key = f"llm:{type(self).__name__}:{b_type}"
        return get_shared_client(key, self._egress_level(), retries=self._max_attempts())

    def _format_status_error(self, exc: httpx2.HTTPError, status: int) -> AIClientError:
        """Extract response body preview for HTTP status errors."""
        detail = ""
        try:
            from devops_cli.security.sanitizer import mask_secrets

            resp = getattr(exc, "response", None)
            raw_body = resp.text if resp is not None else ""
            cleaned = _clean_http_error_body(raw_body)
            if cleaned:
                detail = f": {mask_secrets(cleaned)}"
        except Exception:
            pass
        return AIClientError(f"Provider request failed with HTTP {status}{detail}")

    def _format_network_error(self, exc: httpx2.HTTPError, failure: str) -> AIClientError:
        """Format network and transport errors with exception details."""
        from devops_cli.security.sanitizer import mask_secrets

        exc_msg = mask_secrets(str(exc)[:256])
        if exc_msg:
            return AIClientError(f"{failure} ({exc.__class__.__name__}: {exc_msg})")
        return AIClientError(failure)

    def _provider_http_error(self, exc: httpx2.HTTPError, failure: str) -> AIClientError:
        """Format informative provider HTTP error with status code and sanitized detail."""
        from devops_cli.ai.client.models import credentials_error

        status = exc.response.status_code if isinstance(exc, httpx2.HTTPStatusError) else None
        if status in (401, 403):
            provider_name = getattr(self._config, "provider", "AI")
            has_key = bool(getattr(self, "_api_key", None))
            return credentials_error(
                f"The {provider_name} provider", has_key=has_key, status=status
            )
        if status is not None:
            return self._format_status_error(exc, status)
        return self._format_network_error(exc, failure)

    def _connection_error(self, exc: Exception) -> AIClientError:
        raise NotImplementedError

    def _completion_limit(self) -> int | None:
        """Reply token limit: the smaller of the configured `max_tokens` and the call's cap."""
        from devops_cli.ai.client.network import completion_cap

        limits = [v for v in (getattr(self._config, "max_tokens", None), completion_cap.get()) if v]
        return int(min(limits)) if limits else None

    def _strip_think_blocks(self, text: str) -> str:
        raise NotImplementedError

    @classmethod
    def _load_and_increment_rr_index(cls, n: int) -> int:
        from devops_cli.ai.client.network import load_and_increment_rr_index

        return load_and_increment_rr_index(n)
