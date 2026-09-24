"""Universal secret masking, credential redaction, and token sanitization engine."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# The keyword patterns below match a word following "secret", "token" or "password". In
# prose that word is usually English: "unify secret resolution" was rewritten to "unify
# <masked-token>", and that corruption reached published release descriptions before anyone
# noticed, because the changelog is masked on its way out. A credential is distinguishable
# from a word -- it carries a digit, a capital, or a separator, or it is longer than any
# English word -- so the value is inspected rather than assumed.
_CREDENTIAL_MIN_OPAQUE_LENGTH = 24


def _looks_like_a_credential(value: str) -> bool:
    """Report whether a value following a credential keyword is plausibly a secret.

    Treating any uppercase letter as a credential signal was wrong: an ordinary word is
    capitalised at the start of a sentence or in a heading. "Secret Resolution" and "Token
    Governance" were rewritten to "Secret <masked-token>" and "Token <masked-token>" in the
    published v0.2.22 release description for exactly that reason, because the first fix
    for this was tested only against lowercase prose.

    A leading capital marks a word. An internal capital, a digit, a separator, or a length
    no English word reaches marks a token.
    """
    if len(value) >= _CREDENTIAL_MIN_OPAQUE_LENGTH:
        return True
    if any(char.isdigit() or char in "_-." for char in value):
        return True
    return any(char.isupper() for char in value[1:])


def _mask_credential_like_value(match: re.Match[str]) -> str:
    """Replace a keyword-prefixed value only when it looks like a credential."""
    value = match.group(1)
    if not _looks_like_a_credential(value):
        return match.group(0)
    return match.group(0).replace(value, "<masked-token>")


# A replacement is a literal for a pattern whose whole match is the secret, or a
# callable where the match also covers surrounding text that must survive.
_Replacement = str | Callable[[re.Match[str]], str]

# A value that is code rather than a credential: a call, index or collection expression, or a
# dotted attribute path (`hashlib.md5(pw).hexdigest()`, `os.environ[...]`, `req.query.token`).
_CODE_VALUE = re.compile(r"[(\[{]|^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$")


def _mask_literal(match: re.Match[str], masked: str) -> str:
    """Mask an assigned credential, leaving an unquoted code expression as written.

    Rewriting code before review hides defects: an MD5-hashed password or a token read from
    the query string turn into what look like harmless redactions.
    """
    if not match.group("quote") and _CODE_VALUE.search(match.group("value")):
        return match.group(0)
    return masked


_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], _Replacement], ...] = (
    (
        re.compile(
            r"(?<![a-zA-Z0-9<])(?:ghp_[A-Za-z0-9_]{10,}|gho_[A-Za-z0-9_]{10,}|github_pat_[A-Za-z0-9_]{20,})\b"
        ),
        "<masked-github-token>",
    ),
    (
        re.compile(
            r"\b(?:password|passwd|pwd)\s*[:=]\s*(?P<quote>[\"']?)(?!<masked-)"
            r"(?P<value>[^\s\"',;]{8,})[\"']?",
            re.IGNORECASE,
        ),
        lambda match: _mask_literal(match, "password=<masked-password>"),
    ),
    (
        re.compile(
            r"(?<![a-zA-Z0-9/\\<])(?<!task-)(?<!subtask-)sk-ant-[A-Za-z0-9_-]{19,}[A-Za-z0-9]\b"
        ),
        "<masked-anthropic-key>",
    ),
    (
        re.compile(
            r"(?<![a-zA-Z0-9/\\<])(?<!task-)(?<!subtask-)sk-(?!ant-)[A-Za-z0-9_-]{19,}[A-Za-z0-9]\b"
        ),
        "<masked-openai-key>",
    ),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "<masked-aws-key-id>"),
    (
        re.compile(
            r"\b(?:token|auth_token)\s*[:=]\s*(?P<quote>[\"']?)(?!<masked-)"
            r"(?P<value>[^\s\"',;]{8,})[\"']?",
            re.IGNORECASE,
        ),
        lambda match: _mask_literal(match, "token=<masked-token>"),
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
            r"\b(?:gcloud[- ]?auth[- ]?token|google[-\s]?service[-\s]?account|gcp_[A-Za-z0-9_]{20,})"
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
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
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
        _mask_credential_like_value,
    ),
    (
        re.compile(
            r"-----BEGIN (?:[A-Z0-9_-]+\s+)?PRIVATE KEY-----"
            r"[\s\S]+?-----END (?:[A-Z0-9_-]+\s+)?PRIVATE KEY-----"
        ),
        # Keep the key's line count, so line numbers after it still match the file.
        lambda match: "<masked-private-key>" + "\n" * match.group(0).count("\n"),
    ),
    (
        # user:password@ only; "host:8080/path?email=a@b.com" holds no credentials.
        re.compile(r"https?://[^:/\s@]+:[^@/\s?#]+@"),
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


def redact_text(text: str) -> str:
    """Sanitize and redact known credential and secret patterns in the input text."""
    if not text:
        return ""
    result = text
    for pattern, replacement in _SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def mask_secrets(text: str) -> str:
    """Mask known secret patterns, tokens, and credentials in the input text."""
    return redact_text(text)


sanitize_secrets = mask_secrets


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
            netloc = f"{user}:***@{host}{port}" if user else f"***@{host}{port}"
            return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except ValueError, TypeError, AttributeError:
        pass
    # Regex fallback
    return re.sub(
        r"://([^:]*):([^@]+)@",
        lambda m: f"://{m.group(1)}:***@" if m.group(1) else "://***@",
        uri,
    )


_SENSITIVE_ARG_FLAGS: frozenset[str] = frozenset(
    {"--password", "-p", "--token", "--api-key", "--secret", "--auth-token"}
)
_SENSITIVE_ARG_PREFIXES: tuple[str, ...] = (
    "--password=",
    "-p=",
    "--token=",
    "--api-key=",
    "--secret=",
    "--auth-token=",
)


def sanitize_command_args_for_display(command: list[str]) -> list[str]:
    """Mask sensitive argument values in command list before terminal printing."""
    sanitized: list[str] = []
    skip_next = False
    for arg in command:
        if skip_next:
            sanitized.append("<masked>")
            skip_next = False
            continue
        if arg in _SENSITIVE_ARG_FLAGS:
            sanitized.append(arg)
            skip_next = True
        elif any(arg.startswith(prefix) for prefix in _SENSITIVE_ARG_PREFIXES):
            key = arg.split("=", 1)[0]
            sanitized.append(f"{key}=<masked>")
        else:
            sanitized.append(mask_secrets(arg))
    return sanitized


def sanitize_telemetry_endpoint(endpoint: str) -> str:
    """Sanitize OTLP collector URL to prevent leaking internal network topology and credentials."""
    if not endpoint:
        return ""
    try:
        parsed = urlsplit(endpoint)
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port is not None else ""

        if host in ("localhost", "127.0.0.1", "::1"):
            clean_host = host
        else:
            try:
                import ipaddress

                ip = ipaddress.ip_address(host)
                clean_host = "<internal-ip>" if (ip.is_private or ip.is_loopback) else host
            except ValueError:
                clean_host = host

        clean_netloc = f"{clean_host}{port}"
        return parsed._replace(netloc=clean_netloc).geturl()
    except ValueError, TypeError, AttributeError:
        return "<internal-endpoint>"


_PROMPT_BOUNDARY_TAGS: tuple[str, ...] = (
    "target_code_to_review",
    "untrusted_code_diff",
    "project_conventions_context",
    "untrusted_segment_content",
    "untrusted_finding_excerpts",
    "untrusted_findings_input",
    "untrusted_segment_outputs",
    "review_metadata_context",
    "untrusted_related_files",
    "instruction",
    "instructions",
    "system",
    "prompt",
)


def sanitize_prompt_boundary_tags(text: str) -> str:
    """Sanitize XML-style boundary opening and closing tags in untrusted content."""
    if not text:
        return ""
    sanitized = text
    for tag in _PROMPT_BOUNDARY_TAGS:
        sanitized = sanitized.replace(f"<{tag}>", f"&lt;{tag}&gt;")
        sanitized = sanitized.replace(f"<{tag} ", f"&lt;{tag} ")
        sanitized = sanitized.replace(f"</{tag}>", f"&lt;/{tag}&gt;")
    return sanitized


def sanitize_prompt_injection(text: str) -> str:
    """Scrub prompt injection tags from dynamically interpolated templates or prompt inputs."""
    if not text:
        return ""
    from devops_cli.config.constants import CONST_PROMPT_INJECTION_TAGS_RE

    return CONST_PROMPT_INJECTION_TAGS_RE.sub("", text)
