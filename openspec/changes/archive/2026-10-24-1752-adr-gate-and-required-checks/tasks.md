# Tasks

## 1. Record the decision

- [x] 1.1 Read the `main` ruleset, the CI job times and the Copilot review state (`uv run devops gh api repos/dan-petty/devops-cli/rulesets/21466414`)
- [x] 1.2 Write ADR 0014 with the decision, the evidence, the considered options and the consequences (`uv run devops docs check`)
- [x] 1.3 Add the amendment line that names ADR 0014 to ADR 0004 (`uv run devops docs check`)
- [x] 1.4 Run the OpenSpec gate (`uv run devops openspec check`)

## Workflow follow-up

- The pre-push hook `devops-ci-pre-push` and the documents that say it runs the full `devops ci` change in #2110.
- Pending a person: make sure that the personal Copilot setting "Automatic Copilot code review" is off.
