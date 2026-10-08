"""release.yml's Service image plan and tag steps: a release branch publishes the image main will
pin, and nothing replaces it once main pins it (#1451).

Each step runs verbatim under bash in a real git repository with an `origin` remote. Only the
process edge is faked, by scripts on PATH: `docker` answers `docker buildx imagetools inspect`
from a directory standing in for GHCR and records `imagetools create`, `gh` answers
`gh attestation verify` from the certificate identity recorded for a digest, and, where a test
asks for it, `git` fails `ls-remote` as a network error would. Nothing reaches the network.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
REPOSITORY = "dan-petty/devops-cli"
IMAGE = f"ghcr.io/{REPOSITORY}/service"
FAKE_DOCKER = """#!/usr/bin/env bash
# docker buildx imagetools inspect REF --format F: prints "<digest> <inputs>" from $FAKE_GHCR/<tag>.
# docker buildx imagetools create ARGS: appends ARGS to $FAKE_GHCR/created.
if [ "$3" = "create" ]; then echo "${*:4}" >> "$FAKE_GHCR/created"; exit 0; fi
tag="${4##*:}"
if [ -f "$FAKE_GHCR/$tag.err" ]; then cat "$FAKE_GHCR/$tag.err" >&2; exit 1; fi
if [ -f "$FAKE_GHCR/$tag" ]; then printf '%s' "$(cat "$FAKE_GHCR/$tag")"; exit 0; fi
echo "ERROR: $4: not found" >&2
exit 1
"""
FAKE_GH = """#!/usr/bin/env bash
# gh attestation verify oci://IMAGE@DIGEST ... --cert-identity-regex RE: passes when the signing
# identity recorded in $FAKE_GHCR/attested/DIGEST matches RE, as the certificate check does.
[ "$1 $2" = "attestation verify" ] || exit 2
digest="${3##*@}"
regex=""
while [ $# -gt 0 ]; do
  if [ "$1" = "--cert-identity-regex" ]; then regex="$2"; fi
  shift
done
if [ ! -f "$FAKE_GHCR/attested/$digest" ]; then echo "no attestations for $digest" >&2; exit 1; fi
san="$(cat "$FAKE_GHCR/attested/$digest")"
if [[ -n "$regex" && "$san" =~ $regex ]]; then exit 0; fi
echo "$san does not match $regex" >&2
exit 1
"""
FAKE_GIT = """#!/usr/bin/env bash
# git ls-remote fails as an unreachable remote does; every other git command is the real one.
if [ "$1" = "ls-remote" ]; then
  echo "fatal: unable to access 'https://example.com/': Could not resolve host: example.com" >&2
  exit 128
fi
exec {real_git} "$@"
"""


def _signer(ref: str, workflow: str = "release.yml") -> str:
    """The SubjectAlternativeName GitHub's OIDC token gives a workflow run on `ref`."""
    return f"https://github.com/{REPOSITORY}/.github/workflows/{workflow}@{ref}"


def _workflow() -> dict[str, Any]:
    workflow: dict[str, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return workflow


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(work: Path, message: str, files: dict[str, str]) -> str:
    for name, text in files.items():
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_text(text, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", message)
    return _git(work, "rev-parse", "HEAD")


def _pyproject(version: str) -> str:
    return f'[project]\nname = "devops-cli"\nversion = "{version}"\n'


@pytest.fixture
def repo(tmp_path: Path) -> dict[str, Any]:
    """main at 0.2.28, and release/v0.2.29 cut to 0.2.29 with one more item before the cut."""
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    _git(tmp_path, "init", "-q", "-b", "main", str(work))
    _git(work, "config", "user.email", "ci@example.com")
    _git(work, "config", "user.name", "CI")
    _git(work, "config", "commit.gpgsign", "false")
    _git(work, "config", "tag.gpgsign", "false")
    _git(work, "remote", "add", "origin", str(origin))
    _commit(
        work,
        "base",
        {
            "pyproject.toml": _pyproject("0.2.28"),
            "uv.lock": "lock\n",
            "Dockerfile": "FROM scratch\n",
            ".dockerignore": "*\n",
            "src/devops_cli/a.py": "A = 1\n",
            "CHANGELOG.md": "## [0.2.28]\n",
        },
    )
    _git(work, "push", "-q", "origin", "main")
    _git(work, "checkout", "-q", "-b", "release/v0.2.29")
    pre_cut = _commit(work, "item", {"src/devops_cli/b.py": "B = 1\n"})
    cut = _commit(work, "feat(release): v0.2.29", {"pyproject.toml": _pyproject("0.2.29")})
    _git(work, "push", "-q", "origin", "release/v0.2.29")
    return {"tmp": tmp_path, "origin": origin, "work": work, "pre_cut": pre_cut, "cut": cut}


def _inputs(work: Path, sha: str) -> str:
    paths = _workflow()["jobs"]["service-image"]["env"]["SERVICE_IMAGE_INPUTS"].split()
    listing = _git(work, "ls-tree", sha, "--", *paths) + "\n"
    return hashlib.sha256(listing.encode()).hexdigest()


def _bin(tmp: Path, git_fails: bool) -> Path:
    """The fakes on PATH: docker and gh always, git only when `git_fails`."""
    bin_dir = tmp / ("bin-offline" if git_fails else "bin")
    bin_dir.mkdir(exist_ok=True)
    fakes = {"docker": FAKE_DOCKER, "gh": FAKE_GH}
    if git_fails:
        fakes["git"] = FAKE_GIT.format(real_git=shutil.which("git"))
    for name, script in fakes.items():
        (bin_dir / name).write_text(script, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    return bin_dir


def _run(
    repo: dict[str, Any],
    step_id: str,
    sha: str,
    ref: str,
    env: dict[str, str] | None = None,
    ghcr: dict[str, str] | None = None,
    attested: dict[str, str] | None = None,
    git_fails: bool = False,
) -> tuple[int, dict[str, str], str]:
    """Run the service-image step `step_id` at `sha` on `ref`.

    `ghcr` maps a tag to "<digest> <inputs>" or "!error"; `attested` maps a digest to the
    identity that signed its provenance. Returns the exit code, the step's outputs, and its log.
    """
    tmp: Path = repo["tmp"]
    run_dir = tmp / f"run-{step_id}-{sha[:8]}-{ref.rsplit('/', 1)[-1]}"
    _git(tmp, "clone", "-q", str(repo["origin"]), str(run_dir))
    _git(run_dir, "checkout", "-q", "--detach", sha)
    fake_ghcr = tmp / "ghcr"
    (fake_ghcr / "attested").mkdir(parents=True, exist_ok=True)
    for tag, answer in (ghcr or {}).items():
        target = fake_ghcr / (f"{tag}.err" if answer.startswith("!") else tag)
        target.write_text(answer.lstrip("!"), encoding="utf-8")
    for digest, signer in (attested or {}).items():
        (fake_ghcr / "attested" / digest).write_text(signer, encoding="utf-8")
    output = tmp / "github_output"
    output.write_text("", encoding="utf-8")
    job = _workflow()["jobs"]["service-image"]
    step = next(s for s in job["steps"] if s.get("id") == step_id)
    step_env = {
        **os.environ,
        "PATH": f"{_bin(tmp, git_fails)}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_REF": ref,
        "GITHUB_SHA": sha,
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_OUTPUT": str(output),
        "RUNNER_TEMP": str(tmp),
        "REF_NAME": ref.removeprefix("refs/heads/"),
        "SERVICE_IMAGE": IMAGE,
        "SERVICE_IMAGE_INPUTS": job["env"]["SERVICE_IMAGE_INPUTS"],
        "FAKE_GHCR": str(fake_ghcr),
        **{k: v for k, v in step["env"].items() if "${{" not in str(v)},
        **(env or {}),
    }
    done = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", step["run"]],
        cwd=run_dir,
        env=step_env,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    return done.returncode, outputs, done.stdout + done.stderr


def _plan(
    repo: dict[str, Any],
    sha: str,
    ref: str,
    release_version: str = "",
    ghcr: dict[str, str] | None = None,
    attested: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], str]:
    env = {"RELEASE_VERSION": release_version}
    return _run(repo, "plan", sha, ref, env, ghcr, attested)


def _tag(repo: dict[str, Any], sha: str, ref: str, tags: str) -> tuple[int, list[str], str]:
    """Run the tag step for digest sha256:bbb; returns the exit code, the tags created, the log."""
    env = {"DIGEST": "sha256:bbb", "TAGS": tags, "VERSION": "0.2.29"}
    code, _, log = _run(repo, "tag", sha, ref, env)
    created = repo["tmp"] / "ghcr" / "created"
    return code, created.read_text(encoding="utf-8").splitlines() if created.exists() else [], log


BRANCH = "refs/heads/release/v0.2.29"
MAIN = "refs/heads/main"


def test_a_branch_before_its_cut_publishes_nothing(repo: dict[str, Any]) -> None:
    _git(repo["work"], "push", "-q", "-f", "origin", f"{repo['pre_cut']}:release/v0.2.29")
    code, out, _ = _plan(repo, repo["pre_cut"], BRANCH)
    assert (code, out["action"]) == (0, "none")


def test_the_cut_publishes_its_version_without_latest(repo: dict[str, Any]) -> None:
    code, out, _ = _plan(repo, repo["cut"], BRANCH)
    assert (code, out["action"], out["latest"], out["version"], out["inputs"]) == (
        0,
        "publish",
        "false",
        "0.2.29",
        _inputs(repo["work"], repo["cut"]),
    )


def test_a_push_that_leaves_the_inputs_alone_publishes_nothing(repo: dict[str, Any]) -> None:
    collate = _commit(repo["work"], "collate", {"CHANGELOG.md": "## [0.2.29]\n"})
    _git(repo["work"], "push", "-q", "origin", "release/v0.2.29")
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    code, out, _ = _plan(
        repo, collate, BRANCH, ghcr={"v0.2.29": published}, attested={"sha256:aaa": _signer(BRANCH)}
    )
    assert (code, out["action"]) == (0, "none")


@pytest.mark.parametrize(
    "signer",
    [None, _signer("refs/heads/feature"), _signer(BRANCH, workflow="ci.yml")],
    ids=["unattested", "release.yml-on-another-branch", "another-workflow"],
)
def test_an_image_release_yml_did_not_attest_is_published_again(
    repo: dict[str, Any], signer: str | None
) -> None:
    """The label is only the pusher's claim; provenance from release.yml is what counts."""
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    attested = {"sha256:aaa": signer} if signer else {}
    code, out, _ = _plan(repo, repo["cut"], BRANCH, ghcr={"v0.2.29": published}, attested=attested)
    assert (code, out["action"], out["latest"]) == (0, "publish", "false")


def test_a_fix_after_the_cut_republishes(repo: dict[str, Any]) -> None:
    fix = _commit(repo["work"], "fix", {"src/devops_cli/a.py": "A = 2\n"})
    _git(repo["work"], "push", "-q", "origin", "release/v0.2.29")
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    code, out, _ = _plan(
        repo, fix, BRANCH, ghcr={"v0.2.29": published}, attested={"sha256:aaa": _signer(BRANCH)}
    )
    assert (code, out["action"], out["latest"]) == (0, "publish", "false")


def test_a_superseded_run_publishes_nothing(repo: dict[str, Any]) -> None:
    _commit(repo["work"], "fix", {"src/devops_cli/a.py": "A = 2\n"})
    _git(repo["work"], "push", "-q", "origin", "release/v0.2.29")
    code, out, _ = _plan(repo, repo["cut"], BRANCH)
    assert (code, out["action"]) == (0, "none")


@pytest.mark.parametrize("step_id", ["plan", "tag"])
def test_an_unreadable_branch_tip_fails_closed(repo: dict[str, Any], step_id: str) -> None:
    """A failed `git ls-remote` stops the step instead of reading as a superseded commit."""
    env = {"DIGEST": "sha256:bbb", "TAGS": f"{IMAGE}:v0.2.29", "VERSION": "0.2.29"}
    code, out, log = _run(repo, step_id, repo["cut"], BRANCH, env, git_fails=True)
    created = repo["tmp"] / "ghcr" / "created"
    assert (code, out.get("action"), "no longer the tip" in log, created.exists()) == (
        128,
        None,
        False,
        False,
    )


def _push_to_main(repo: dict[str, Any], files: dict[str, str]) -> None:
    work = repo["work"]
    _git(work, "checkout", "-q", "main")
    _commit(work, "fix on main", files)
    _git(work, "push", "-q", "origin", "main")


def test_a_branch_missing_main_image_changes_fails_before_publishing(
    repo: dict[str, Any],
) -> None:
    _push_to_main(repo, {"uv.lock": "lock 2\n"})
    code, out, log = _plan(repo, repo["cut"], BRANCH)
    assert (code, out.get("action"), "Merge main into release/v0.2.29" in log) == (
        1,
        None,
        True,
    )


def test_a_branch_missing_main_commits_that_leave_the_image_alone_still_publishes(
    repo: dict[str, Any],
) -> None:
    """Merging the release keeps the branch's image inputs, so the image built here is the one."""
    _push_to_main(repo, {"NOTES.md": "x\n"})
    code, out, _ = _plan(repo, repo["cut"], BRANCH)
    assert (code, out["action"]) == (0, "publish")


def _merge(repo: dict[str, Any], extra: dict[str, str] | None = None) -> str:
    """Squash release/v0.2.29 into main and tag the merge, as the PR and the release job do."""
    work = repo["work"]
    _git(work, "checkout", "-q", "main")
    _git(work, "merge", "-q", "--squash", "release/v0.2.29")
    merged = _commit(work, "feat(release): v0.2.29 (#1)", extra or {})
    _git(work, "tag", "-a", "v0.2.29", "-m", "v0.2.29")
    _git(work, "push", "-q", "--follow-tags", "origin", "main")
    return merged


def test_a_merged_release_is_never_republished_from_its_branch(repo: dict[str, Any]) -> None:
    _merge(repo)
    code, out, _ = _plan(repo, repo["cut"], BRANCH)
    assert (code, out["action"]) == (0, "none")


def test_main_points_latest_at_the_image_built_from_its_inputs(repo: dict[str, Any]) -> None:
    merged = _merge(repo, {"CHANGELOG.md": "## [0.2.29]\n"})
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    attested = {"sha256:aaa": _signer(BRANCH)}
    code, out, _ = _plan(repo, merged, MAIN, "0.2.29", {"v0.2.29": published}, attested)
    assert (code, out["action"], out["digest"]) == (0, "promote", "sha256:aaa")


def _later_push(repo: dict[str, Any]) -> str:
    """A push to main after the release merged that changes the image's inputs."""
    _merge(repo)
    later = _commit(repo["work"], "chore(deps): bump", {"uv.lock": "lock 2\n"})
    _git(repo["work"], "push", "-q", "origin", "main")
    return later


def _recovery(repo: dict[str, Any]) -> str:
    """The release merged but its release job failed before tagging; the fix is the tagged commit."""
    work = repo["work"]
    _git(work, "checkout", "-q", "main")
    _git(work, "merge", "-q", "--squash", "release/v0.2.29")
    _commit(work, "feat(release): v0.2.29 (#1)", {})
    fix = _commit(work, "fix(release): the check", {"src/devops_cli/a.py": "A = 3\n"})
    _git(work, "tag", "-a", "v0.2.29", "-m", "v0.2.29")
    _git(work, "push", "-q", "--follow-tags", "origin", "main")
    return fix


@pytest.mark.parametrize(
    "make_head",
    [lambda repo: _merge(repo, {"src/devops_cli/a.py": "A = 3\n"}), _later_push, _recovery],
    ids=["the-release-merge", "a-later-push", "the-push-that-recovers-a-failed-release"],
)
def test_main_never_replaces_the_image_it_pins_and_still_points_latest_at_it(
    repo: dict[str, Any], make_head: Callable[[dict[str, Any]], str]
) -> None:
    """A tree with other inputs than the published image ships them in the next release."""
    head = make_head(repo)
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    attested = {"sha256:aaa": _signer(BRANCH)}
    code, out, log = _plan(repo, head, MAIN, "0.2.29", {"v0.2.29": published}, attested)
    assert (code, out["action"], out["digest"], "ship in the next release" in log) == (
        0,
        "promote",
        "sha256:aaa",
        True,
    )


def test_main_points_latest_at_an_image_its_own_run_built(repo: dict[str, Any]) -> None:
    """A release merged over a failed check was built by main's run, signed on main."""
    later = _later_push(repo)
    published = f"sha256:aaa {_inputs(repo['work'], later)}"
    attested = {"sha256:aaa": _signer(MAIN)}
    code, out, _ = _plan(repo, later, MAIN, "0.2.29", {"v0.2.29": published}, attested)
    assert (code, out["action"]) == (0, "promote")


def test_main_refuses_an_image_release_yml_did_not_attest(repo: dict[str, Any]) -> None:
    merged = _merge(repo)
    published = f"sha256:aaa {_inputs(repo['work'], repo['cut'])}"
    attested = {"sha256:aaa": _signer("refs/heads/feature")}
    code, out, log = _plan(repo, merged, MAIN, "0.2.29", {"v0.2.29": published}, attested)
    assert (code, out.get("action"), "no provenance" in log) == (1, None, True)


def test_main_builds_a_missing_image_with_latest(repo: dict[str, Any]) -> None:
    merged = _merge(repo)
    code, out, _ = _plan(repo, merged, MAIN, "0.2.29")
    assert (code, out["action"], out["latest"]) == (0, "publish", "true")


def test_main_fails_closed_when_ghcr_cannot_be_read(repo: dict[str, Any]) -> None:
    merged = _merge(repo)
    code, out, _ = _plan(repo, merged, MAIN, "0.2.29", {"v0.2.29": "!ERROR: i/o timeout"})
    assert (code, out.get("action")) == (1, None)


def test_the_branch_tip_tags_its_attested_digest(repo: dict[str, Any]) -> None:
    code, created, _ = _tag(repo, repo["cut"], BRANCH, f"{IMAGE}:v0.2.29")
    assert (code, created) == (0, [f"--tag {IMAGE}:v0.2.29 {IMAGE}@sha256:bbb"])


def test_main_tags_the_image_it_built_with_latest(repo: dict[str, Any]) -> None:
    merged = _merge(repo)
    code, created, _ = _tag(repo, merged, MAIN, f"{IMAGE}:v0.2.29\n{IMAGE}:latest")
    assert (code, created) == (
        0,
        [f"--tag {IMAGE}:v0.2.29 --tag {IMAGE}:latest {IMAGE}@sha256:bbb"],
    )


def test_a_release_merged_during_the_build_keeps_the_image_main_pins(
    repo: dict[str, Any],
) -> None:
    """The plan ran before the merge; the tag step sees main holding the version and stops."""
    _merge(repo)
    code, created, log = _tag(repo, repo["cut"], BRANCH, f"{IMAGE}:v0.2.29")
    assert (code, created, "never replaced" in log) == (1, [], True)


def test_a_run_superseded_during_the_build_leaves_the_tag_to_the_tip(
    repo: dict[str, Any],
) -> None:
    _commit(repo["work"], "fix", {"src/devops_cli/a.py": "A = 2\n"})
    _git(repo["work"], "push", "-q", "origin", "release/v0.2.29")
    code, created, log = _tag(repo, repo["cut"], BRANCH, f"{IMAGE}:v0.2.29")
    assert (code, created, "no longer the tip" in log) == (0, [], True)
