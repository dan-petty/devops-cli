# Proposal

## Why

`LabelColor` names its design token only in a comment. The token files of #4738 now exist, so a token value can change while the label colors keep the old value, and no test fails (#4786).

## What Changes

- `workflow_labels.py` holds `LABEL_COLOR_TOKENS`, the token of each `LabelColor` member.
- A test reads `tokens-base.json` and `tokens-light.json` and asserts that each member equals its token value.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/workflow_labels.py`
- Tests: `tests/roadmap/test_roadmap_labels_file.py`

## Feasibility

- The token files hold the hex values.
- The existing test already reads the label colors.
- Verification commands: `uv run devops ci test tests/roadmap/test_roadmap_labels_file.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

The test reads the JSON that Style Dictionary writes, with the standard library. No library.
