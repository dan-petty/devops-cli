# Proposal

## Why

A new `devops` command or a new test touches several places whose rules are scattered, and an agent that misses one breaks CI, as #3182 and #3190 record. #3204 asks for a scaffold that writes those places in project form, refuses to overwrite, prints the remaining manual steps, and computes the shared lists that need no hand edit.

## What Changes

- Add the `devops new` group with the `command` and `test` subcommands, registered in the command specs of the CLI.
- The command scaffold writes the command function in the group module, the help and message entries, the mirror-path test with a failing first test and `match=`, and prints the manual steps that remain.
- The test scaffold writes a test module at the mirror path of a source module, asks for the shared fake of the edge that the module reaches, and refuses a path that is not a source module.
- The command scaffold adds a command to a group that exists and refuses an unknown group. The scaffold refuses to write over an existing file and writes nothing under `--dry-run`.
- The MCP coverage test derives its excluded commands from the command tree, so a new command needs no hand entry.
- The hand-written class of the docs inventory becomes the complement of its other classes, so a new page needs no hand entry.
- The layout section of `docs/TESTING.md` states the mirror path as the one test-location rule and drops the flat-file fallback.
- A skill names both scaffold commands in each agent skill root (`.claude/skills/` and `.agents/skills/`), held by an invariant test.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `new-command-scaffold`: The new group lists the command and test subcommands, The command scaffold writes the command module and the language entries, The command scaffold writes the test at the mirror path, The help that the scaffold writes is short and names its page, The scaffold prints the steps that remain manual, The test scaffold writes the test at the mirror path, The test scaffold refuses a path that is not a source module, The test that the scaffold writes asks for the fake of its edge, The scaffold refuses to write over a file, A dry run writes nothing, A skill names both scaffold commands
- `project-form-checks`: The MCP coverage test derives the excluded commands, An unmatched docs page is hand-written, The test document states the mirror rule as the only rule

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/config/constants.py`, `src/devops_cli/docs/inventory.py` (new), `src/devops_cli/docs/markdown_argv_collector.py`, `src/devops_cli/commands/new.py`, `src/devops_cli/main.py`, `src/devops_cli/lang/en/help.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/scaffold/` (new: `edges.py`, `edits.py`, `plan.py`), `src/devops_cli/templates/scaffold_*.j2` (new)
- Documents: `docs/TESTING.md`, `CONTRIBUTING.md`, `.claude/skills/new-scaffold/SKILL.md`, `.agents/skills/new-scaffold/SKILL.md`, `.gitignore`
- Tests: `tests/docs/test_docs_inventory.py`, `tests/invariants/test_architectural_invariants.py`, `tests/invariants/test_agents_md_claims.py`, `tests/ai/mcp/test_mcp.py`, `tests/commands/test_new.py`, `tests/scaffold/` (new), `tests/invariants/test_skills.py`

## Feasibility

- The run exposed no repository tool, so this plan cites the `probes` lines and the files of `context` only.
- `probes`: "The path `tests/ai/mcp/test_mcp.py` is a file of the staging commit." That file holds `test_all_cli_commands_are_either_exposed_or_excluded`, whose docstring is "Exhaustive coverage test fails if any CLI command is neither exposed nor in exclusions." The excluded set is a hand-written tuple inside the test, and it already holds `("roadmap", "eval", "verify"),`, the entry that #3182 needed. The last line is `assert (unaccounted, extra) == (set(), set())`, so a new command with no entry fails the check.
- `probes`: "The path `docs/TESTING.md` is a file of the staging commit." Its migration section still says "Until the move into the mirror, a new test joins the file that already tests its behaviour, flat or already in its mirror directory such as `tests/ai/review/`, or else goes into a new flat file named after the behaviour.", beside the mirror target "`tests/` mirrors the package tree of `src/devops_cli` at full depth *(target)*". The two rules stand side by side, as the issue says.
- `probes`: "The path `src/devops_cli/config/constants.py` is a file of the staging commit." `context` names its readers as `src/devops_cli/config/constants.py` and `src/devops_cli/docs/markdown_argv_collector.py`, and its tests as `tests/docs/test_docs_inventory.py`, `tests/invariants/test_architectural_invariants.py` and others.
- `probes`: "The path `tests/test_constants.py` is no file of the staging commit." and "The path `tests/config/test_constants.py` is no file of the staging commit. No commit in the history deleted or renamed it." Both are outputs that the scaffold writes under a temporary directory, and neither is a premise that a commit removed.
- The three-sentence help rule is real: capability `roadmap-command-help` holds "The help of a job command is a short summary that names its page".
- The dry-run class of a command is real: capability `command-dry-run-class` holds the requirement "command-declares-dry-run-class", and `context` lists `tests/invariants/test_dry_run_class_ratchet.py` as a test of that class. The scaffold group declares the class of each new command with the decorator that the ratchet reads, and no table of dry-run classes exists.
- The premise holds, so the plan compensates for nothing. First checks against the real system: `uv run devops new --help` must list `command` and `test`; `uv run devops ci test tests/ai/mcp/test_mcp.py` must pass with no hand list; `uv run devops ci docs` must pass on the new `docs/TESTING.md`; `uv run devops openspec check` must accept this change.

- Checked again at the implement stage, against the code of `origin/main`: `docs/TESTING.md` no longer holds the flat-file fallback, so the change adds the one sentence that states the mirror rule for a new file. `CONST_DOCS_INVENTORY` has five readers beside the collector (the inventory test, the task-file scan, the two-link test, the OpenSpec scaffold test and the TUI config test), and only three of them read the hand-written class. `jinja2` is a dependency and `devops_cli.core.templating.render_template` renders packaged templates, so the scaffold uses them and builds no template engine. `.gitignore` ignores every `.claude/skills/*` folder but the OpenSpec ones, so the Claude copy of the skill needs one negation line.

## Existing Tool Considered

Copier is the open, maintained generator: it renders a local template set with no network call. Its update mode rewrites the files that it once rendered, so it fits a new folder and not a tree that must never be overwritten. The issue records the cost to build the two commands with a built-in template set instead: about 150k tokens and 8 hours, plus the upkeep of the templates each time a rule changes, and the guard tests that hold the templates in step. The in-house code that this change deletes: the hand-written exclusion tuple of `test_all_cli_commands_are_either_exposed_or_excluded` in `tests/ai/mcp/test_mcp.py`, and the per-file hand-written entries of `CONST_DOCS_INVENTORY`.
