"""Finding locations keep paths with `+`, `@`, `~`, `%` and non-ASCII letters (#498).

Location patterns matched paths with `[a-zA-Z0-9_\\-./\\\\]` only. A path outside that class fell
through to a fallback that kept its first path-like fragment, so every finding under a corpus
named `playbooks+core+...` was saved as `.data/reviews/corpora/playbooks`, with no file and no
lines.
"""

from __future__ import annotations

import pytest

from devops_cli.ai.review_schema import Finding, canonicalize_finding_location

_PATHS = [
    ".data/reviews/corpora/playbooks+core+security-1/files/core/audit.py",
    "include/c++/vector.hpp",
    "node_modules/@scope/pkg/index.js",
    "assets/logo@2x.svg",
    "~/.config/devops/config.yaml",
    "docs/100%-coverage.md",
    "docs/café/résumé.md",
]


@pytest.mark.parametrize("path", _PATHS)
def test_a_path_keeps_every_character_with_its_lines(path: str) -> None:
    """Verify the whole path survives, alone, with a line and with a range."""
    canonical = tuple(
        canonicalize_finding_location(loc) for loc in (path, f"{path}:7", f"{path}:12-20")
    )

    assert canonical == (path, f"{path}:7", f"{path}:12-20")


@pytest.mark.parametrize("path", _PATHS)
def test_a_path_is_normalized_like_any_other(path: str) -> None:
    """Verify reversed ranges, `#L` anchors, backticks and `, lines` apply to these paths."""
    canonical = tuple(
        canonicalize_finding_location(loc)
        for loc in (f"{path}:20-12", f"{path}#L7", f"`{path}:7`", f"{path}, lines 12-20")
    )

    assert canonical == (f"{path}:12-20", f"{path}:7", f"{path}:7", f"{path}:12-20")


@pytest.mark.parametrize("path", _PATHS)
def test_a_path_embedded_in_prose_is_extracted_whole(path: str) -> None:
    """Verify a location the model buried in a sentence keeps its full path."""
    location = canonicalize_finding_location(f"We need the lines. So location: {path}:12-20.")

    assert location == f"{path}:12-20"


def test_a_dependency_target_keeps_a_scoped_package_path() -> None:
    """Verify `file:target` locations accept the same path characters."""
    location = canonicalize_finding_location("packages/@scope/web/package.json:lodash")

    assert location == "packages/@scope/web/package.json:lodash"


def test_a_finding_under_a_plus_named_corpus_keeps_its_file_and_lines() -> None:
    """Verify the #415 corpus case end to end through the Finding model."""
    finding = Finding(
        severity="HIGH",
        location=".data/reviews/corpora/playbooks+core+security+crypto/files/crypto/kh.py:248-250",
        title="Directory created world-writable",
        description="mkdir(mode=0o777)",
    )

    assert (finding.location, finding.is_empty) == (
        ".data/reviews/corpora/playbooks+core+security+crypto/files/crypto/kh.py:248-250",
        False,
    )
