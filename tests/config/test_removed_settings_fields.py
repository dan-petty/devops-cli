"""The two settings that no code reads are off the model and out of a config file that still holds
them (#2457).

`cloudflare.access.enabled` and `cloudflare.access.idp` held a value that no reader took: the
Cloudflare reader takes `allowed_emails`, `bypass_ips` and `public_ip_bypass`. Removing them leaves a
config file that still names them able to load, because the section drops a key it does not declare.

`telemetry.logfire` is kept: `_init_logfire_if_enabled` reads it as the ambient fallback for the
`--logfire` flag on the review commands, and a test covers it.
"""

from __future__ import annotations

from devops_cli.config.settings import CloudflareAccessConfig, TelemetryConfig


def test_the_removed_fields_are_off_their_model() -> None:
    assert (
        "enabled" in CloudflareAccessConfig.model_fields,
        "idp" in CloudflareAccessConfig.model_fields,
    ) == (False, False)


def test_a_model_that_still_holds_a_removed_key_loads_and_drops_it() -> None:
    access = CloudflareAccessConfig(allowed_emails=["a@example.com"], enabled=True, idp="google")

    assert (
        "enabled" in access.model_dump(),
        "idp" in access.model_dump(),
        access.allowed_emails,
    ) == (False, False, ["a@example.com"])


def test_telemetry_logfire_stays_because_it_has_a_reader() -> None:
    assert "logfire" in TelemetryConfig.model_fields
