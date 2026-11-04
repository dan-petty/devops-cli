"""`mask_private_hosts` hides private host names and addresses, and nothing else (#3032)."""

from __future__ import annotations

from devops_cli.security.sanitizer import mask_private_hosts


def test_a_host_name_an_address_and_localhost_are_masked() -> None:
    text = "curl https://db.corp.internal/x 127.0.0.1 and localhost done"
    assert mask_private_hosts(text) == (
        "curl https://<masked-host>/x <masked-host> and <masked-host> done"
    )


def test_a_private_address_built_at_run_time_is_masked() -> None:
    address = ".".join(("10", "1", "2", "3"))
    assert mask_private_hosts(f"to {address}") == "to <masked-host>"


def test_a_public_host_and_a_code_name_are_left_alone() -> None:
    text = "example.com 198.51.100.7 config.local_value"
    assert mask_private_hosts(text) == text
