"""Service image invariants: what the committed `Dockerfile` must hold.

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

from pathlib import Path

from tests.support.paths import REPO_ROOT


def _check_copy_from_ref(tokens: list[str], stage_names: set[str]) -> bool:
    """Return True if any --from= reference in COPY is an unpinned non-stage image."""
    for tok in tokens[1:]:
        if tok.startswith("--from="):
            ref = tok.split("=", 1)[1]
            if ref not in stage_names and "@sha256:" not in ref:
                return True
    return False


def _unpinned_dockerfile_images(dockerfile: Path) -> list[str]:
    stage_names: set[str] = set()
    unpinned: list[str] = []
    for raw_line in dockerfile.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        tokens = line.split()
        cmd = tokens[0].upper()
        if cmd == "FROM":
            if len(tokens) >= 4 and tokens[2].upper() == "AS":
                stage_names.add(tokens[3])
            if (
                tokens[1] != "scratch"
                and "@sha256:" not in tokens[1]
                and tokens[1] not in stage_names
            ):
                unpinned.append(line)
        elif cmd == "COPY" and _check_copy_from_ref(tokens, stage_names):
            unpinned.append(line)
    return unpinned


def test_service_dockerfile_base_images_pinned_by_digest() -> None:
    """Every FROM and COPY --from= image in Dockerfile carries @sha256:, Dockerfile sets
    # check=error=true, and .dockerignore drops bytecode (#6415)."""
    unpinned = _unpinned_dockerfile_images(REPO_ROOT / "Dockerfile")
    assert unpinned == []


def test_unpinned_dockerfile_images_allows_scratch_and_reports_unpinned(tmp_path: Path) -> None:
    """Docker's reserved empty `scratch` base has no digest; other bases must pin `@sha256:`."""
    sample = tmp_path / "sample.df"
    sample.write_text(
        "FROM scratch AS uv-seed\nFROM python:3.14-slim-trixie AS bad\n",
        encoding="utf-8",
    )

    assert _unpinned_dockerfile_images(sample) == ["FROM python:3.14-slim-trixie AS bad"]
