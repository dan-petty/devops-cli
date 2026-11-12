# Proposal: #4906

## Why

The review of the design token build found two gaps in its checks. Closes #4906.

1. The CI step "Run the Design Tests" has a limit of 2 minutes, but the bound of one test is 600 s (`timeout = 600` in `pyproject.toml`). ARCHITECTURE.md, "Nested Time Limits", says: "Set the bound of one test shorter than its step." When a design test hangs, the runner stops the step at 120 s, and pytest-timeout gives no diagnostic.
2. Each DTCG source color holds its value two times, in `components` and in `hex`. Style Dictionary reads only `components`, and no check compares the two. When a person edits only `hex`, the outputs do not change, the CI diff step passes, and the source shows a color that no output has.

## What Changes

- The step "Run the Design Tests" of the job `design-tokens` runs `uv run pytest tests/design -n 0 --timeout 60`. The bound of one test (60 s) is shorter than the step (120 s).
- The contract test of the job asserts that the bound of one design test is more than 0 and shorter than its step.
- A new test in `tests/design/test_tokens.py` asserts that the `hex` of each of the 66 source colors is the color of its `components`.
- `docs/DESIGN.md` tells a person to give a color the same value in `components` and in `hex`, and lists the new check.

The change alters no behavior that a consumer observes: it changes tests, a CI workflow and a document. It has no spec delta and sets `skip_specs: true`.

## Capabilities

None. The change adds checks to the existing `design-tokens` build and changes no requirement.

## Impact

- `.github/workflows/ci.yml`: the job `design-tokens`.
- `tests/invariants/test_workflow_contracts.py`, `tests/design/test_tokens.py`.
- `docs/DESIGN.md`: "Change a token" and "Checks".

The change fits one pull request.

## Feasibility

- `grep -n -A3 "Run the Design Tests" .github/workflows/ci.yml` on `main` shows `timeout-minutes: 2` and no `--timeout`. `pyproject.toml` sets `timeout = 600`. The pytest-timeout option `--timeout` overrides the ini value for one run.
- `uv run pytest tests/design -n 0 --durations=3` takes 10.7 s for the 16 tests, and 0.8 s at most for one test. A bound of 60 s leaves a large margin and is half of the step limit.
- With the locked Style Dictionary 5.8.0, a change of `"hex": "#ffffff"` of `color.bg` in `design/tokens/light.tokens.json` to `#fffffe`, then `make design-tokens`, changes only the source file. The build reads `components`.
- All 66 source colors are `srgb` with 3 components and a 7-character `hex`. coloraide 8.14.1 gives the same hex from the components of each of them, so the new test passes on `main` and fails on the changed `hex`.

## Existing Tool Considered

- pytest-timeout, already a test dependency, sets the bound of one test with `--timeout`. The change adds no tool.
- coloraide, already a test dependency, converts the `components` of a DTCG color to hex. The test uses it and adds no color math of its own.
- The change deletes no internal code.
