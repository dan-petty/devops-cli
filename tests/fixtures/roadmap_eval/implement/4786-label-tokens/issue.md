### Problem or Motivation

- #4652 gives each workflow label and each label of `.github/labels.yml` a color of `LabelColor` (`src/devops_cli/roadmap/workflow_labels.py`). A test holds each label color to `LabelColor`.
- Each member of `LabelColor` names its design token only in a comment. The token files of #4738 (`src/devops_cli/design/tokens-light.json` and `tokens-base.json`) are not on `main` yet, so no test holds `LabelColor` to the token values.
- When a token value changes, the label colors stay on the old value, and no test fails. The design spec plan of #4735 asks for a test that every label color is a token hex value.

### Proposed Solution & Architectural Design

- Give each `LabelColor` member its token name in code, not in a comment (for example a mapping from the member to the token name).
- A test reads the token JSON files of `src/devops_cli/design/` and asserts that each `LabelColor` value is the value of its token.

### Target Subsystem

SDLC, Git & PR Governance (`src/devops_cli/roadmap/workflow_labels.py`).

### Existing Tool Considered

Style Dictionary builds the token files (#4738). The test reads its JSON output with the standard library. Cost: about 15 lines and 1 test, about 40,000 tokens and 30 minutes.

### Acceptance Criteria

- [ ] A test fails when a `LabelColor` value is not the hex value of the token that the member names in the token files of `src/devops_cli/design/`.

### Dependencies

#4652, #4738.


Source: https://github.com/dan-petty/devops-cli/issues/4652

<!-- devops-roadmap-record {"Effort": "Low", "Priority": "P2-Medium", "Status": "In Review", "Value": "Medium"} -->
