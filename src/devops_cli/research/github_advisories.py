"""The client of the GitHub advisories API for `devops research advisories` (#3987).

Two reads, both on `api.github.com`:

- `GET /advisories?ecosystem=<ecosystem>&affects=<names>` lists the reviewed advisories of the
  GitHub Advisory Database that name a package. GitHub Actions are the packages of the ecosystem
  `actions`, and OSV does not match their versions.
- `GET /repos/{owner}/{repo}/security-advisories` lists the advisories that a repository published.
  A vendor of an image or a binary publishes the advisory here before, or without, a CVE and a
  database entry: the Qdrant server advisories GHSA-3gph-6c29-p29v and GHSA-frc7-44gm-99qq are
  not in `GET /advisories` (a read of each gave 404 on 2026-11-07).

Both read public data, so a token is optional: it lifts the limit of 60 requests an hour for a
caller with no token to 5000. The client follows no redirect and reads the next page of a list
only when its URL is on `api.github.com`, so the token never reaches another host. A reply over
`DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES` is an error.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx2
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from devops_cli.config.constants import CONST_MAX_ERROR_DETAIL_LENGTH
from devops_cli.config.defaults import (
    DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX,
    DEFAULT_GITHUB_ADVISORIES_MAX_PAGES,
    DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES,
    DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS,
)
from devops_cli.http.public_api import public_api_client, read_json
from devops_cli.telemetry import trace_span
from devops_cli.telemetry.instruments import VULNERABILITY_LOOKUPS_TOTAL, emit

logger = logging.getLogger(__name__)

_SOURCE = "GitHub"
_API_VERSION = "2022-11-28"
_PAGE_SIZE = "100"


class GhsaPackage(BaseModel):
    """The package of a vulnerability: the ecosystem and the name that GitHub gives it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ecosystem: str = ""
    name: str = ""


class GhsaVulnerability(BaseModel):
    """One package of an advisory, with the versions that it affects and the version that fixes it.

    The list reads the fix as `first_patched_version`, and the repository read as `patched_versions`.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    package: GhsaPackage | None = None
    vulnerable_version_range: str | None = None
    first_patched_version: str | None = None
    patched_versions: str | None = None

    @property
    def fixed_version(self) -> str:
        """The version that fixes the package, or an empty string when none does."""
        return self.first_patched_version or self.patched_versions or ""


class GhsaAdvisory(BaseModel):
    """The fields of an advisory that the report uses."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    ghsa_id: str
    cve_id: str | None = None
    severity: str | None = None
    summary: str | None = None
    vulnerabilities: list[GhsaVulnerability] = Field(default_factory=list)


class GhsaLookup(BaseModel):
    """The advisories that a read returned, or the reason that it got none. A failed read is no
    clean package."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "failed"]
    reason: str = ""
    advisories: list[GhsaAdvisory] = Field(default_factory=list)


_ADVISORY_PAGE = TypeAdapter(list[GhsaAdvisory])


def _failed(reason: str) -> GhsaLookup:
    return GhsaLookup(status="failed", reason=reason[:CONST_MAX_ERROR_DETAIL_LENGTH])


class GitHubAdvisoryClient:
    """Reads advisories from `api.github.com`. The token, when there is one, goes to that host only."""

    BASE_URL = "https://api.github.com"
    ADVISORIES_URL = f"{BASE_URL}/advisories"
    REPOSITORY_URL = f"{BASE_URL}/repos"

    def __init__(
        self,
        token: str | None = None,
        timeout: float = DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS,
    ) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": _API_VERSION}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = public_api_client(timeout, headers)

    def _read_pages(self, url: str, params: dict[str, str]) -> list[GhsaAdvisory]:
        """Every advisory of a list, read page by page up to `DEFAULT_GITHUB_ADVISORIES_MAX_PAGES`."""
        advisories: list[GhsaAdvisory] = []
        next_url: str | None = url
        next_params: dict[str, str] | None = params
        for _ in range(DEFAULT_GITHUB_ADVISORIES_MAX_PAGES):
            if next_url is None:
                return advisories
            if not next_url.startswith(f"{self.BASE_URL}/"):
                raise ValueError("GitHub named a next page on another host")
            answer = read_json(
                self._client,
                "GET",
                next_url,
                source=_SOURCE,
                max_bytes=DEFAULT_GITHUB_ADVISORIES_MAX_RESPONSE_BYTES,
                params=next_params,
            )
            advisories.extend(_ADVISORY_PAGE.validate_python(answer.data))
            next_url, next_params = answer.next_url, None
        if next_url is not None:
            raise ValueError(
                f"GitHub listed more than {DEFAULT_GITHUB_ADVISORIES_MAX_PAGES} pages of advisories"
            )
        return advisories

    def _lookup(self, url: str, params: dict[str, str], span_name: str, count: int) -> GhsaLookup:
        with trace_span(
            span_name,
            attributes={"rpc.system": "http", "rpc.service": "api.github.com", "count": count},
        ) as span_h:
            try:
                advisories = self._read_pages(url, params)
            except (httpx2.HTTPError, ValueError) as exc:
                logger.debug("GitHub advisory read failed: %s", exc)
                span_h.set_attribute("lookup.error", str(exc))
                return _failed(str(exc))
            span_h.set_attribute("advisories_found", len(advisories))
            emit(
                VULNERABILITY_LOOKUPS_TOTAL,
                float(count),
                {"source": "github", "status": "ok", "batch": str(count > 1).lower()},
            )
            return GhsaLookup(status="ok", advisories=advisories)

    def for_packages(self, ecosystem: str, names: list[str]) -> dict[str, GhsaLookup]:
        """The advisories that name each package of `ecosystem`, in chunks of `affects` names.

        A package gets the advisories that name it, whatever the version; the caller matches the
        version. A chunk whose read fails fails its own packages only. The key is the name as given.
        """
        found: dict[str, GhsaLookup] = {}
        size = DEFAULT_GITHUB_ADVISORIES_AFFECTS_MAX
        for start in range(0, len(names), size):
            chunk = names[start : start + size]
            lookup = self._lookup(
                self.ADVISORIES_URL,
                {
                    "ecosystem": ecosystem,
                    "affects": ",".join(chunk),
                    "per_page": _PAGE_SIZE,
                },
                "vulnerability.lookup.github_advisories",
                len(chunk),
            )
            for name in chunk:
                if lookup.status != "ok":
                    found[name] = lookup
                    continue
                wanted = name.lower()
                found[name] = GhsaLookup(
                    status="ok",
                    advisories=[
                        advisory
                        for advisory in lookup.advisories
                        if any(
                            v.package is not None
                            and v.package.ecosystem == ecosystem
                            and v.package.name.lower() == wanted
                            for v in advisory.vulnerabilities
                        )
                    ],
                )
        return found

    def for_repository(self, repository: str) -> GhsaLookup:
        """The advisories that the repository `owner/name` published."""
        return self._lookup(
            f"{self.REPOSITORY_URL}/{repository}/security-advisories",
            {"per_page": _PAGE_SIZE},
            "vulnerability.lookup.github_repository_advisories",
            1,
        )
