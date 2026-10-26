# Design

## Where the pin lives

`uv check` takes its `ty` version from the first of these that applies:

1. The `--ty-version` option.
2. The exact version in `uv.lock`, when `ty` is a project dependency or a dependency in the `dev` group.
3. A constrained range (`>=0.0,<0.1`) of `ty`.

Today the step uses the third source, so every `ty` release in the range reaches `main` with no change in the repository.
The change moves the step to the second source with one `ty==0.0.92` entry in the `dev` group. This is the same place that pins `ruff`, `mypy`, `bandit`, `actionlint-py` and `zizmor`.
A person raises the pin in a pull request, and that pull request shows the new diagnostics before they reach `main`.

## Rejected alternatives

- **Pass `--ty-version 0.0.92` in the `uv-check` step of `devops ci`.**
  It works, but it keeps a second version number in Python code, away from `uv.lock`, `uv audit` and the outdated-dependency check. The `dev` group is the documented source.
- **Only remove the `cast`.**
  Pull request #2283 did it already. It fixes this release of `ty` and leaves the cause: the next release can add a new diagnostic and fail `main` again.
- **Let `uv check` use the range and suppress `redundant-cast` in `[tool.ty.rules]`.**
  It lowers a quality threshold, and only the owner can allow that.

## Test

The test reads `pyproject.toml` and `uv.lock` and compares the two. It holds no version number, so a later raise of the pin does not change the test.
It runs no `ty` and reaches no network, as `docs/TESTING.md` requires. The `uv-check` step of `devops ci` is the check that `ty` passes.
