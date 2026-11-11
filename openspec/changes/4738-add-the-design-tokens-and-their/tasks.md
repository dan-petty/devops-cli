# Tasks

## 1. Behavior: the tokens and their package module

- [x] 1.1 Write the tests of `tests/design`: name parity, the contrast rules, the categorical gates, the ramps, the breakpoint literals and the dash patterns
  - Verification: `$ uv run pytest tests/design -n 0`
- [x] 1.2 Add the token sources, the Style Dictionary configs, `make design-tokens`, the committed outputs and `devops_cli.design`
  - Verification: `$ uv run pytest tests/design -n 0`

## 2. Behavior: the build pipeline

- [x] 2.1 Write the contract tests of the CI job, the Renovate rule and the devcontainer install
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_workflow_contracts.py tests/tools_lock/test_tools_lock.py tests/invariants/test_devcontainer_config.py`
- [x] 2.2 Add the lock, the CI job "Design Tokens", the Renovate rule and the install in the devcontainer image
  - Verification: `$ uv run pytest -n 0 tests/invariants/test_workflow_contracts.py tests/tools_lock/test_tools_lock.py tests/invariants/test_devcontainer_config.py`
- [x] 2.3 Write the rule test and add the ast-grep rule `css-color-literal`, with its entry in the construct gate
  - Verification: `$ uv run devops ci --check --only constructs`

## 3. Documents

- [x] 3.1 Add `docs/DESIGN.md`, ADR 0024, the row of `AGENTS.md`, the line of `docs/index.md` and the job section of `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- #4777: add the `tools.lock` entry of Style Dictionary when the dependencies of a release that is 14 days old have no audit finding.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
