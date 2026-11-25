# Design

## Decisions
- Add `"lizard==1.26.1"` (exact pin matching `[project.optional-dependencies] review`) to `[dependency-groups] dev` in `pyproject.toml`, because `uv sync` / `uv run` installs the `dev` group by default across fresh worktrees and clones.
- Keep `review = ["lizard==1.26.1"]` in `[project.optional-dependencies]` untouched so `--no-dev --extra review` image builds keep working unchanged.
- Add `tests/invariants/test_review_extra_present.py` asserting `importlib.util.find_spec("lizard") is not None` with a failure message naming `uv sync --all-extras`, plus a test overriding `importlib.util.find_spec` to verify the failure text.
- List `test_review_extra_present.py` in `docs/TESTING.md` under `tests/invariants/` so `test_invariant_files_are_listed_in_testing_doc` remains satisfied.

## Rejected alternatives
- Skip `review_window` tests when `lizard` is absent: hides environment drift in local worktrees and fails `devops ci --check --only git` equivalence.
- Modify `read_tags` to stop using `for-each-ref creatordate`: `devops ci --check --only git` passes with `git 2.55.0` and `tests/core/test_git_contract.py` never starts real `git`.
- Re-record `review_window.json` without `lizard`: breaks CI runs where `--all-extras` installs `lizard`.
