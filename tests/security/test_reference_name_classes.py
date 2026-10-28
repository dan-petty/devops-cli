"""The class of a name in a network reference: an example, a local name, a package registry, a
lockfile or a fictitious phone number."""

from __future__ import annotations

import pytest

from devops_cli.security.reference_extractor import (
    is_example_or_invalid_domain,
    is_example_or_invalid_network_target,
    is_example_phone_number,
    is_local_or_reserved_domain,
    is_lockfile_or_ignore_file,
    is_trusted_registry_host,
)


@pytest.mark.parametrize(
    "domain",
    [
        "example.com",
        "sub.deep.example.net",
        "sample.example.org",
        "test.example.edu",
        "service.example",
        "broken.invalid",
        "staging.test",
    ],
)
def test_an_rfc_2606_name_is_an_example_domain_and_target(domain: str) -> None:
    """The RFC 2606 domains and the `.example`, `.invalid` and `.test` names are examples."""
    assert (is_example_or_invalid_domain(domain), is_example_or_invalid_network_target(domain)) == (
        True,
        True,
    )


@pytest.mark.parametrize(
    "domain",
    [
        "localhost",
        "app.localhost",
        "worker.internal",
        "gateway.home.arpa",
        "github.com",
        "api.cloudflare.com",
        "openai.com",
    ],
)
def test_a_local_or_real_name_is_not_an_example_domain(domain: str) -> None:
    """A local endpoint such as `localhost` and a real public name are not examples."""
    assert is_example_or_invalid_domain(domain) is False


@pytest.mark.parametrize(
    ("domain", "local"),
    [
        ("service.cluster.local", True),
        ("node.cluster.local", True),
        ("database.svc", True),
        ("router.lan", True),
        ("node.internal", True),
        ("device.home.arpa", True),
        ("host.localdomain", True),
        ("api.datadoghq.com", False),
        ("invalid-domain-", False),
        ("has_underscore.internal", False),
    ],
)
def test_a_name_under_a_local_suffix_is_local_or_reserved(domain: str, local: bool) -> None:
    """Cluster, service, LAN, internal, home and local-domain suffixes are local; a public name,
    and a name that is not a valid host name, are not."""
    assert is_local_or_reserved_domain(domain) is local


@pytest.mark.parametrize(
    ("host", "trusted"),
    [
        ("files.pythonhosted.org", True),
        ("registry.npmjs.org", True),
        ("crates.io", True),
        ("repo.maven.apache.org", True),
        ("api.my-vendor-service.io", False),
        ("evil-host.xyz", False),
        ("app.datadoghq.com", False),
    ],
)
def test_only_a_package_registry_host_is_trusted(host: str, trusted: bool) -> None:
    """The package registries' download hosts are trusted, and no other host is."""
    assert is_trusted_registry_host(host) is trusted


@pytest.mark.parametrize(
    ("name", "lockfile"),
    [
        ("uv.lock", True),
        ("poetry.lock", True),
        ("package-lock.json", True),
        ("cargo.lock", True),
        ("yarn.lock", True),
        ("pnpm-lock.yaml", True),
        ("composer.lock", True),
        ("Gemfile.lock", True),
        (".gitignore", True),
        (".dockerignore", True),
        ("pyproject.toml", False),
        ("src/client.py", False),
        ("main.py", False),
    ],
)
def test_a_lockfile_or_ignore_file_is_recognized_by_name(name: str, lockfile: bool) -> None:
    """Lockfiles and ignore files are recognized; a manifest or a source file is not."""
    assert is_lockfile_or_ignore_file(name) is lockfile


@pytest.mark.parametrize(
    ("number", "fictitious"),
    [
        ("555-0142", True),
        ("+1-212-555-0199", True),
        ("1-800-555-0100", True),
        ("(212) 555-0123", True),
        ("01632 960001", True),
        ("+44 1632 4960123", True),
        ("212-555-1212", False),
        ("1-800-222-3333", False),
    ],
)
def test_a_fictitious_phone_number_is_an_example(number: str, fictitious: bool) -> None:
    """The ATIS-0300115 / NANPA 555-01xx range and the UK Ofcom drama ranges are fictitious; an
    ordinary number is not."""
    assert is_example_phone_number(number) is fictitious
