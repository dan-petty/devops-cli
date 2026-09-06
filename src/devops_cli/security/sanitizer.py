"""Universal secret masking, credential redaction, and token sanitization engine."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?:ghp_[A-Za-z0-9_]{10,}|gho_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{20,})"),
        "<masked-github-token>",
    ),
    (
        re.compile(
            r"\b(?:password|passwd|pwd)\s*[:=]\s*[\"']?(?!<masked-)[^\s\"',;]{8,}[\"']?",
            re.IGNORECASE,
        ),
        "password=<masked-password>",
    ),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "<masked-anthropic-key>"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "<masked-openai-key>"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "<masked-aws-key-id>"),
    (
        re.compile(
            r"\b(?:token|auth_token)\s*[:=]\s*[\"']?(?!<masked-)[^\s\"',;]{8,}[\"']?",
            re.IGNORECASE,
        ),
        "token=<masked-token>",
    ),
    (
        re.compile(
            r"(?:aws_secret_access_key|AWS_SECRET_ACCESS_KEY)\s*[:=]\s*[\"']?[A-Za-z0-9/+=]{40}[\"']?"
        ),
        "aws_secret_access_key=<masked-aws-secret>",
    ),
    (
        re.compile(
            r"(?:client_secret|client-secret|AZURE_CLIENT_SECRET)\s*[:=]\s*[\"']?[A-Za-z0-9_\-~.]{20,}[\"']?"
        ),
        "client_secret=<masked-client-secret>",
    ),
    (
        re.compile(
            r"(?:gcloud[- ]?auth[- ]?token|google[-\s]?service[-\s]?account|gcp_[A-Za-z0-9_]{20,})"
        ),
        "<masked-gcp-service-account>",
    ),
    (
        re.compile(
            r"\b(?:api[_-]?key|access[_-]?token|bearer[_-]?token|auth[_-]?token)\s*[:=]\s*(?:[\"'][A-Za-z0-9_\-.]{16,}[\"']|(?![\"'])[A-Za-z0-9_\-.]{20,}\b(?!\s*\())",
            re.IGNORECASE,
        ),
        "api_key=<masked-api-key>",
    ),
    (
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        "<masked-jwt>",
    ),
    (
        re.compile(
            r"((?:[:=]\s*[\"']?|\bBearer\s+|\btoken\s+|[\"']))secret_[A-Za-z0-9_]{10,}\b",
            re.IGNORECASE,
        ),
        r"\g<1><masked-secret>",
    ),
    (
        re.compile(
            r"\b(?:token|bearer|secret|password|api_key)\s+([A-Za-z0-9_\-.]{10,})\b",
            re.IGNORECASE,
        ),
        "<masked-token>",
    ),
    (
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_-]+\s+)?PRIVATE KEY-----"
            r"[\s\S]+?-----END (?:[A-Z0-9_-]+\s+)?PRIVATE KEY-----"
        ),
        "<masked-private-key>",
    ),
    (
        re.compile(r"https?://[^:\s]+:([^@\s]+)@"),
        "https://<masked-user>:<masked-password>@",
    ),
    (
        re.compile(r"\b(?:hvs\.[A-Za-z0-9_-]{20,}|s\.[A-Za-z0-9]{24}|hvb\.[A-Za-z0-9_-]{20,})\b"),
        "<masked-vault-token>",
    ),
    (
        re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"),
        "<masked-gitlab-token>",
    ),
    (
        re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/_-]+"),
        "<masked-slack-webhook>",
    ),
    (
        re.compile(r"\bhf_[A-Za-z0-9]{32,}\b"),
        "<masked-huggingface-token>",
    ),
)


def mask_secrets(text: str) -> str:
    """Mask known secret patterns, tokens, and credentials in the input text."""
    if not text:
        return ""
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def mask_dict_secrets(data: Any) -> Any:
    """Recursively mask secrets in string values across dictionaries and lists."""
    if isinstance(data, dict):
        return {k: mask_dict_secrets(v) for k, v in data.items()}
    if isinstance(data, list):
        return [mask_dict_secrets(item) for item in data]
    if isinstance(data, str):
        return mask_secrets(data)
    return data


def mask_uri_credentials(uri: str) -> str:
    """Mask password or credentials in URL/URI strings while preserving scheme and host."""
    if not uri:
        return ""
    try:
        parts = urlsplit(uri)
        if parts.password:
            user = parts.username or ""
            host = parts.hostname or ""
            port = f":{parts.port}" if parts.port else ""
            netloc = f"{user}:***@{host}{port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        pass
    # Regex fallback
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", uri)
