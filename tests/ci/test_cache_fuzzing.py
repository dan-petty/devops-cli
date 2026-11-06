"""Property-based fuzzing tests for git porcelain v1 status parsing in CI cache.

Grounds property assertions in the git-status(1) porcelain v1 format specification:
Format is `XY PATH` or `XY ORIG_PATH -> PATH` where X shows index status,
Y shows worktree status, column 3 is a space delimiter, and paths with special characters
may be enclosed in double quotes.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import HealthCheck, Phase, example, given, settings
from hypothesis import strategies as st

from devops_cli.ci.cache import worktree_divergent_paths
from tests.support.fakes.process import ProcessAnswer, ProcessFake

_FUZZ_SETTINGS = settings(
    phases=[Phase.explicit, Phase.generate],
    derandomize=True,
    max_examples=35,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

_VALID_INDEX_STATES = ("M", "A", "D", "R", "C", "U", "?", "!", " ")
_VALID_WORKTREE_STATES = ("M", "D", "U", "?", "!", " ")


@_FUZZ_SETTINGS
@given(
    entries=st.lists(
        st.tuples(
            st.sampled_from(_VALID_INDEX_STATES),
            st.sampled_from(_VALID_WORKTREE_STATES),
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyz0123456789_./-",
                min_size=1,
                max_size=30,
            ),
            st.booleans(),
        ),
        min_size=0,
        max_size=10,
    )
)
@example(entries=[])
@example(entries=[(" ", "M", "src/core.py", False)])
@example(entries=[("M", " ", "README.md", False)])
@example(entries=[("?", "?", "new_file.py", False)])
@example(entries=[(" ", "D", "deleted.py", False)])
@example(entries=[("D", " ", "staged_delete.py", False)])
@example(entries=[("R", " ", "old.py -> new.py", False)])
@example(entries=[(" ", "M", "path with spaces.txt", True)])
def test_git_status_porcelain_v1_divergent_paths_specification(
    entries: list[tuple[str, str, str, bool]],
    process_fake: ProcessFake,
) -> None:
    """git-status(1) porcelain v1: parses index and worktree status columns and paths.

    Asserts that:
    - 'D' in worktree or index status classifies path as deleted
    - Unstaged modifications (worktree != ' ') or untracked ('?') classify as changed
    - Quoted paths and rename targets ('old -> new') are properly unwrapped.
    """
    lines: list[str] = []
    expected_changed: list[str] = []
    expected_deleted: list[str] = []

    for idx_state, wt_state, path_val, is_quoted in entries:
        raw_path = f'"{path_val}"' if is_quoted else path_val
        line = f"{idx_state}{wt_state} {raw_path}"
        lines.append(line)

        target_path = path_val.split(" -> ", 1)[1] if " -> " in path_val else path_val
        if wt_state == "D" or idx_state == "D":
            expected_deleted.append(target_path)
        elif wt_state != " " or idx_state == "?":
            expected_changed.append(target_path)

    stdout_text = "\n".join(lines)

    process_fake.answer("git status", ProcessAnswer(stdout=stdout_text))
    changed, deleted = worktree_divergent_paths(Path("/dummy/repo"))

    assert (changed, deleted) == (expected_changed, expected_deleted)


@_FUZZ_SETTINGS
@given(
    short_lines=st.lists(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=0, max_size=3),
        min_size=1,
        max_size=5,
    )
)
@example(short_lines=["", " ", "M ", "??"])
def test_git_status_porcelain_v1_short_lines_skipped_specification(
    short_lines: list[str],
    process_fake: ProcessFake,
) -> None:
    """git-status(1) porcelain v1: lines shorter than 4 characters are incomplete and skipped."""
    stdout_text = "\n".join(short_lines)
    process_fake.answer("git status", ProcessAnswer(stdout=stdout_text))
    changed, deleted = worktree_divergent_paths(Path("/dummy/repo"))

    assert (changed, deleted) == ([], [])
