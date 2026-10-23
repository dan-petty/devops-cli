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

A scan reads the cached ruleset offline through `cached_ruleset`, which takes the sha256 of the
file as it reads it and the age from the file's modification time. A 304 sets that time to now,
since the registry has just confirmed the ruleset.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass, field
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
    DEFAULT_SEMGREP_REGISTRY_TTL_SECONDS,
)
from devops_cli.core.repo import user_data_root
from devops_cli.core.serialization import YAML_SAFE_LOADER
from devops_cli.exceptions import ToolDownloadError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel
from devops_cli.lang import MESSAGES
from devops_cli.output import print_warning
from devops_cli.output.file_writer import write_bytes_file, write_text_file

_DIGEST_PREFIX = "sha256:"


class RegistryCachePaths(NamedTuple):
    """Where a ruleset's cache files are: the downloaded YAML and the ETag that describes it."""

    rules: Path
    etag: Path


@dataclass(frozen=True)
class CachedRuleset:
    """A cached ruleset a scan can read: its file, the bytes read from it, their sha256 and the
    age of the file.

    A review scans with `body`, the bytes it hashed, and not with the file. A fetch can replace
    the file at any time.
    """

    path: Path
    digest: str
    age_seconds: float
    body: bytes = field(repr=False)

    @property
    def workdir_name(self) -> str:
        """The file name of the ruleset in a review's working directory: its digest."""
        return f"{self.digest.removeprefix(_DIGEST_PREFIX)}.yaml"


class _RegistryAnswer(NamedTuple):
    body: bytes
    etag: str | None


def _parse_registry_id(ruleset: str) -> tuple[str, str] | None:
    """The kind and name of `ruleset`, such as `p` and `default` for `p/default`; None when it is
    no registry id.

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
        return None
    return kind, name


def is_registry_id(config: str) -> bool:
    """Whether a Semgrep `--config` value names a registry ruleset, which the cache serves."""
    return _parse_registry_id(config) is not None


def _registry_id(ruleset: str) -> tuple[str, str]:
    """The kind and name of `ruleset`; a `ValidationError` when it is no registry id."""
    parsed = _parse_registry_id(ruleset)
    if parsed is None:
        raise ValidationError(
            MESSAGES.review.registry_ruleset_invalid.format(
                ruleset=ruleset[:CONST_MAX_ERROR_DETAIL_LENGTH],
                kinds=", ".join(sorted(CONST_SEMGREP_REGISTRY_RULESET_KINDS)),
            ),
            field="ruleset",
        )
    return parsed


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

    None when the registry reports the cached ruleset unchanged, which rewrites nothing but sets the
    file's modification time to now, the cache's age. Nothing is written unless the answer is a
    ruleset within `max_bytes`, so a refused download leaves the earlier cache as it was. The ETag
    is written after the ruleset, and removed when the registry sent none, since the one on disk
    would describe a ruleset that is no longer there.
    """
    url = registry_ruleset_url(ruleset)
    paths = registry_cache_paths(ruleset)
    answer = _download(url, max_bytes, _cached_etag(paths))
    if answer is None:
        os.utime(paths.rules)
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


def cached_ruleset(ruleset: str) -> CachedRuleset | None:
    """The cached `ruleset` a scan can read offline; None when none is cached or the file is no
    longer a ruleset, as when it was emptied or edited until it does not parse.

    The digest is the sha256 of the bytes read here, and the age counts from the file's
    modification time. The cache keeps no digest from the fetch, so an edit that leaves a ruleset
    is read as one, and its digest shows in what a review records.
    """
    rules = registry_cache_paths(ruleset).rules
    try:
        body = rules.read_bytes()
        modified = rules.stat().st_mtime
    except OSError:
        return None
    if not _rules_in(body):
        return None
    return CachedRuleset(
        rules,
        f"{_DIGEST_PREFIX}{hashlib.sha256(body).hexdigest()}",
        max(0.0, time.time() - modified),
        body,
    )


def registry_cache_warning(ruleset: str, cached: CachedRuleset) -> str:
    """What to tell the user when `cached` is older than the TTL, which still serves a scan; empty
    when it is current."""
    if cached.age_seconds <= DEFAULT_SEMGREP_REGISTRY_TTL_SECONDS:
        return ""
    return MESSAGES.review.registry_cache_old.format(
        ruleset=ruleset, hours=int(cached.age_seconds // 3600)
    )


def warn_of_old_cache(ruleset: str, cached: CachedRuleset, *, to_stderr: bool = True) -> None:
    """Print the warning for a cache older than the TTL, if there is one. It goes to stderr unless
    the caller keeps stdout for it, so that a JSON report on stdout stays clean."""
    if warning := registry_cache_warning(ruleset, cached):
        print_warning(warning, to_stderr=to_stderr)
