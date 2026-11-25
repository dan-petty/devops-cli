### Problem Description

The review of #4811 (issue #4738, merged) found two problems in the design token checks:

1. The CI step "Run the Design Tests" of the job `design-tokens` has a limit of 2 minutes, but the bound of one test is 600 s (`timeout = 600` in `pyproject.toml`). This breaks the rule "Nested Time Limits" of ARCHITECTURE.md: "Set the bound of one test shorter than its step." When a design test hangs, the runner stops the step at 120 s, and pytest-timeout gives no diagnostic. The contract test of the job checks step < job, but not test < step.
2. Each color in `design/tokens/*.tokens.json` holds its value two times: `components` and `hex`. Style Dictionary reads only `components`, and no check compares the two. When a person edits only `hex`, the outputs do not change, the CI diff step passes, and the source shows a color that no output has.

### Reproduction Steps

1. `grep -n -A3 "Run the Design Tests" .github/workflows/ci.yml` shows `timeout-minutes: 2` and `uv run pytest tests/design -n 0` with no `--timeout`.
2. In a checkout of `main`, change `"hex": "#ffffff"` of `color.bg` in `design/tokens/light.tokens.json` to `#fffffe`, and run `make design-tokens` with the locked Style Dictionary.
3. `git diff --stat` shows only the source file. `uv run pytest tests/design` passes.

### Expected vs Actual Behavior

Expected: the bound of one design test is shorter than its step, and a check fails when the `hex` of a source color is not the color of its `components`.

Actual: the test bound (600 s) is longer than the step (120 s), and a `hex` that differs from `components` passes every check.

### Environment Diagnostics

`main` at the merge of #4811; Style Dictionary 5.8.0 from `src/devops_cli/tools_lock/style-dictionary/`.

### Logs, Traces, or Terminal Output

After step 2: `git diff --stat` gives `design/tokens/light.tokens.json | 2 +-` and no output file. The design tests take 10.7 s in total, and 0.8 s at most for one test.

### Pre-Submission Checklist

- [x] I have verified that no sensitive credentials, private keys, or internal tokens are contained in this issue report.
- [x] I have checked existing issues and pull requests to ensure this is not a duplicate.


<!-- devops-roadmap-record {"Effort": "Low", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium", "intake.jev_shadow": "{\"at\":\"2026-11-12T02:53:08Z\",\"answers\":{\"priority\":[\"P1-High\",0.53,\"P2-Medium\"],\"value\":[\"High\",0.3,\"Medium\"],\"effort\":[\"Medium\",0.61,\"Low\"],\"duplicate\":[\"\",0.14,\"\"]}}"} -->
