# Proposal: #4641

## Why

`devops ai agents` writes a Python `AGENTS.md` for every project (#4641). `ProjectMetadata` sets `requires_python` to `>=3.14` and the check commands to `uv run pytest`, `uv run ruff check` and `uv run mypy src` when the project does not give them. `parse_project_metadata` reads only `pyproject.toml`. So a folder with only `Cargo.toml` gets "It runs on Python `>=3.14`" and three checks that it cannot run. The template has 11 rules and `AGENTS.md` has 14, and no test finds the drift. The model path sends the ARCHITECT review persona as its system prompt. 5 of the 6 other repositories have no `AGENTS.md`, so onboarding (#3770) writes one with this tool.

## What Changes

- `parse_project_metadata` detects the manifests `pyproject.toml`, `Cargo.toml`, `package.json` and `go.mod` (`CONST_AGENTS_MD_MANIFESTS`). The template writes a toolchain line only for the manifests that exist, and none when there is no manifest.
- The check line comes only from the pre-push hooks. A project with no pre-push hook gets no check line. `DEFAULT_AGENTS_MD_CHECK_COMMANDS` and `DEFAULT_PYTHON_REQUIRES` are deleted.
- The `devops ci fail-to-pass` sentence of rule 4 renders only for a Python project.
- A plan-system slot: the OpenSpec sentence of rule 1 renders only when `openspec/config.yaml` exists.
- The model path sends `generate_agents.md` as its own short system prompt, with the detected toolchains, checks and documents, and no review persona. The project context holds each detected manifest.
- The template rules take the titles of the `AGENTS.md` rules. A new invariant test compares the rule titles of the template, rendered for devops-cli, with those of `AGENTS.md`, less a named list of the two rules that only devops-cli has. It compares titles, not bytes, because `AGENTS.md` is near its character cap.

The output of a devops command changes, so the change carries a spec delta.

## Capabilities

- `agent-instructions` (modified): ADDED requirements for the detected toolchain and checks, the system prompt of the model path, and the rule-title check.

## Impact

- `src/devops_cli/ai/instruction_generator.py`, `src/devops_cli/templates/AGENTS.md.j2`, `src/devops_cli/ai/tasks/generate_agents.md`, `src/devops_cli/commands/ai.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/config/defaults.py`.
- The `AGENTS.md` that `devops ai agents` writes for devops-cli names the same two pre-push checks as before. The existing `AGENTS.md` of a repository does not change, because the command does not replace it without `--force`.
- The change fits one pull request.

## Feasibility

On `main` at `c9513687`, `uv run devops ai agents --repo <folder> --template --file AGENTS.md` for a folder that holds only `Cargo.toml` wrote "It runs on Python `>=3.14`." and "**Run the checks before each push:** `uv run pytest`, `uv run ruff check`, `uv run mypy src`." The same command on the branch writes "It uses Rust." and no Python, uv, pytest, ruff or mypy word. `AGENTS.md` has 14 numbered rules and `AGENTS.md.j2` had 11 (counted with the markdown parser in the new invariant test).

## Existing Tool Considered

The template stays Jinja2. The project kit (#3753) moves the template into Copier later. Manifest detection reads 4 standard file names, so no tool is necessary. Cost to build: about 50 lines and 6 tests, about 200,000 tokens and 2 hours, and little to keep. The change deletes `DEFAULT_AGENTS_MD_CHECK_COMMANDS`, `DEFAULT_PYTHON_REQUIRES` and `_get_agents_task_addendum`.
