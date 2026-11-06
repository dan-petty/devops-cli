# Tasks

## 1. State the mirror path as the one test-location rule

Reads: `docs/TESTING.md`, `AGENTS.md`. Changes: `docs/TESTING.md`.

- [x] 1.1 In the Layout section of `docs/TESTING.md`, state that a new test module sits at the mirror path of its source module and in the folder of the behaviour it tests. Remove the sentence that lets a new test join a flat file until the migration ends. Keep the rule that an invariant test joins the file of its subject in the invariants folder
  - Verification: `uv run devops ci docs` passes
- [x] 1.2 `docs/TESTING.md`: the Layout section states the mirror path as the one rule for a new test file, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs` passes

## 2. Classify an unmatched docs page as hand-written

Reads: `src/devops_cli/config/constants.py`, `src/devops_cli/docs/markdown_argv_collector.py`, `tests/docs/test_docs_inventory.py`, `tests/invariants/test_architectural_invariants.py`, `tests/invariants/test_agents_md_claims.py`. Changes: the same files, and `src/devops_cli/docs/inventory.py` (new).

- [x] 2.1 In `tests/docs/test_docs_inventory.py`, write first: a page at a docs path that no other class matches is classified hand-written, and a page that another class claims stays out of the hand-written class
  - Verification: `uv run devops ci test tests/docs/test_docs_inventory.py` fails on the base
- [x] 2.2 Make the hand-written class the complement of the other classes: delete its entries from `CONST_DOCS_INVENTORY`, add `src/devops_cli/docs/inventory.py` with the classifier, and read the hand-written documents through it in the collector, the inventory test, the task-file scan and the two-link test
  - Verification: `uv run devops ci test tests/docs/test_docs_inventory.py` passes

## 3. Derive the MCP excluded commands from the command tree

Reads: `tests/ai/mcp/test_mcp.py`, `src/devops_cli/main.py`, `src/devops_cli/core/command_resolver.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/ai/mcp/generator.py`. Changes: `tests/ai/mcp/test_mcp.py`.

- [x] 3.1 In `test_all_cli_commands_are_either_exposed_or_excluded`, delete the hand-written exclusions tuple. Walk the commands of `_COMMAND_SPECS` as the test does today, take the exposed set from `CONST_MCP_EXPOSURE_TABLE`, and assert that an exposure entry resolves to a command of the tree and that no exposed path is also excluded
  - Verification: `uv run devops ci test tests/ai/mcp/test_mcp.py` passes

## 4. Add the devops new test subcommand

Reads: `src/devops_cli/main.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/commands/mcp.py`, `tests/commands/test_openspec_scaffold.py`, `tests/invariants/test_dry_run_class_ratchet.py`. Changes: `src/devops_cli/commands/new.py` (new), `src/devops_cli/main.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_new.py` (new).

- [x] 4.1 In `tests/commands/test_new.py`, write first: the scaffold for a module of the source package writes a test module at the mirror path of that module; a path outside the source package exits nonzero and names the mirror path; a second run exits nonzero, names the existing target and leaves it as it was; `--dry-run` lists the target and writes nothing
  - Verification: `uv run devops ci test tests/commands/test_new.py` fails on the base
- [x] 4.2 Create the `new` group in `src/devops_cli/commands/new.py` with the `test` subcommand, register the group in `src/devops_cli/main.py`, and add its help entries to `src/devops_cli/lang/en/help.py`. Compute the mirror path from the module path, refuse a path that is not a module of the source package, refuse to write over an existing file, and print the plan under `--dry-run`. Declare the dry-run class of each command with the `@dry_run_class` decorator on its function, which is the record that `tests/invariants/test_dry_run_class_ratchet.py` reads
  - Verification: `uv run devops ci test tests/commands/test_new.py` passes

## 5. Add the devops new command subcommand and its templates

Reads: `src/devops_cli/commands/new.py`, `tests/commands/test_new.py`, `src/devops_cli/lang/en/help.py`, `tests/commands/test_openspec_scaffold.py`, `tests/invariants/test_dry_run_class_ratchet.py`. Changes: `src/devops_cli/commands/new.py`, `src/devops_cli/scaffold/` (new), `src/devops_cli/templates/scaffold_*.j2` (new), `tests/commands/test_new.py`.

- [x] 5.1 In `tests/commands/test_new.py`, in a temporary repository that holds the source, language and test folders: `devops new command sample hello` writes the command function in the group module, its help and message entries, and a test at the mirror path of that module with a failing first test and `match=`; the help holds at most three sentences and names the page of its command; the output names `devops docs generate --sync-readme`; and `--dry-run` writes no file
  - Verification: `uv run devops ci test tests/commands/test_new.py` fails on the base
- [x] 5.2 Hold the templates in `src/devops_cli/templates/scaffold_*.j2` and render them from the `command` subcommand of `src/devops_cli/commands/new.py`. Compute every target path, refuse to write over an existing file, print the target paths under `--dry-run`, and print only the steps that remain manual. Declare the dry-run class of the subcommand with the `@dry_run_class` decorator on its function. Give the test that it writes the fake fixture of the edge that the group module reaches
  - Verification: `uv run devops ci test tests/commands/test_new.py` passes

## 6. Add the skill that calls both scaffold commands

Reads: `AGENTS.md`, `tests/invariants/test_agents_md_claims.py`. Changes: `.claude/skills/new-scaffold/SKILL.md` (new), `.agents/skills/new-scaffold/SKILL.md` (new), `tests/invariants/test_skills.py` (new), `CONTRIBUTING.md`, `.gitignore`.

- [x] 6.1 Write a short skill in `.claude/skills/new-scaffold/SKILL.md` and the same skill in `.agents/skills/new-scaffold/SKILL.md`, because the project commits its agent skills in each agent root and an agent reads only its own. The skill names `devops new command` and `devops new test` and sends the reader to the checklist that the scaffold prints. Link both skills from `CONTRIBUTING.md`, so they sit within two links of `AGENTS.md`, and let `.gitignore` keep the Claude skill. Add an invariant test that fails when the skill of either root does not name both commands, or when the two roots hold different text
  - Verification: `uv run devops ci test tests/invariants/test_skills.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
