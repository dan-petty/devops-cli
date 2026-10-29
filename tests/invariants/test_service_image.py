"""Service image invariants: what the committed `Dockerfile` and `.trivyignore` must hold.

They read only committed files, so they need no network, no image build and no scanner.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from tests.support.dockerfile import env_of as _env_of
from tests.support.dockerfile import stages as _stages
from tests.support.paths import REPO_ROOT

# A gh release URL, wherever it stands in the Dockerfile text: bare, in quotes or after `=`. Its
# path after `releases/` stops at white space, a quote or a backslash.
GH_RELEASE_URL = re.compile(r"github\.com/cli/cli/releases/(?P<path>[^\s\"'\\]*)")
# The one release path that the pin test accepts: one asset of one tag.
GH_RELEASE_DOWNLOAD_PATH = re.compile(r"download/(?P<tag>[^/]+)/(?P<asset>[^/]+)")

# gh v2.102.1 is the first GitHub CLI release that cli/cli builds with Go 1.27.2 or later
# (`toolchain go1.27.3` in its go.mod) and with golang.org/x/net v0.60.0 (#1492).
GH_FIRST_SAFE_VERSION = Version("2.102.1")

# The HIGH Go findings that Trivy reports in gh v2.102.0 (Go 1.27.1, golang.org/x/net v0.58.0).
# Go 1.27.2 and golang.org/x/net v0.60.0 fix them, so the pinned gh build does not have them.
GH_GO_FINDINGS_FIXED_IN_THE_PIN = frozenset({"CVE-2026-78667", "CVE-2026-97031", "CVE-2026-78669"})


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
            if "@sha256:" not in tokens[1] and tokens[1] not in stage_names:
                unpinned.append(line)
        elif cmd == "COPY" and _check_copy_from_ref(tokens, stage_names):
            unpinned.append(line)
    return unpinned


def test_service_dockerfile_base_images_pinned_by_digest() -> None:
    """Every FROM and COPY --from= image in Dockerfile carries @sha256: (stage names exempt, also
    as the base of another stage: the runner stage is built from `builder`)."""
    unpinned = _unpinned_dockerfile_images(REPO_ROOT / "Dockerfile")
    assert unpinned == []


def _gh_release_paths(dockerfile: str) -> list[str]:
    """Return the path after `releases/` of each gh release URL in the Dockerfile text."""
    return [match["path"] for match in GH_RELEASE_URL.finditer(dockerfile)]


def test_the_gh_release_finder_sees_a_url_in_quotes_or_after_another_character() -> None:
    """Verify that the finder returns each gh release URL of a Dockerfile, wherever it stands.

    Regression test (#2433): the finder kept only the bare tokens that start with the URL. A
    `RUN curl` of an older gh in quotes then passed the pin test.
    """
    release = "https://github.com/cli/cli/releases/download"
    dockerfile = (
        f"ADD --checksum=sha256:0 {release}/v2.102.1/gh_2.102.1_linux_amd64.tar.gz /tmp/gh.tgz\n"
        f'RUN curl -fsSLo /tmp/old.tgz "{release}/v2.102.0/gh_2.102.0_linux_amd64.tar.gz"\n'
        f"ENV GH_URL={release}/v2.101.0/gh_2.101.0_linux_arm64.tar.gz\n"
    )

    assert _gh_release_paths(dockerfile) == [
        "download/v2.102.1/gh_2.102.1_linux_amd64.tar.gz",
        "download/v2.102.0/gh_2.102.0_linux_amd64.tar.gz",
        "download/v2.101.0/gh_2.101.0_linux_arm64.tar.gz",
    ]


def test_the_gh_release_finder_sees_a_release_path_that_names_no_tag() -> None:
    """Verify that the finder returns each gh release path, also one that is not a tagged download.

    Regression test (#2433): the finder saw only the `releases/download/` URLs. A `RUN curl` of
    `releases/latest/download/`, or a base URL that a later line completes, then passed the pin
    test.
    """
    release = "https://github.com/cli/cli/releases"
    dockerfile = (
        f'RUN curl -fsSLo /tmp/gh.tgz "{release}/latest/download/gh_linux_amd64.tar.gz"\n'
        f"ENV GH_BASE={release}/download\n"
    )

    assert _gh_release_paths(dockerfile) == ["latest/download/gh_linux_amd64.tar.gz", "download"]


def test_service_image_installs_a_gh_release_built_with_go_1_27_2_or_later() -> None:
    """Verify that the Service image fetches one gh release, at or above the first safe release.

    Regression test (#1492): gh v2.102.0 is built with Go 1.27.1, and Trivy fails the image on
    its HIGH denial-of-service findings in `net/http`, `crypto/tls` and HTTP/2.
    """
    paths = _gh_release_paths((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))

    downloads = [GH_RELEASE_DOWNLOAD_PATH.fullmatch(path) for path in paths]
    tags = {download["tag"] for download in downloads if download}
    assert len(tags) == 1, f"the Dockerfile does not fetch gh from one release tag: {paths}"
    version = tags.pop().removeprefix("v")
    assert sorted(paths) == [
        f"download/v{version}/gh_{version}_linux_amd64.tar.gz",
        f"download/v{version}/gh_{version}_linux_arm64.tar.gz",
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


def _service_stage() -> list[list[str]]:
    return _stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))["service"]


def _install_tools_target(stage: list[list[str]]) -> str:
    """The `--target-dir` of the one `devops install-tools --tool openspec` command in `stage`."""
    commands = [
        words
        for words in stage
        if words[0].upper() == "RUN" and "install-tools" in words and "openspec" in words
    ]
    assert len(commands) == 1, f"expected one install of OpenSpec, found {commands}"
    words = commands[0]
    assert words[words.index("--tool") + 1] == "openspec"
    return words[words.index("--target-dir") + 1]


def test_the_service_stage_installs_openspec_from_the_lockfile_and_puts_it_on_path() -> None:
    """Verify that the service stage gets the OpenSpec that `devops install-tools` installs.

    The installer runs `npm ci` on the lockfile of `src/devops_cli/tools_lock/openspec` in the
    builder stage. The service stage copies the tool directory to the same path, and its PATH
    holds the directory with the `openspec` link (#2659).
    """
    stages = _stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))
    target = _install_tools_target(stages["builder"])
    tools_root = str(Path(target).parent)

    service = stages["service"]
    copies = [
        words for words in service if words[0].upper() == "COPY" and "--from=builder" in words
    ]
    assert [tools_root, tools_root] in [words[-2:] for words in copies]
    assert target in _env_of(service)["PATH"].split(":")
    assert (REPO_ROOT / "src/devops_cli/tools_lock/openspec/package-lock.json").is_file()


def test_the_service_stage_runs_openspec_with_telemetry_off() -> None:
    """Verify that the image turns off the telemetry and the update check of OpenSpec (#2659)."""
    env = _env_of(_service_stage())
    assert {key: env.get(key) for key in ("OPENSPEC_TELEMETRY", "OPENSPEC_NO_UPDATE_CHECK")} == {
        "OPENSPEC_TELEMETRY": "0",
        "OPENSPEC_NO_UPDATE_CHECK": "1",
    }
    assert env.get("DO_NOT_TRACK") == "1"


def test_the_service_and_builder_stages_take_node_from_the_major_of_node_version() -> None:
    """Verify that the Node binary is the one of a digest-pinned `node` image, and that the
    image's major version is the one of `.node-version`, which CI and the devcontainer use.

    The tool runs `#!/usr/bin/env node`, so the service stage needs the binary on PATH (#2659).
    """
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    stages = _stages(dockerfile)
    node_from = next(words for words in stages["node"] if words[0].upper() == "FROM")
    image, _, digest = node_from[1].partition("@")
    major = (REPO_ROOT / ".node-version").read_text(encoding="utf-8").strip().partition(".")[0]
    assert (
        image.split(":")[0],
        image.split(":")[1].split("-")[0],
        digest.startswith("sha256:"),
    ) == (
        "node",
        major,
        True,
    )
    for name in ("builder", "service"):
        assert ["COPY", "--from=node", "/usr/local/bin/node", "/usr/local/bin/node"] in stages[name]
