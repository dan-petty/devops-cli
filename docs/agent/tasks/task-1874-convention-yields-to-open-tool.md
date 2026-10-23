# Task: A Convention Yields to an Open Tool, and Rules With No Check or a Contradiction Are Pruned (#1874)

**Issue**: [#1874](https://github.com/dan-petty/devops-cli/issues/1874)
**Scope**: type/docs, scope/docs, scope/ai
**Feasibility**: The author checked this on 2026-10-22. The author read the rules in `AGENTS.md` and searched `tests/` and `src/` for a check of each rule that the item deletes. No check exists for any of them. The author ran the replacement measures on this tree. The results are in the section "Feasibility Evidence".

## Description

`AGENTS.md` told an agent to name the open tool before it builds. The same file also told the agent to meet "all project standards and conventions" and not to relax "lint rules". No rule said which line wins. An agent that replaced a bespoke check with a standard tool read the swap as lowering a threshold, and kept the bespoke code. Some rules also contradicted each other, and the file had no room for a new rule.

- **Precedence.** The bullet "Open Tools Before Internal Code" now says that a convention is never a reason to keep or write custom code. It also says that the bullet outranks every convention in the file.
- **Never lower.** The bullet "Continuous Standards Compliance" is merged into the bullet "Never Lower Security Standards or Quality Thresholds". The merged bullet keeps one sentence of the old bullet: "Every change meets the project standards." The merged bullet separates lowering a threshold from replacing a check with a tool. A tool replaces a check when it enforces at least the same property on this repository. The PR runs both checks once and shows both results.
- **Contradictions.** Agents run `intake --confirm` for their own new candidates, as the bullets on defect filing and roadmap synthesis say. The suspended-Service bullet now agrees with them. The bullet "Stop Rather Than Add Compensating Code" asks a person to run `roadmap return --confirm`, because that command stays with a person. The text that `devops ai agents` writes for this repository says the same.
- **Pruned rules.** The rule on `Gated` terminology, the headroom targets, the bullet on forward-looking project management and the section 1 naming bullet are gone. The sentence on an empty issue queue is gone from `AGENTS.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, the knowledge base guide `github_project_management.md` and the generator. The section 4 naming bullet keeps the naming rule.
- **Reworded rules.** The bullets on dispatch style, the Python ecosystem, secrets and root-cause remediation say what outcome they want. The secrets rule gives examples of a secret store, so its list is open. `docs/ROUTINE_TASKS.md` states the same outcome.
- **Shipped copy.** `devops ai agents` writes the never-lower bullet into other repositories. `src/devops_cli/ai/instruction_generator.py` now writes the new wording and no longer writes the continuous-compliance bullet. The generator also writes the new root-cause wording.
- **Linked guides.** `docs/SELF_IMPROVEMENT.md` and `docs/VISION.md` no longer state the deleted headroom targets. `docs/SELF_IMPROVEMENT.md` says that a check guards a recurring problem. It says that a rule goes into `AGENTS.md` only when no check is possible.
- Pending a person: apply the item that intake folded into this issue, "agents reach GitHub through the paced session and workflow steps use the runner's `gh`". The item changes the bullet "Strict Prohibition of Bare `gh` CLI Invocations". The GitHub request budget design changes that rule, so this PR leaves it as it is. The issue body does not list the item, so a person files it as its own issue.

## Feasibility Evidence

- **Size.** `AGENTS.md` had 39,954 characters. It has 38,850 after the change. The change frees 1,104 characters, and the cap is 40,000.
- **Gated terminology.** A search of `tests/` and `src/` finds no test or code that enforces the `Gated` terminology rule or the numbered-gate ban.
- **Headroom targets.** `uv run ruff check src --select C901` at a limit of 6 reports 371 functions. At the cap of 10 it reports none. The project collector `devops_cli.core.code_metrics` counts 557 functions deeper than 3 and none deeper than 5. Nothing enforced the targets, and the cap of 10 and 5 in the same file already bounded the code.
- **Empty queue.** A search of `tests/` and `src/` finds no check of the sentence on an empty issue queue.
- **Roadmap commands.** `uv run devops roadmap intake --help` shows that a candidate an agent files with `--title` and `--body-file` is labeled `source/agent` and held to the filing quota. The same help shows that intake without `--title` works on every open issue that is not on the board. The suspended-Service bullet keeps that second use with a person.
- **Replacement tools.** No check is replaced in this item. Every deleted rule had no check, so no pair of runs applies. The new text keeps the checks that exist: Ruff `C901` and `N`, the architectural invariant tests, `detect-private-key`, `bandit` and `tests/test_zero_plaintext_invariants.py`.
- **Secret stores.** ADR 0004 keeps the machine-account token in a cluster Secret. The repository also reads the GitHub token from the credential store of `gh`. The old text named only the OS keyring and Vault.

## Acceptance Criteria

- [x] `AGENTS.md` is 1,104 characters shorter than before the change, at 38,850 of 40,000. `tests/test_agents_md_claims.py` passes.
- [x] The compliance bullet is merged into the never-lower bullet, which keeps one sentence of it. The "Open Tools Before Internal Code" bullet carries the precedence sentences.
- [x] No line tells an agent to run a command that another line reserves for a person. This holds for `AGENTS.md` and for the generator.
- [x] The generator no longer writes the continuous-compliance bullet, and its never-lower bullet separates lowering from replacing.
- [x] No document keeps the empty-queue sentence or the headroom targets.
- [x] `uv run devops docs check` finds the generated documents current.
- [x] `devops ci` passes.

## Deliverables

- [x] `AGENTS.md`: the precedence sentences, the merged never-lower bullet, the pruned rules and the reworded rules.
- [x] `src/devops_cli/ai/instruction_generator.py` and `tests/test_instruction_generator.py`: the new never-lower, root-cause and `roadmap return` wording, and the deleted continuous-compliance bullet and empty-queue sentence.
- [x] `docs/ROUTINE_TASKS.md`, `docs/SDLC.md`, `docs/SELF_IMPROVEMENT.md`, `docs/VISION.md` and `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`: the matching statements.
- [x] `docs/agent/tasks/task-1874-convention-yields-to-open-tool.md` and `changelog.d/1874.md`.
