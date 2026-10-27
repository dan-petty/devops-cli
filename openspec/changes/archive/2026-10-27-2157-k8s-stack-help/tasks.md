# Tasks

## 1. Kubernetes stack help naming every stack

- [x] 1.1 Add failing tests asserting that `HELP.k8s.stack` and commands using it contain all values from `VALID_STACKS`; verify failure with `uv run pytest tests/test_k8s_networking.py -k test_k8s_stack_help_names_every_valid_stack`
- [x] 1.2 Define `CONST_K8S_VALID_STACKS` in `src/devops_cli/config/constants.py`, bind `VALID_STACKS` to it in `src/devops_cli/commands/k8s/networking.py` and `src/devops_cli/commands/k8s/stack_lifecycle.py`, and dynamically format `HELP.k8s.stack` in `src/devops_cli/lang/en/help.py`; verify with `uv run pytest tests/test_k8s_networking.py -k test_k8s_stack_help_names_every_valid_stack`
- [x] 1.3 Regenerate CLI reference documentation with `uv run devops docs generate --sync-readme` and verify with `uv run devops docs check`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
