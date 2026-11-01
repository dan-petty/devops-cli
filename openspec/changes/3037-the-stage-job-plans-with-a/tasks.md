# Tasks

## 1. Define read-only tool set and sandbox

Reads: none. Changes: `src/devops_cli/roadmap/stage_tools.py` (new), `tests/test_roadmap_stage_tools.py` (new).

- [ ] 1.1 Write a failing test that asserts the stage job exposes only read-only tools (list files, read file, grep, git log, git show, AST graph, callers, repomap, read spec) and no write or network tool, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` fails on the base
- [ ] 1.2 Create a new module that defines the read-only tool schemas: list files, read file, read line range, grep, git log, git show, AST graph, callers of symbol, devops ai repomap, and read base spec. Create a git worktree on the staged commit for the sandbox. Set the sandbox to have no network and no write access. Register the tools with the existing agent loop. Write a failing test first that asserts the tool set contains only read-only tools and no write or network tool, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` passes

## 2. Enforce budget and record trace

Reads: none. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/stage_tools.py`, `tests/test_roadmap_stage_tools.py`.

- [ ] 2.1 Write a failing test that asserts a plan run stops at 30 tool calls or 50000 tokens and the trace records the limit that was hit, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` fails on the base
- [ ] 2.2 Add budget constants (30 tool calls, 50000 tokens) to the config module. Enforce the budget in the agent loop: when either limit is hit, stop the run and record the reason in the job record. Record each tool call with its arguments and the cumulative token count in the trace. Write a failing test first that asserts a plan run stops at the budget and the trace records the limit, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` passes

## 3. Write evidence into Feasibility

Reads: none. Changes: `src/devops_cli/roadmap/stage_tools.py`, `tests/test_roadmap_stage_tools.py`.

- [ ] 3.1 Write a failing test that asserts the plan output includes a Feasibility section with the tool calls and their output summaries, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` fails on the base
- [ ] 3.2 Modify the plan output builder to include the tool calls and their output summaries in the Feasibility section of the plan. The planner writes the commands it ran and what they showed. Write a failing test first that asserts the plan output includes a Feasibility section with the tool calls and their output summaries, and verify that `uv run devops ci test tests/test_roadmap_stage_tools.py` passes

## 4. Update documentation

Reads: none. Changes: `CONTEXT.md`.

- [ ] 4.1 Update the Step definition in CONTEXT.md to note that the stage job planner uses the agent loop with read-only tools. Add the budget and trace to the Stage job description in the glossary, and verify that `uv run devops ci --only openspec` passes
- [ ] 4.2 CONTEXT.md, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
