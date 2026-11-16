"""Unit tests for the Kubernetes Cloudflare Tunnel (cloudflared) manifests."""

from __future__ import annotations

import yaml
from packaging.version import Version

from devops_cli.tools_lock import load_tools_lock
from tests.support.paths import REPO_ROOT

K8S_DIR = REPO_ROOT / "k8s"
CLOUDFLARED_DIR = K8S_DIR / "cloudflared"

# The first cloudflared release built with Go 1.27.3, which rejects the eight eMudhra
# intermediate certificates whose private keys are weak (#2322).
CLOUDFLARED_FIRST_SAFE_VERSION = Version("2026.10.2")


def test_cloudflared_deployment_runs_a_release_that_rejects_the_compromised_emudhra_intermediates() -> (
    None
):
    """Verify the Deployment's image tag is at or above the first release built with Go 1.27.3.

    Regression test (#2322): cloudflared 2026.9.3 and older trust eight eMudhra intermediate
    certificates with weak private keys. The container runs with `--no-autoupdate`, so only a
    change of this tag removes the trust.
    """
    deployment = yaml.safe_load((CLOUDFLARED_DIR / "deployment.yaml").read_text(encoding="utf-8"))
    containers = deployment["spec"]["template"]["spec"]["containers"]
    assert [container["name"] for container in containers] == ["cloudflared"]

    repository, _, tag = containers[0]["image"].partition(":")
    assert repository == "cloudflare/cloudflared"
    assert Version(tag) >= CLOUDFLARED_FIRST_SAFE_VERSION


def test_cloudflared_tools_lock_installs_a_release_that_rejects_the_compromised_emudhra_intermediates() -> (
    None
):
    """Verify the lock pins cloudflared at or above the first safe release, and fetches that release.

    Regression test (#2322): `version` names the install directory, and each `sha256` only checks
    the bytes of its own `url`. A bump of `version` that leaves a `url` at the old release would
    install the old build under the new version, and the checksum would pass.
    """
    cloudflared = load_tools_lock().binary["cloudflared"]

    assert Version(cloudflared.version) >= CLOUDFLARED_FIRST_SAFE_VERSION
    assert {
        platform: artifact.url.startswith(
            f"https://github.com/cloudflare/cloudflared/releases/download/{cloudflared.version}/"
        )
        for platform, artifact in cloudflared.platforms.items()
    } == dict.fromkeys(("linux-amd64", "linux-arm64", "darwin-amd64", "darwin-arm64"), True)
