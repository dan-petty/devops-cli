"""Invariant tests for the gh build that the Service image installs, and its Trivy ignores (#1492).

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import urlsplit

from packaging.version import Version

from tests.support.paths import REPO_ROOT

GH_RELEASE_DOWNLOAD_URL = "https://github.com/cli/cli/releases/download/"

# gh v2.102.1 is the first GitHub CLI release that cli/cli builds with Go 1.27.2 or later
# (`toolchain go1.27.3` in its go.mod) and with golang.org/x/net v0.60.0 (#1492).
GH_FIRST_SAFE_VERSION = Version("2.102.1")

# The HIGH Go findings that Trivy reports in gh v2.102.0 (Go 1.27.1, golang.org/x/net v0.58.0).
# Go 1.27.2 and golang.org/x/net v0.60.0 fix them, so the pinned gh build does not have them.
GH_GO_FINDINGS_FIXED_IN_THE_PIN = frozenset({"CVE-2026-78667", "CVE-2026-97031", "CVE-2026-78669"})


def test_service_image_installs_a_gh_release_built_with_go_1_27_2_or_later() -> None:
    """Verify that the Service image fetches one gh release, at or above the first safe release.

    Regression test (#1492): gh v2.102.0 is built with Go 1.27.1, and Trivy fails the image on
    its HIGH denial-of-service findings in `net/http`, `crypto/tls` and HTTP/2.
    """
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    urls = [token for token in dockerfile.split() if token.startswith(GH_RELEASE_DOWNLOAD_URL)]
    tags_and_assets = [PurePosixPath(urlsplit(url).path).parts[-2:] for url in urls]

    tags = {tag for tag, _ in tags_and_assets}
    assert len(tags) == 1, f"the Dockerfile fetches gh from more than one release: {sorted(tags)}"
    version = tags.pop().removeprefix("v")
    assert sorted(asset for _, asset in tags_and_assets) == [
        f"gh_{version}_linux_amd64.tar.gz",
        f"gh_{version}_linux_arm64.tar.gz",
    ]
    assert Version(version) >= GH_FIRST_SAFE_VERSION


def test_trivyignore_ignores_no_go_finding_that_the_pinned_gh_fixes() -> None:
    """Verify that `.trivyignore` holds no ignore for a Go finding that the pinned gh build fixes.

    Regression test (#1492): the three ignores stayed after the Dockerfile moved to gh v2.102.1,
    and their reason still named gh v2.102.0 and Go 1.27.1. An ignore that no finding needs only
    hides that finding when a later change brings it back.
    """
    lines = (REPO_ROOT / ".trivyignore").read_text(encoding="utf-8").splitlines()
    ignored = {
        line.split()[0] for line in lines if line.strip() and not line.lstrip().startswith("#")
    }

    assert ignored & GH_GO_FINDINGS_FIXED_IN_THE_PIN == set()
