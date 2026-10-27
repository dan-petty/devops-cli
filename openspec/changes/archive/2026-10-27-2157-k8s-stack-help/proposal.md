# Proposal

## Why

Issue #2157: `devops k8s deploy-stack --help` says for `--stack`: "Stack to operate on: infra | llm | all." The command accepts more stacks. `VALID_STACKS` in `src/devops_cli/commands/k8s/networking.py:68` contains `("infra", "llm", "logging", "devops", "gitea", "all")`. The help string does not name `logging`, `devops`, or `gitea`. When contributors add a new stack, a hardcoded help string becomes incorrect again.

## What Changes

- Declare `CONST_K8S_VALID_STACKS` in `src/devops_cli/config/constants.py` as the single source of truth for valid stacks.
- Reference `CONST_K8S_VALID_STACKS` for `VALID_STACKS` in `src/devops_cli/commands/k8s/networking.py` and `src/devops_cli/commands/k8s/stack_lifecycle.py`.
- Update `HELP.k8s.stack` in `src/devops_cli/lang/en/help.py` to format all items of `CONST_K8S_VALID_STACKS` dynamically.
- Regenerate the CLI documentation to reflect the updated help text.
- Add an automated test that fails if any item in `VALID_STACKS` is missing from the help text.
- This change alters command help text observed by users, so it includes a new capability specification delta: `k8s-stack-help`.
- This change fits one pull request.

## Capabilities

### New Capabilities

- `k8s-stack-help`: help documentation for Kubernetes stack commands dynamically names every valid stack.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/config/constants.py`
- `src/devops_cli/commands/k8s/networking.py`
- `src/devops_cli/commands/k8s/stack_lifecycle.py`
- `src/devops_cli/lang/en/help.py`
- `docs/CLI_REFERENCE.md`
- `docs/commands/k8s.md`
- `tests/test_k8s_networking.py`

## Feasibility

- Running `uv run devops k8s deploy-stack --help` produces `--stack: Stack to operate on: infra | llm | all.`
- Inspection of `src/devops_cli/commands/k8s/networking.py:68` and `src/devops_cli/commands/k8s/stack_lifecycle.py:286` confirms `VALID_STACKS` contains `("infra", "llm", "logging", "devops", "gitea", "all")`.
- `CONST_K8S_VALID_STACKS` in `src/devops_cli/config/constants.py` can be imported by `src/devops_cli/lang/en/help.py` with zero circular import risk.
- Verification with `uv run pytest tests/test_cli_startup_imports.py` confirms importing constants does not exceed startup module limits.

## Existing Tool Considered

Python standard library tuple constants and string joining format the help string from the constant. No custom parser or external library is needed. The redundant tuple literal in `stack_lifecycle.py` and `networking.py` is removed in favor of `CONST_K8S_VALID_STACKS`.
