# Proposal

## Why

Issue #3006: the implement step of the runner gives the agent no rule for scratch files. On #2175 the agent wrote `test_get_ollama_semaphore.py` in the checkout root, `mypy --strict` failed on it, and the step stopped with the work done. The step commits with `git add -A`, so a scratch file can also reach the pull request.

## Feasibility

- `git grep -n scratch src/devops_cli/ai/tasks/roadmap_implement_step.md` prints nothing on `origin/main`.
- `git grep -n 'add", "-A"' src/devops_cli/roadmap/implement_step.py` shows the step stages the whole checkout.
- `.gitignore` ignores `.data/*`, so `.data/agent/scratch/` is a safe place (AGENTS.md rule 12).

## Existing Tool Considered

No external tool covers this. The change adds one rule to a prompt file and one test.

## What Changes

- `src/devops_cli/ai/tasks/roadmap_implement_step.md` gets a rule: scratch files go under `.data/agent/scratch/`, none in the checkout root, `src/`, `tests/` or `docs/`, no check runs on a scratch file.
- `tests/roadmap/test_roadmap_implement_prompt.py` fails if the prompt lacks the rule.
- The change has no spec delta: no `devops` command, option or message changes.

## Impact

- The runner agent of the implement job. Any other agent that changes code is covered by AGENTS.md rule 12.
