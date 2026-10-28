"""The parsers that read string literals and comments out of a file before references are
looked for in them."""

from __future__ import annotations

import pytest

from devops_cli.security.reference_extractor import (
    _clean_yaml_scalar,
    _extract_hcl_literals_and_comments,
    _extract_ip_reference,
    _extract_json_strings,
    _extract_python_literals_and_comments,
    _extract_toml_strings,
    _extract_url_reference,
    _extract_yaml_strings,
    _parse_python_token_string,
)


@pytest.mark.parametrize(
    ("token", "value"),
    [
        ('"hello"', "hello"),
        ("'world'", "world"),
        ('"""multi"""', "multi"),
        ("raw_identifier", "raw_identifier"),
    ],
)
def test_a_python_string_token_is_read_as_its_value(token: str, value: str) -> None:
    """Quoted tokens lose their quotes, and a bare identifier stays as it is."""
    assert _parse_python_token_string(token) == value


def test_python_literals_and_comments_are_read() -> None:
    """A string literal and a comment are both given to the reference search."""
    py_src = """
    # Security header
    API_URL = "https://api.segment.io/v1"
    # End of file
    """
    texts = [literal[0] for literal in _extract_python_literals_and_comments(py_src)]

    assert (
        "https://api.segment.io/v1" in texts,
        any("Security header" in text for text in texts),
    ) == (True, True)


def test_hcl_literals_and_comments_are_read() -> None:
    """HCL string literals, `#` comments and `//` and block comments are read."""
    hcl_src = """
    # Terraform VPC config
    resource "aws_security_group" "sg" {
        cidr_blocks = ["198.51.100.0/24"] // public CIDR
        /* Multi-line
           comment */
    }
    """
    texts = [literal[0] for literal in _extract_hcl_literals_and_comments(hcl_src)]

    assert (
        any("198.51.100.0/24" in text for text in texts),
        any("Terraform VPC config" in text for text in texts),
    ) == (True, True)


def test_a_yaml_scalar_loses_its_template_expressions_and_keeps_its_url() -> None:
    """A `${{ ... }}` expression is removed, and the URL beside it stays a whole token."""
    cleaned = _clean_yaml_scalar(
        "curl -H 'Authorization: ${{ secrets.TOKEN }}' https://api.site.com"
    )

    assert ("${{" in cleaned, "https://api.site.com" in cleaned.split()) == (False, True)


@pytest.mark.parametrize(
    ("reader", "text", "value"),
    [
        pytest.param(
            _extract_json_strings,
            '{"server": "https://example.com", "port": 8080}',
            "https://example.com",
            id="json",
        ),
        pytest.param(
            _extract_toml_strings, '[tool.poetry]\nname = "my-tool"\n', "my-tool", id="toml"
        ),
        pytest.param(
            _extract_yaml_strings,
            "services:\n  web:\n    image: nginx:alpine\n",
            "nginx:alpine",
            id="yaml",
        ),
    ],
)
def test_the_string_values_of_a_structured_file_are_read(
    reader: object, text: str, value: str
) -> None:
    """JSON, TOML and YAML readers give their string values."""
    assert any(value in string[0] for string in reader(text))  # type: ignore[operator]


@pytest.mark.parametrize(("include_local", "kept"), [(True, True), (False, False)])
def test_a_local_url_is_a_reference_only_when_local_targets_are_included(
    include_local: bool, kept: bool
) -> None:
    """A URL on a private address is a local reference, and is dropped when local targets are
    not wanted."""
    reference = _extract_url_reference(
        "http://192.168.1.100:8080/api", "config.py", 5, include_local=include_local
    )

    assert (reference is not None, reference is not None and reference.is_local) == (kept, kept)


def test_a_public_address_is_an_external_reference_without_local_targets() -> None:
    """A public IP is kept when local targets are excluded, and is not local."""
    reference = _extract_ip_reference("8.8.8.8", "config.py", 12, include_local=False)

    assert (reference is not None, reference is not None and reference.is_local) == (True, False)
