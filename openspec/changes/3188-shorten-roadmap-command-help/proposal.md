# Proposal

## Why

Issue #3188: the help of six `devops roadmap` commands is as long as a specification. In characters: `implement` 3,977, `refine` 2,115, `stage` 1,573, `alternatives` 1,448, `intake` 1,322 and `inbox` 1,002. `devops roadmap --help` lists each command with the start of that text, so the list does not fit one screen. The same text also sits in the specs and in `docs/ROADMAP_WORKFLOW.md`, so one change has to be made in more than one place.

## What Changes

- Cut the help of the commands `intake`, `refine`, `alternatives`, `stage`, `implement` and `inbox` (`RoadmapCommandHelp` in `src/devops_cli/lang/en/help.py`) to a summary of two sentences, and add one sentence that names the page of the job. The help of an option stays as it is. No command name, option or behavior changes.
- Add one page for each job: `docs/roadmap/intake.md`, `refine.md`, `alternatives.md`, `stage.md`, `implement.md` and `inbox.md`. A page holds the description that left the help, in the order of the work of the job, and a table that names the spec that holds the rules. A page states a fact only when no spec states it. Add the glob `docs/roadmap/*.md` to the hand-written class of `CONST_DOCS_INVENTORY`, so `devops docs check` resolves every `devops` command that a page names, and link the pages from `docs/index.md`.
- Replace the two bullets of `docs/ROADMAP_WORKFLOW.md` that repeat the help of `inbox` and `refine` with a sentence and a link to the page.
- Replace the one test that asserts a sentence of the long help (the request count of `inbox`, in `tests/roadmap/test_roadmap_inbox_command.py`) with a test of the plan of the reads, and state the rule in the spec `roadmap-inbox`. The count "5 requests, or 6" in the old help was the count for two pages of issues on the day it was written; the rule is one request for each 100 rows.
- Add a test (`tests/roadmap/test_roadmap_command_help.py`) that fails when the help of one of the six commands has more than three sentences or does not name an existing page. It is the check that fails if the problem returns.
- Regenerate `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md` and `docs/MCP_TOOLS.md` with `devops docs generate --sync-readme`.
- A command, an option text and a message are observable, so the change carries a spec delta: a new capability `roadmap-command-help`, and a MODIFIED requirement of `roadmap-inbox`.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-command-help`: the length of the help of the job commands and the page that each one names.

### Modified Capabilities

- `roadmap-inbox`: the requirement "The inbox reads a bounded number of requests and writes none" states the number of requests of a run, and has a scenario for the plan of the reads.

## Impact

- Code: `src/devops_cli/lang/en/help.py` (six strings) and `src/devops_cli/config/constants.py` (one glob).
- Tests: `tests/roadmap/test_roadmap_inbox_command.py` loses `test_the_help_states_how_many_requests_a_run_sends`. `tests/roadmap/test_roadmap_inbox_requests.py` gains one test. `tests/roadmap/test_roadmap_command_help.py` is new.
- Documents: six new pages, and edits of `docs/index.md` and `docs/ROADMAP_WORKFLOW.md`. The generated files listed above change.
- Consumers of the help: an MCP client reads the first paragraph of a command help as the description of its tool (`docs/MCP_TOOLS.md`). It now reads a summary and the path of a page. `tests/ai/mcp/test_mcp.py` only asserts that a description is not empty.
- Code, specs and tests this change keeps: the rules of the jobs stay in `openspec/specs/roadmap-*/spec.md`. No requirement is deleted.

## Acceptance

| Criterion of #3188 | Where |
| :--- | :--- |
| The help of each command is a summary of one to three sentences, and the help of the options stays | `tests/roadmap/test_roadmap_command_help.py` |
| The long description is in one document for each job under `docs/`, linked from the help | `docs/roadmap/*.md`, the same test |
| `devops docs check` checks each command that a page names | The inventory glob, `uv run devops ci docs` |
| One source for each fact: the rules stay in the specs, and the page points to them | The tables "Where the rules are" in the pages |
| A test or a snapshot that asserts a sentence of the long help moves to the page or the spec | Feasibility, third point |

## Feasibility

The checks ran on 2026-11-02 in a clone at `origin/main` (commit 6f648d59).

- **The sizes in the issue are true.** `RoadmapCommandHelp` in `src/devops_cli/lang/en/help.py` gave 3,977, 2,115, 1,573, 1,448, 1,322 and 1,002 characters for `implement`, `refine`, `stage`, `alternatives`, `intake` and `inbox` (`len(getattr(RoadmapCommandHelp(), name))`). Five more commands have 575 to 837 characters (`run`, `eval_stage`, `eval_implement`, `explain`, `intake_eval`). The issue names six commands, so the other five are not in this change.
- **What reads the long strings.** `git grep -n 'HELP.roadmap\.' src` finds them only in the `help=` arguments of `src/devops_cli/commands/roadmap.py`. No test, spec or snapshot imports `RoadmapCommandHelp`. The long text flows into four generated files. `devops docs generate --sync-readme` changed exactly `README.md` (the command matrix), `docs/CLI_REFERENCE.md`, `docs/commands/roadmap.md` and `docs/MCP_TOOLS.md` (the tool descriptions), and no other file. The `docs/commands/roadmap.md` file went from 30,451 to 20,371 characters.
- **What asserts a sentence of the long help.** I took every clause of the eleven long commands, cut them into 5-word windows, and ran `git grep -F -f` over `tests`, `openspec`, `docs`, `src`, `k8s` and the root documents. Two kinds of match came out. Most matches are the same rule stated in a spec or in the code (for example the `roadmap-implement-step` spec states the programs of the shell). They do not read the help, so they stay. One test reads the help: `tests/roadmap/test_roadmap_inbox_command.py::test_the_help_states_how_many_requests_a_run_sends` asserts "5 requests, or 6 when the labels differ" and "one more for each 100 open issues and pull requests" in the output of `roadmap inbox --help`. The tests that run `--help` for the other commands (`tests/commands/test_all_commands_help_dryrun.py` asserts exit code 0, `tests/commands/test_cli_startup_imports.py` asserts that a module stays unloaded, and `tests/roadmap/test_roadmap_stage_eval_command.py::test_the_group_lists_the_stage_command` asserts the word `stage`) read no sentence. `tests/ai/mcp/test_mcp.py` asserts only a non-empty description. The snapshot `tests/roadmap/__snapshots__/test_roadmap_intake.ambr` holds the prompt of the model, not the help.
- **The inbox count was stale.** The plan of the reads (`inbox_requests` in `src/devops_cli/roadmap/request_plan.py`) holds three listings that repeat "per page, while GitHub links a next one", one read of the labels file, and one conditional commit read. The "5 requests" of the old help came from the archived proposal of #2915, which counted 2 pages of issues on that day. The rule is one request for each 100 rows. The new test pins that plan, and the spec states it.
- **No spec asserts a sentence of the long help.** The only spec that names `--help` is `roadmap-stage-eval` ("`devops roadmap eval --help` lists `stage`"), and the commands it names are unchanged.
- **Facts that live only in the help.** I compared the six strings with the specs of the jobs. These facts have no spec line, so the pages state them: the candidate rule of intake (an open issue with no `priority/*` label), the fields that intake writes and their order, `source/agent` and the secret refusal, the comparison with issues closed as not planned, the three modes; the selection order and the wait rules of refine as an overview; the verdict values and the body block of the alternatives check; the branch, commit and pull request text of stage and the row `stage_ready`; the inputs, the exit checks, the stray-file clean-up and the workstation start of implement; and the lines and reads of inbox. These facts also sit in a spec, so the page names the spec: the duplicate verdict and no close (`roadmap-intake-duplicates`), the list of items that stage leaves out (`roadmap-stage`), and the items that alternatives takes (`roadmap-alternatives`). The pages of `implement` and `inbox` keep a short statement of the order of the work, because a reader needs it before the specs, which split it into many requirements.
- **`devops docs check` resolves the names.** `src/devops_cli/docs/markdown_argv_collector.py` checks the classes in `CONST_DOCS_NAME_CHECKED_CLASSES`: prompt and hand-written. The generated files are not checked, so the commands that the old help named (`devops gh issues close`, `devops k8s run-job`, `devops argo cd apps status`) were not checked. `tests/docs/test_docs_inventory.py` fails for a Markdown file in no class, so the new pages need the glob. With the glob, those commands are checked on the pages.

## Existing Tool Considered

Typer and Click print the help they are given, and no open tool shortens it. The `docs` tooling of this repository (`devops docs generate`, `devops docs check`) already generates the references and checks the names, and the change uses it. The change is an edit of text, a glob and two tests. The cost to build: about 60,000 tokens and 3 hours of elapsed time. The upkeep is small: a rule changes in its spec and the page keeps a pointer, and the new test fails if a help grows again. No internal code is deleted, except one help-text test that the new plan test replaces.
