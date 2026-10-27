# Design

## Context

See proposal.md - Why. `HELP.k8s.stack` defines a static help string that only names `infra | llm | all`.

## Goals / Non-Goals

**Goals:**
- Centralize accepted stack values in `CONST_K8S_VALID_STACKS` in `src/devops_cli/config/constants.py`.
- Re-use `CONST_K8S_VALID_STACKS` for `VALID_STACKS` in `networking.py` and `stack_lifecycle.py`.
- Dynamically format `HELP.k8s.stack` using `CONST_K8S_VALID_STACKS`.
- Ensure tests verify that all valid stacks appear in the help string.

**Non-Goals:**
- Modify stack deployment logic or change the set of accepted stacks.

## Decisions

### Centralize stack definition in constants.py
Declare `CONST_K8S_VALID_STACKS: Final[tuple[str, ...]] = ("infra", "llm", "logging", "devops", "gitea", "all")` in `src/devops_cli/config/constants.py`.
- *Rationale*: `constants.py` has only standard library dependencies. `src/devops_cli/lang/en/help.py` can import it without circular dependencies.
- *Rejected Alternative*: Import `VALID_STACKS` directly from `src/devops_cli/commands/k8s/networking.py` into `help.py`. Rejected because `networking.py` imports `HELP` from `devops_cli.lang`, creating a circular import cycle.

### Format help string dynamically
Format `HELP.k8s.stack` as `f"Stack to operate on: {' | '.join(CONST_K8S_VALID_STACKS)}."`.
- *Rationale*: Guarantees that any stack added to `CONST_K8S_VALID_STACKS` is automatically included in the CLI help of all commands sharing `HELP.k8s.stack`.
- *Rejected Alternative*: Manually updating the static string to `"Stack to operate on: infra | llm | logging | devops | gitea | all."`. Rejected because future stack additions would cause help to become stale again.

## Risks / Trade-offs

- [Generated docs drift] → Run `devops docs generate --sync-readme` and verify with `devops docs check`.
