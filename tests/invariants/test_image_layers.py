"""Image layer invariants: the dependency stages of the runner and Service images install the
requirements of the lock with every hash checked (#4550).

The tests read only the committed `Dockerfile`, so they need no network and no image build.
"""

from __future__ import annotations

from tests.support.dockerfile import stages
from tests.support.paths import REPO_ROOT


def _stages() -> dict[str, list[list[str]]]:
    return stages((REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"))


def _runs(stage: list[list[str]]) -> list[str]:
    return [" ".join(words[1:]) for words in stage if words[0].upper() == "RUN"]


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
