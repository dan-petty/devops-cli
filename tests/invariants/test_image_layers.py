"""Image layer invariants: the dependencies of the runner and Service images lie in layers that a
change of `src/` or a release keeps (#4550).

A release changes `src/` and the project version in `pyproject.toml` and `uv.lock`. The stages
under a final stage build from the requirements that the `lock` stage exports without the project,
so they keep their cache, and each node keeps their layers. The final stages are never cached
(`no-cache-filters`), so they take only the project from `builder` and run only the upgrade of
the apt packages. The tests read only the committed `Dockerfile`, so they need no network and no
image build.
"""

from __future__ import annotations

import pytest

from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT

FINAL_STAGES = ("runner", "service")
SITE_PACKAGES = "/app/.venv/lib/python3.14/site-packages"
PROJECT_COPY = [
    "COPY",
    "--from=builder",
    "--parents",
    f"{SITE_PACKAGES}/devops_cli",
    f"{SITE_PACKAGES}/devops_cli-*.dist-info",
    "/app/.venv/bin/devops",
    "/",
]
UV_CACHE_MOUNT = "--mount=type=cache,target=/root/.cache/uv"


def _stages() -> dict[str, list[list[str]]]:
    return stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


def _runs(stage: list[list[str]]) -> list[str]:
    return [" ".join(words[1:]) for words in stage if words[0].upper() == "RUN"]


def _bases(all_stages: dict[str, list[list[str]]], name: str) -> list[str]:
    """The stages that `name` builds on, the nearest first."""
    found: list[str] = []
    base = all_stages[name][0][1]
    while base in all_stages:
        found.append(base)
        base = all_stages[base][0][1]
    return found


def _copies_from_context(stage: list[list[str]]) -> list[list[str]]:
    return [
        words
        for words in stage
        if words[0].upper() == "COPY" and not any(w.startswith("--from=") for w in words)
    ]


def test_the_lock_stage_exports_the_requirements_without_the_project() -> None:
    """Verify that the `lock` stage writes the runtime and the dev requirements of `uv.lock`
    without the project, so a release that changes only the project version gives the same files.
    The runtime requirements hold the extra `review`, which the images install (#4686).
    """
    lock = _stages()["lock"]
    exports = [
        command.split()
        for run in _runs(lock)
        for command in run.split("&&")
        if "uv export" in command
    ]

    assert _copies_from_context(lock) == [["COPY", "pyproject.toml", "uv.lock", "./"]]
    assert sorted(
        (
            words[words.index("-o") + 1],
            [word for word in words if word in ("--no-dev", "--only-dev")],
            [words[i + 1] for i, word in enumerate(words) if word == "--extra"],
            "--locked" in words,
            "--no-emit-project" in words,
        )
        for words in exports
    ) == [
        ("/lock/dev.txt", ["--only-dev"], [], True, True),
        ("/lock/runtime.txt", ["--no-dev"], ["review"], True, True),
    ]


@pytest.mark.parametrize("final", FINAL_STAGES)
def test_the_dependency_layers_of_an_image_hold_no_file_of_the_project(final: str) -> None:
    """Verify that no stage under a final stage builds on `builder` or copies a file of the build
    context, so a change of `src/`, `pyproject.toml` or `uv.lock` alone keeps their layers."""
    all_stages = _stages()
    bases = _bases(all_stages, final)

    assert "builder" not in bases
    assert {name: _copies_from_context(all_stages[name]) for name in bases} == {
        name: [] for name in bases
    }


def test_the_dependency_stages_install_the_requirements_of_the_lock_with_their_hashes() -> None:
    """Verify that `deps` installs the runtime requirements and `runner-deps` the dev requirements
    that they copy from the `lock` stage, with every hash checked."""
    all_stages = _stages()
    installs = {
        name: [run for run in _runs(all_stages[name]) if "uv pip" in run]
        for name in ("deps", "runner-deps")
    }
    lock_copies = {
        name: [words[1:] for words in all_stages[name] if "--from=lock" in words]
        for name in ("deps", "runner-deps")
    }

    assert lock_copies == {
        "deps": [["--from=lock", "/lock/runtime.txt", "/lock/runtime.txt"]],
        "runner-deps": [["--from=lock", "/lock/dev.txt", "/lock/dev.txt"]],
    }
    assert {
        name: [("--require-hashes" in run.split(), lock_copies[name][0][2] in run) for run in runs]
        for name, runs in installs.items()
    } == {"deps": [(True, True)], "runner-deps": [(True, True)]}


@pytest.mark.parametrize("final", FINAL_STAGES)
def test_a_final_stage_takes_only_the_project_from_the_builder(final: str) -> None:
    """Verify that a final stage copies only the `devops_cli` package, its dist-info and its
    console script from `builder`, in one layer, to the paths of the venv of its base."""
    stage = _stages()[final]

    assert [words for words in stage if "--from=builder" in words] == [PROJECT_COPY]


@pytest.mark.parametrize("final", FINAL_STAGES)
def test_a_final_stage_upgrades_the_apt_packages_and_installs_none(final: str) -> None:
    """Verify that a final stage, which no build caches, runs the apt upgrade before it copies
    the project, and leaves every package install to the cached stages under it."""
    stage = _stages()[final]
    upgrade = next(
        index
        for index, words in enumerate(stage)
        if words[0].upper() == "RUN" and "apt-get upgrade" in " ".join(words)
    )

    assert [run for run in _runs(stage) if "apt-get install" in run] == []
    assert upgrade < stage.index(PROJECT_COPY)


def test_every_uv_install_keeps_the_uv_cache_out_of_the_layers() -> None:
    """Verify that each `uv sync` and `uv pip` of the file mounts the uv cache of root, so no
    layer holds the cache and no stage must delete it."""
    unmounted = [
        f"{name}: {' '.join(words[1:])[:80]}"
        for name, stage in _stages().items()
        for words in stage
        if words[0].upper() == "RUN"
        and any(tool in " ".join(words) for tool in ("uv sync", "uv pip"))
        and UV_CACHE_MOUNT not in words
    ]

    assert unmounted == []
