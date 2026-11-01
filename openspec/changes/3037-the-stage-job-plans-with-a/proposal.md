# Proposal

## Why

The stage job (#2654) asks the model for one `StageProposal` on a fixed context. The model cannot read the repository, and its prompt says "You cannot run a command". #3037 reports the result: 25 of the 37 plans of 2026-11-01 name files that do not exist, and plans ignore code and tests that exist. #3037 asks for a planner with read-only tools and a bounded budget. The planner writes the commands it ran and what they showed into `Feasibility`. The gates stay as they are.

## What Changes

- The stage planner runs a pydantic-ai agent with nine read-only tools: list files, read a file or a line range, search code, git log, git show, the symbols of a file, the callers of a symbol, a repository map, and a read of a base spec. It has no write tool and no network tool.
- The tools reuse `InvestigationTools` of refine. They read the staged commit through git. `StageTools` adds six tools.
- A plan run stops at 30 tool calls or at 50000 output tokens. The item then fails, and the failure names the limit that was hit.
- The comment of a staged item lists the tool calls and the tokens of the plan run.
- The stage prompt asks the model to call the tools first and to write each command and its result in `feasibility`.
- `devops roadmap eval stage` plans with the toolbox. The new option `--no-toolbox` plans with the one call of today, so two runs of the same model compare.
- `investigate` takes optional limits, output retries and a trace. Refine and the alternatives check keep their behavior.
- The change has spec deltas. The planner, its budget and the comment of a staged item are observable behavior of `devops roadmap stage`. The option `--no-toolbox` is a command option.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-stage`: the planner has a read-only toolbox, a plan run has a budget, a toolbox run keeps the return rules of a broken reply, and the comment of a staged item reports the plan run
- `roadmap-stage-eval`: the live run plans with the toolbox unless `--no-toolbox` is given, and the command group lists the new option

## Impact

- Code: `src/devops_cli/roadmap/agent_run.py`, `src/devops_cli/roadmap/refine_investigation.py`, `src/devops_cli/roadmap/stage_tools.py` (new), `src/devops_cli/roadmap/stage_toolbox.py` (new), `src/devops_cli/roadmap/stage.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/commands/roadmap.py`, `src/devops_cli/commands/roadmap_eval_stage.py`, `src/devops_cli/roadmap/stage_eval_run.py`, `src/devops_cli/roadmap/stage_eval_render.py`, `src/devops_cli/roadmap/implement_eval_run.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`
- Prompts: `src/devops_cli/ai/tasks/roadmap_stage_tools.md` (new), `src/devops_cli/ai/tasks/roadmap_stage_change.md`
- Documents: `CONTEXT.md`, `docs/ROADMAP_WORKFLOW.md`, and the generated command documents
- Tests: `tests/roadmap/test_roadmap_refine_investigation.py`, `tests/ai/client/test_roadmap_agent_run.py`, `tests/roadmap/test_roadmap_stage_tools.py` (new), `tests/roadmap/test_roadmap_stage_toolbox.py` (new), `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/test_roadmap_stage_job.py`, `tests/roadmap/test_roadmap_stage_command.py`, `tests/roadmap/test_roadmap_stage_apply.py`, `tests/roadmap/test_roadmap_stage_eval_run.py`, `tests/roadmap/test_roadmap_stage_eval_command.py`

## Existing code to reuse and to keep passing

- `InvestigationTools`, `investigate`, `InvestigationStopped` and `_within_budget` in `src/devops_cli/roadmap/refine_investigation.py`. Refine and the alternatives check call `investigate`. Their tests (`tests/roadmap/test_roadmap_refine_investigation.py`, `tests/roadmap/test_roadmap_alternatives.py`, `tests/roadmap/test_roadmap_refine.py`) stay green after each group.
- `drain_events` and `record_run_spend` in `src/devops_cli/roadmap/agent_run.py`. A toolbox run goes to the spend ledger as refine's run does.
- `StageClient`, `RecordingClient`, `plan_item`, `check_proposal` and the path check (`stage_paths.py`). The toolbox client implements `StageClient`, so the planner, the gates and the golden-set run stay as they are.
- `TreeSitterEngine.parse_file` and `generate_repo_map` for the symbol tools. `git grep` for the callers.
- The pins on the stage prompt in `tests/roadmap/test_roadmap_stage_plan.py` and `tests/roadmap/test_roadmap_stage_kind.py`.
- The base requirements "A reply that breaks the schema returns once", "The plan names files that exist at the staged commit" and "A failure stops one item and never hides the others" of `roadmap-stage`. The toolbox run keeps all three.

## Acceptance

- "The planner runs with the toolbox in a scratch clone and has no write tool and no network tool": groups 2, 3 and 4. The tools read the staged commit through git on the clone that the job already has (`model_clone`), or on the detached worktree of the eval. No tool writes, so a second copy of the tree adds nothing.
- "The score of A1 on the 37 cases is higher with the toolbox than without it": group 6 adds `--no-toolbox`, and group 7 documents the comparison. The comparison itself needs a model through the gateway: pending a person (see "Workflow follow-up" in `tasks.md`).
- "The tool calls and tokens of a plan run are in the trace (A3)": groups 1 and 5. The trace of #3032 is open. This change keeps the calls and the tokens of the plan run in the comment of the staged item, and #3032 can read the same `RunTrace`.
- "A plan run stops at its budget and reports the reason": groups 1, 3 and 4.
- The design asked that the budget be configurable per run. No criterion asks for it. The budgets of refine and of the alternatives check are constants, and a setting adds a schema entry, a variable and documents. So the budget is a constant.

## Feasibility

Checked on `origin/main` (de52216e) in a worktree of the plan branch.

- The planner makes one call and has no tools. `git grep -n chat_structured -- src/devops_cli/roadmap/stage.py` prints the `StageClient` protocol (line 578) and one call in `_Planner._ask` (line 645). `grep -n "cannot run a command" src/devops_cli/ai/tasks/roadmap_stage_change.md` prints line 9.
- The agent loop exists in refine, not in stage. `git grep -n "UsageLimits(" -- src/devops_cli/roadmap/refine_investigation.py` prints line 255, and `git grep -n -E "def (search_code|list_files|read_file|search_web)" -- src/devops_cli/roadmap/refine_investigation.py` prints the four tools of `InvestigationTools`. Three of them are the first three tools of the toolbox. They read a commit with `git grep`, `git ls-tree` and `git show`, and write nothing.
- The pydantic-ai version (2.59.0) has `UsageLimits(tool_calls_limit, output_tokens_limit, request_limit)`. The messages of a stop are "Exceeded the output_tokens_limit of N" and the like, so the stop names the limit. `_within_budget` reads `request_limit`, so the stage run must set it.
- The counts of the issue, from the golden set: a script over `tests/fixtures/roadmap_eval/stage/*/case.json` counts, among the 37 plans with a verdict other than `good`, 25 with a defect `missing_path`, 15 with `ignores_existing_code` (the issue says 17) and 34 with `false_premise`. So the premise holds. The count of `ignores_existing_code` is 15 in the recorded set.
- Newer work: #3036 (merged) made the job refuse a plan with a missing path (`git log --oneline -1 -- src/devops_cli/roadmap/stage_paths.py` prints 334f0ead). That gate sends a wrong reply back once. It does not make the first reply right, and the eval scores the first reply. So the toolbox is not superseded. #3011 and #3012 are open and ask for probes and callers in the context. They have no pull request, they use another mechanism, and they do not delete anything this plan uses. No code of this plan was deleted after the issue: `git log --oneline -3 -- src/devops_cli/roadmap/refine_investigation.py` prints only older commits.
- `git grep -c -i toolbox -- openspec/specs src` prints nothing, so no spec or code has the toolbox yet.
- The AST graph does not fit as a tool. `devops ai ast graph --dir src/devops_cli/roadmap -n 100` took 110 s for 52 files (1317 symbols). `CodeGraphBuilder` with `max_files` 5, 10 and 20 took 0.3 s, 0.6 s and 19.2 s. The cost grows with the square of the symbols (`_link_call_edges` in `src/devops_cli/ai/ast/graph.py` tests each symbol name against each body), and the files are the first N found, not the files that matter. A tool call must not take 110 s. So the toolbox gives the symbols of one file instead: `TreeSitterEngine().parse_file(Path("src/devops_cli/roadmap/stage.py"))` found 90 symbols in 0.04 s. The callers come from `git grep` on the commit, which is fast on the whole repository, and which uses the rule of the graph (a name followed by `(`).
- `generate_repo_map(Path("src/devops_cli/roadmap"))` took 0.3 s and gave 137092 characters for 50 files. A tool answer is cut to 4000 characters (`cut`), so `repo_map` takes a directory and at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files.
- The base spec file `openspec/specs/roadmap-stage/spec.md` is long, and `read_file` returns at most 120 lines. So `read_spec` lists the requirement names and returns the whole text of one requirement. That is what a `MODIFIED` delta must copy.
- First checks of the implementation: `uv run devops ci test tests/roadmap/test_roadmap_refine_investigation.py`, `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py`, `uv run devops openspec check`.

## Existing Tool Considered

pydantic-ai, which the project already uses for refine's investigation, runs the agent loop, the tool calls and the usage limits. `git` and tree-sitter (`TreeSitterEngine`) read the repository. The change builds one thin layer on them: six tools, a client that implements `StageClient`, and a trace of the run. The cost is about 600 lines of code and tests to write, a small cost to keep because the tools are git and tree-sitter calls, and about two hours to build and fix. It deletes no code. It does not copy `InvestigationTools`: `StageTools` extends it.
