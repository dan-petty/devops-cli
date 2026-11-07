"""The CISA Known Exploited Vulnerabilities list, for the `exploited` flag (#3987).

CISA publishes the list as one JSON file on `www.cisa.gov`. A CVE in the list has been exploited in
the wild. The client reads the file once, as a stream up to `DEFAULT_KEV_MAX_RESPONSE_BYTES`, and
follows no redirect. It sends no token.
"""

from __future__ import annotations

import logging
from typing import Literal

import httpx2
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.constants import CONST_MAX_ERROR_DETAIL_LENGTH
from devops_cli.config.defaults import (
    DEFAULT_KEV_MAX_RESPONSE_BYTES,
    DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS,
)
from devops_cli.http.public_api import public_api_client, read_json
from devops_cli.telemetry import trace_span

logger = logging.getLogger(__name__)


class _KevEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cve_id: str = Field(alias="cveID")


class _KevCatalog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    vulnerabilities: list[_KevEntry]


class KevLookup(BaseModel):
    """The CVE ids of the list, or the reason that it could not be read."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "failed"]
    reason: str = ""
    cves: frozenset[str] = Field(default_factory=frozenset)


class KevClient:
    """Reads the KEV list from `www.cisa.gov`."""

    URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

    def __init__(self, timeout: float = DEFAULT_VULNERABILITY_LOOKUP_TIMEOUT_SECONDS) -> None:
        self._client = public_api_client(timeout)

    def load(self) -> KevLookup:
        """The CVE ids of the list. A list that cannot be read is `failed`, and no CVE is clean."""
        with trace_span(
            "vulnerability.lookup.cisa_kev",
            attributes={"rpc.system": "http", "rpc.service": "www.cisa.gov"},
        ) as span_h:
            try:
                answer = read_json(
                    self._client,
                    "GET",
                    self.URL,
                    source="CISA KEV",
                    max_bytes=DEFAULT_KEV_MAX_RESPONSE_BYTES,
                )
                catalog = _KevCatalog.model_validate(answer.data)
            except (httpx2.HTTPError, ValueError) as exc:
                logger.debug("CISA KEV read failed: %s", exc)
                span_h.set_attribute("lookup.error", str(exc))
                return KevLookup(status="failed", reason=str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH])
            span_h.set_attribute("entries", len(catalog.vulnerabilities))
            return KevLookup(
                status="ok", cves=frozenset(entry.cve_id for entry in catalog.vulnerabilities)
            )
