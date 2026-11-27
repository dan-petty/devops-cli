"""Tests for the behaviour of `devops_cli.core.serialization`."""

from __future__ import annotations

import yaml

from devops_cli.core.serialization import YAML_SAFE_LOADER


def test_shared_safe_loader_reads_a_plain_equals_as_a_string() -> None:
    """PyYAML resolves a plain `=` to the YAML 1.1 value tag, which it cannot construct. YAML 1.2,
    and so Kubernetes, reads it as the string `"="`, and the shared loader does too (#7380)."""
    rendered = (
        "kind: ConfigMap\n"
        "---\n"
        "kind: CustomResourceDefinition\n"
        "enum:\n  - '!='\n  - =\n  - =~\n"
        "flow: [=, a]\n"
    )

    documents = list(yaml.load_all(rendered, Loader=YAML_SAFE_LOADER))

    assert documents == [
        {"kind": "ConfigMap"},
        {"kind": "CustomResourceDefinition", "enum": ["!=", "=", "=~"], "flow": ["=", "a"]},
    ]
