# Tasks

## 1. Add the one tool registry

Reads: `src/devops_cli/ai/mcp/roles.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/config/settings.py`, `docs/roadmap/stage.md`. Changes: `src/devops_cli/roadmap/tools.py` (new), `tests/roadmap/test_roadmap_tools.py` (new).

- [x] 1.1 Write the failing tests in `tests/roadmap/test_roadmap_tools.py`: each entry has a one-line purpose, a boolean read-only flag and a holder, `tool_names` raises for an unknown holder, `check_tables` names a table and its missing tool, and the real role tables and toolset holders pass the check
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py` fails on the base
- [x] 1.2 Add `src/devops_cli/roadmap/tools.py` with the `ToolEntry` record, the `TOOLS` table for the holders `stage`, `stage-extended`, `implement`, `planning`, `implementation` and `review`, and the functions `tool_names` and `check_tables`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_tools.py` passes

## 2. Choose the stage tools from the registry

Reads: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/config/defaults.py`. Changes: `src/devops_cli/roadmap/stage/stage_tools.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.

- [x] 2.1 Add a failing test in `tests/roadmap/stage/test_roadmap_stage_tools.py` that `StageTools.tools()` names the methods of the `stage` holder, and with `extended` also the three of `stage-extended`, in table order
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` fails on the base
- [x] 2.2 Replace the method list of `StageTools.tools()` with the names that `tool_names` gives for `stage`, plus `tool_names` of `stage-extended` when the toolset is `extended`, and wrap each named method with `Tool(method, takes_ctx=False)`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` passes

## 3. Choose the role tables from the registry

Reads: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/ai/mcp/roles.py`. Changes: `src/devops_cli/ai/mcp/roles.py`, `tests/ai/mcp/test_mcp_roles.py`.

- [ ] 3.1 Add a failing test in `tests/ai/mcp/test_mcp_roles.py` that each job role table equals `tool_names(role)`, that the three role counts stay 28, 17 and 16, and that a name outside the registry is still refused
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_roles.py` fails on the base
- [ ] 3.2 Build `_JOB_ROLE_TOOLS` from `tool_names(role)` for each role of `JOB_ROLES`, keep the `ops` role on the whole catalogue, and keep the read-only filter and the missing-tool refusal of `tools_for_role`
  - Verification: `$ uv run devops ci test tests/ai/mcp/test_mcp_roles.py` passes

## 4. Add the implement and review toolset settings

Reads: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `src/devops_cli/roadmap/tools.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_limit_classes.py`. Changes: `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [ ] 4.1 Add failing tests in `tests/roadmap/stage/test_roadmap_stage_settings.py` for the `base` default of `roadmap.implement.toolset` and `roadmap.review.toolset`, a value from a config file and from a variable, and the refusal of any other value that names the variable
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py` fails on the base
- [ ] 4.2 Add `JobToolset = Literal["base"]` and `DEFAULT_ROADMAP_JOB_TOOLSET` to `src/devops_cli/config/defaults.py`, the `toolset` field to `RoadmapImplementConfig`, a `RoadmapReviewConfig` with the same field, and the `review` member of `RoadmapConfig`. Delete the two new variables in the `config_file` fixture of the test module, and update `tests/roadmap/test_roadmap_limit_classes.py` for the new constant
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_settings.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 5. Document the registry and the three toolsets

Reads: `docs/roadmap/stage.md`, `docs/roadmap/implement.md`, `src/devops_cli/roadmap/tools.py`, `src/devops_cli/config/settings.py`. Changes: `docs/roadmap/tools.md` (new), `docs/roadmap/stage.md`, `docs/roadmap/implement.md`.

- [ ] 5.1 Add `docs/roadmap/tools.md` with the registry table, the three settings, the `base` value of each and the holders, and name the page from the toolset section of `docs/roadmap/stage.md` and from `docs/roadmap/implement.md`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 5.2 Edit `docs/roadmap/tools.md`, `docs/roadmap/stage.md` and `docs/roadmap/implement.md`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 4: Each of the three jobs has a toolset setting with a documented `base` value.
- Group 1: A test fails when a tool is in a role table or a toolset and not in the registry.
- Pending person: The stage tools of #3238 are available through the MCP planning role from the same functions., The role server runs on the Service host, and a stage tool reads the path that the model gives in the job's checkout, so the planning role would read the server's own tree. Serving them needs a server that reads the job's checkout, which this change does not add.
- Group 3: No tool is defined twice.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
