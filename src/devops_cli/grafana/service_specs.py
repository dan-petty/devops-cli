"""The specs of the service dashboards (`[[service]]` tables), with no Grafana SDK (#7212).

`grafana/service_dashboard.py` builds the dashboard JSON with `grafana-foundation-sdk`, which is a
dev-only package. The commands that only read the specs, such as the service catalog, import this
module.
"""

from __future__ import annotations

import tomllib
from decimal import Decimal
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

type Resource = Literal["memory", "cpu"]
type ProfileType = Literal[
    "process_cpu:cpu:nanoseconds:cpu:nanoseconds", "memory:inuse_space:bytes:space:bytes"
]

# The file of the specs.
SPEC_FILE_NAME: Final = "services.toml"


class ServiceSpec(BaseModel):
    """The spec of the dashboard of one Kubernetes service: its identity, its request metrics
    and its SLO. Each selector can name the Grafana variables `$namespace` and `$workload`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    uid: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,39}$")
    title: str
    description: str
    namespace: str
    workload: str
    variables: bool = False
    # The counter of the requests of the service, with the matchers that select the service. It
    # ends with its matchers in braces, because `errors` goes into them.
    requests: str = Field(
        default='traefik_service_requests_total{service=~"$namespace-$workload-[0-9]+@kubernetes"}',
        pattern=r"\}$",
    )
    # The matcher, added to `requests`, that selects the failed requests.
    errors: str = 'code=~"5.."'
    # The histogram buckets of the latency of the successful requests.
    latency: str = (
        "traefik_service_request_duration_seconds_bucket"
        '{service=~"$namespace-$workload-[0-9]+@kubernetes", code!~"5.."}'
    )
    slo_target: Decimal = Field(default=Decimal("0.999"), gt=0, lt=1)
    slo_window_days: int = Field(default=30, gt=0)
    saturation: tuple[Resource, ...] = Field(default=("memory", "cpu"), min_length=1, max_length=2)
    logs: bool = True
    profiles: tuple[ProfileType, ...] = ()

    @property
    def budget(self) -> Decimal:
        """The error budget: the share of the requests that can fail."""
        return 1 - self.slo_target

    @property
    def window(self) -> str:
        """The SLO window as a PromQL duration."""
        return f"{self.slo_window_days}d"


def load_specs(spec_file: Path) -> list[ServiceSpec]:
    """The specs of the `[[service]]` tables of `spec_file`."""
    document = tomllib.loads(spec_file.read_text(encoding="utf-8"))
    return [ServiceSpec.model_validate(entry) for entry in document["service"]]
