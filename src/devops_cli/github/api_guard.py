"""Route-level write guard for `devops gh api` agent invocations (#5316)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from devops_cli.config.constants import (
    CONST_GH_API_DEFAULT_METHOD,
    CONST_GH_API_PARAMS_METHOD,
    CONST_GH_API_PROTECTED_ROUTES,
)
from devops_cli.core.caller import is_agent_caller
from devops_cli.exceptions.git import GitHubApiAccessRefusedError
from devops_cli.github.request_classifier import parse_gh_api_args
from devops_cli.lang import ERRORS

_IMPLICIT_POST_FLAGS = frozenset({"-f", "--raw-field", "-F", "--field", "--input"})


@dataclass(frozen=True, slots=True)
class ProtectedRouteMatch:
    """Matched protected route metadata from `CONST_GH_API_PROTECTED_ROUTES`."""

    route_class: str
    method: str
    endpoint: str
    pattern: str


def normalize_gh_api_path(endpoint: str) -> str:
    """Strip any URL scheme/host, query string, fragment, and outer slashes from `endpoint`."""
    raw = endpoint.strip()
    split_url = urlsplit(raw)
    if split_url.scheme in {"http", "https"} and split_url.netloc:
        return split_url.path.strip("/")
    return raw.partition("?")[0].partition("#")[0].strip("/")


def _is_single_wildcard(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _match_segments(pattern_parts: tuple[str, ...], path_parts: tuple[str, ...]) -> bool:
    """Return whether normalized URL segments satisfy a pattern containing literals, `*`/`{x}`, or `**`."""
    if not pattern_parts:
        return not path_parts
    head, *rest = pattern_parts
    rest_tuple = tuple(rest)
    if head == "**":
        return _match_segments(rest_tuple, path_parts) or (
            bool(path_parts) and _match_segments(pattern_parts, path_parts[1:])
        )
    if not path_parts:
        return False
    seg = path_parts[0]
    if not _is_single_wildcard(head) and seg.lower() != head.lower():
        return False
    return _match_segments(rest_tuple, path_parts[1:])


def classify_protected_route(method: str, endpoint: str) -> ProtectedRouteMatch | None:
    """Return matching protected route info if `(method, endpoint)` is protected, else `None`."""
    normalized_method = method.strip().upper()
    normalized_path = normalize_gh_api_path(endpoint)
    if not normalized_path:
        return None
    path_parts = tuple(part for part in normalized_path.split("/") if part)
    for route_class, methods, pattern in CONST_GH_API_PROTECTED_ROUTES:
        if normalized_method not in methods:
            continue
        pattern_parts = tuple(pattern.split("/"))
        if _match_segments(pattern_parts, path_parts):
            return ProtectedRouteMatch(
                route_class=route_class,
                method=normalized_method,
                endpoint=normalized_path,
                pattern=pattern,
            )
    return None


def require_gh_api_access(method: str, endpoint: str) -> None:
    """Refuse a protected mutating request when `core.caller.is_agent_caller()` is true."""
    match = classify_protected_route(method, endpoint)
    if match is None or not is_agent_caller():
        return
    raise GitHubApiAccessRefusedError(
        ERRORS.git.gh_api_agent_refused.format(
            method=match.method,
            endpoint=match.endpoint,
            route_class=match.route_class,
            pattern=match.pattern,
        ),
        method=match.method,
        endpoint=match.endpoint,
        route_class=match.route_class,
        details={"pattern": match.pattern},
    )


def _fallback_method(api_args: Sequence[str], method_override: str | None) -> str:
    if method_override:
        return method_override.strip().upper()
    if any(token in _IMPLICIT_POST_FLAGS or token.startswith(("-f=", "-F=")) for token in api_args):
        return CONST_GH_API_PARAMS_METHOD
    return CONST_GH_API_DEFAULT_METHOD


def require_gh_api_argv_access(
    api_args: Sequence[str],
    *,
    method_override: str | None = None,
    endpoint_override: str | None = None,
) -> None:
    """Resolve effective HTTP method and endpoint from `gh api` args and enforce agent write access."""
    parsed = parse_gh_api_args(api_args)
    if parsed is not None and parsed.endpoint is not None:
        method = method_override.strip().upper() if method_override else parsed.method
        require_gh_api_access(method, parsed.endpoint)
        return
    endpoint = endpoint_override or (next((arg for arg in api_args if not arg.startswith("-")), ""))
    if endpoint:
        require_gh_api_access(_fallback_method(api_args, method_override), endpoint)


__all__ = [
    "ProtectedRouteMatch",
    "classify_protected_route",
    "normalize_gh_api_path",
    "require_gh_api_access",
    "require_gh_api_argv_access",
]
