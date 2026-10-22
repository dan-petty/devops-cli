"""Semgrep registry rulesets cached in the user data root by `devops review rules fetch` (#1144).

A registry ruleset such as `p/default` is downloaded into `<user data root>/semgrep/<slug>.yaml`,
byte for byte as the registry answered, with the ETag it answered with in `<slug>.etag` beside it.
The next fetch sends that ETag as `If-None-Match`, and a 304 leaves both files as they are, so the
2.5 MB ruleset is downloaded again only when it has changed. The registry answers a client that
accepts gzip, as this one does, with the ruleset as JSON and any other client with YAML. JSON is a
YAML document, and Semgrep reads either under the `.yaml` name.

Both files are written atomically, the ruleset first. A run that stops between the two leaves a
ruleset with the ETag of an older one, or none, which the registry does not answer with a 304, so
an interrupted fetch costs one download.
"""

from __future__ import annotations

import os
from http import HTTPStatus
from pathlib import Path
from typing import NamedTuple
from urllib.parse import quote

import httpx2
import yaml

from devops_cli.config.commands import BIN_SEMGREP
from devops_cli.config.constants import (
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_SEMGREP_REGISTRY_CACHE_DIRNAME,
    CONST_SEMGREP_REGISTRY_RULESET_KINDS,
    CONST_SEMGREP_REGISTRY_URL_TEMPLATE,
)
from devops_cli.config.defaults import (
    DEFAULT_SEMGREP_CONFIG,
    DEFAULT_SEMGREP_REGISTRY_MAX_BYTES,
    DEFAULT_SEMGREP_REGISTRY_TIMEOUT_SECONDS,
)
from devops_cli.core.repo import user_data_root
from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.exceptions import ToolDownloadError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import MESSAGES
from devops_cli.output.file_writer import write_bytes_file, write_text_file


class RegistryCachePaths(NamedTuple):
    """Where a ruleset's cache files are: the downloaded YAML and the ETag that describes it."""

    rules: Path
    etag: Path


class _RegistryAnswer(NamedTuple):
    body: bytes
    etag: str | None


def _registry_id(ruleset: str) -> tuple[str, str]:
    """The kind and name of `ruleset`, such as `p` and `default` for `p/default`.

    Semgrep takes `p/` (a pack), `r/` (a rule) and `s/` (a snippet) as registry ids. The name is
    one URL path segment that needs no percent-encoding, so it cannot add a path, a query or a
    fragment to the URL, or a directory to the cache path, and it is not `.` or `..`, which a URL
    resolves away.
    """
    kind, separator, name = ruleset.partition("/")
    if (
        kind not in CONST_SEMGREP_REGISTRY_RULESET_KINDS
        or not separator
        or not name
        or name in (os.curdir, os.pardir)
        or quote(name, safe="") != name
    ):
        raise ValidationError(
            MESSAGES.review.registry_ruleset_invalid.format(
                ruleset=ruleset[:CONST_MAX_ERROR_DETAIL_LENGTH],
                kinds=", ".join(sorted(CONST_SEMGREP_REGISTRY_RULESET_KINDS)),
            ),
            field="ruleset",
        )
    return kind, name


def registry_ruleset_url(ruleset: str) -> str:
    """The registry URL that serves `ruleset`."""
    _registry_id(ruleset)
    return CONST_SEMGREP_REGISTRY_URL_TEMPLATE.format(ruleset=ruleset)


def registry_cache_paths(ruleset: str) -> RegistryCachePaths:
    """The cache files of `ruleset`, named `<kind>-<name>` in `<user data root>/semgrep`.

    The kind is one character and the name has no `/`, so two rulesets never share a slug.
    """
    kind, name = _registry_id(ruleset)
    cache_dir = user_data_root() / CONST_SEMGREP_REGISTRY_CACHE_DIRNAME
    slug = f"{kind}-{name}"
    return RegistryCachePaths(cache_dir / f"{slug}.yaml", cache_dir / f"{slug}.etag")


def _cached_etag(paths: RegistryCachePaths) -> str | None:
    """The ETag of the cached ruleset, or None when there is no ruleset for a 304 to leave."""
    try:
        etag = paths.etag.read_text(encoding="utf-8").strip() if paths.rules.is_file() else ""
    except OSError, UnicodeDecodeError:
        return None
    return etag or None


def _download(url: str, max_bytes: int, cached_etag: str | None) -> _RegistryAnswer | None:
    """The answer of `url` read through the public-only client, never beyond `max_bytes`.

    None when the registry answers 304 to the `cached_etag` that was sent. A 304 to a request that
    sent none is not an answer to use.
    """

    def refused(reason: str) -> ToolDownloadError:
        return ToolDownloadError(url, reason[:CONST_MAX_ERROR_DETAIL_LENGTH], tool_name=BIN_SEMGREP)

    conditional = {"If-None-Match": cached_etag} if cached_etag else {}
    body = bytearray()
    try:
        with (
            new_http_client(
                level=EgressLevel.PUBLIC, read_timeout=DEFAULT_SEMGREP_REGISTRY_TIMEOUT_SECONDS
            ) as client,
            client.stream("GET", url, headers=conditional) as response,
        ):
            if cached_etag and response.status_code == HTTPStatus.NOT_MODIFIED:
                return None
            if not response.is_success:
                raise refused(
                    MESSAGES.review.registry_answer_refused.format(status=response.status_code)
                )
            for chunk in response.iter_bytes():
                body += chunk
                if len(body) > max_bytes:
                    raise refused(MESSAGES.review.registry_answer_too_large.format(limit=max_bytes))
            return _RegistryAnswer(bytes(body), response.headers.get("etag"))
    except httpx2.HTTPError as exc:
        raise refused(f"{type(exc).__name__}: {exc}") from exc


def _is_rule(entry: object) -> bool:
    return isinstance(entry, dict) and isinstance(entry.get("id"), str)


def _rules_in(body: bytes) -> list[object]:
    """The rules `body` holds: empty unless it is YAML with a `rules` list of rules that each have
    an id."""
    try:
        # `load_all` and not `load`: Bandit's B506 passes only the literal names of the safe
        # loaders to `load`. libyaml's reads the 2.5 MB p/default ruleset in under a second, the
        # pure-Python one in several.
        document = next(yaml.load_all(body.decode("utf-8"), Loader=YAML_SAFE_LOADER), None)
    except UnicodeDecodeError, yaml.YAMLError, RecursionError:
        # libyaml's loader recurses per nesting level, and 200 KB of brackets overflows its stack.
        return []
    rules = document.get("rules") if isinstance(document, dict) else None
    return rules if isinstance(rules, list) and all(map(_is_rule, rules)) else []


def fetch_registry_ruleset(
    ruleset: str = DEFAULT_SEMGREP_CONFIG, *, max_bytes: int = DEFAULT_SEMGREP_REGISTRY_MAX_BYTES
) -> int | None:
    """Download `ruleset` into the cache and return how many rules it holds.

    None when the registry reports the cached ruleset unchanged, which rewrites nothing. Nothing is
    written unless the answer is a ruleset within `max_bytes`, so a refused download leaves the
    earlier cache as it was. The ETag is written after the ruleset, and removed when the registry
    sent none, since the one on disk would describe a ruleset that is no longer there.
    """
    url = registry_ruleset_url(ruleset)
    paths = registry_cache_paths(ruleset)
    answer = _download(url, max_bytes, _cached_etag(paths))
    if answer is None:
        return None
    rules = _rules_in(answer.body)
    if not rules:
        raise ValidationError(
            MESSAGES.review.registry_answer_not_a_ruleset.format(url=url),
            field="ruleset",
            details={"url": url},
        )
    write_bytes_file(paths.rules, answer.body)
    if answer.etag:
        write_text_file(paths.etag, answer.etag)
    else:
        paths.etag.unlink(missing_ok=True)
    return len(rules)
