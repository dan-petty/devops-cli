# Proposal

## Why

Three places choose the tools of a model that works on the project: the stage planner, the implement step and the MCP job role servers. Each keeps its own list, so a tool that one place changes stays missing in the others (#3244). The stage toolset names its nine tools and three more in `src/devops_cli/roadmap/stage/stage_tools.py`, the implement step takes six tools from the harness `Coder`, and the role tables name 28, 17 and 16 tools in `src/devops_cli/ai/mcp/roles.py`. No setting names the tools of the implement or review job.

## What Changes

- Add `src/devops_cli/roadmap/tools.py` with the `ToolEntry` record and the `TOOLS` table: one entry for each tool name, with its one-line purpose, its read-only flag and the tables that hold it (the stage toolset, the implement toolset, the planning, implementation and review roles).
- Add `tool_names(holder)` to `src/devops_cli/roadmap/tools.py`, which returns the names of one holder in table order and raises `ValueError` for a holder that the table does not know.
- Add `check_tables(tables)` to `src/devops_cli/roadmap/tools.py`, which returns one problem for each name of a table that the registry lacks, with the table and the name in the text.
- Change `StageTools.tools` in `src/devops_cli/roadmap/stage/stage_tools.py` to wrap the methods that `tool_names` gives for `stage`, and for `extended` also the three of `stage-extended`, in place of the method list at `src/devops_cli/roadmap/stage/stage_tools.py:344:methods: list[Callable[..., ToolReturn]] = [`.
- Change `_JOB_ROLE_TOOLS` in `src/devops_cli/ai/mcp/roles.py` to `{role: frozenset(tool_names(role)) for role in JOB_ROLES}`, in place of the name sets of `src/devops_cli/ai/mcp/roles.py:68:_JOB_ROLE_TOOLS: Final[dict[str, frozenset[str]]] = {`. The `ops` role keeps the whole catalogue, and `tools_for_role` keeps its read-only filter and its refusal of a missing tool.
- Add `JobToolset = Literal["base"]` and `DEFAULT_ROADMAP_JOB_TOOLSET` to `src/devops_cli/config/defaults.py`, next to `src/devops_cli/config/defaults.py:847:StageToolset = Literal["base", "extended"]`.
- Add the `toolset` field to `RoadmapImplementConfig` in `src/devops_cli/config/settings.py`, and a `RoadmapReviewConfig` with the same field, and give `RoadmapConfig` a `review` member at `src/devops_cli/config/settings.py:1232:implement: RoadmapImplementConfig = Field(default_factory=RoadmapImplementConfig)`.
- Add `docs/roadmap/tools.md` with the registry, the three settings and the `base` value of each, and name it from `docs/roadmap/stage.md` and `docs/roadmap/implement.md`.
- The change carries a spec delta in a new capability `roadmap-tool-registry`, because a setting and the tools of a service are behavior that a consumer observes.
- The persona tool maps of `src/devops_cli/ai/tools/registry.py:def get_default_tools` keep their own lists. They choose tools for `devops ai` chat personas, not for a roadmap job, so this change leaves them as they are.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `roadmap-tool-registry`: One table holds the tools of every job and role, The three jobs have a toolset setting, A table name must be a registry entry, One table chooses the tools of each host

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/roadmap/tools.py`, `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/ai/mcp/roles.py`, `src/devops_cli/config/defaults.py`, `src/devops_cli/config/settings.py`
- Documents: `docs/roadmap/tools.md`, `docs/roadmap/stage.md`, `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_tools.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`, `tests/ai/mcp/test_mcp_roles.py`, `tests/roadmap/stage/test_roadmap_stage_settings.py`

## Feasibility

- The probe line for the cited stage module is "The path `stage_tools.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/stage/stage_tools.py`. No commit in the history deleted or renamed it." The file exists: `list_files` of `src/devops_cli/roadmap/stage` showed `stage_tools.py`, and `read_file` showed `class StageTools` with the twelve tool methods.
- The probe line for the first new setting is "The path `roadmap.implement.toolset` is no file of the staging commit. No commit in the history deleted or renamed it." A setting is no file, and the issue asks to create this one, so this is no false premise. The same holds for `roadmap.review.toolset`.
- The stage toolset exists at `src/devops_cli/config/settings.py:class RoadmapStageConfig`, with `toolset: Annotated[StageToolset, Variable()]` and the default `extended` at `src/devops_cli/config/defaults.py:848:DEFAULT_ROADMAP_STAGE_TOOLSET: StageToolset = "extended"`. No `toolset` field exists on `RoadmapImplementConfig`, and `RoadmapConfig` has no `review` member, so the change adds both.
- The premise that the stage planner holds nine tools is out of date: #3238 merged. The archived folder `openspec/changes/archive/2026-11-02-3238-stage-planner-tools/` exists, and `StageTools` holds `references`, `read_issue` and `find_issues`, so `base` names nine tools and `extended` names twelve.
- The implement job holds six tools today, from the pinned harness `Coder` that `src/devops_cli/roadmap/implement/implement_step.py:def build_agent` builds: `read_file`, `write_file`, `edit_file`, `list_files`, `grep` and `shell`. The archived proposal of #2664 records them, and the archived spec of `roadmap-implement-step` asserts them.
- The role tables exist at `src/devops_cli/ai/mcp/roles.py:68:_JOB_ROLE_TOOLS: Final[dict[str, frozenset[str]]] = {`, and `read_file` of `tests/ai/mcp/test_mcp_roles.py` showed the counts 28, 17 and 16 at line 49, which the registry must keep.
- Acceptance criterion 3 cannot be built as written. The role server runs on the Service host, and a stage tool reads the path that the model gives in the job's checkout, at `src/devops_cli/roadmap/stage/stage_tools.py:def _checkout_path`. The module states the rule: `src/devops_cli/ai/mcp/roles.py:8:The tables name only tools that need nothing from the files of the job.` A planning role that served the stage tools would read the server's own tree. This change adds no server with a checkout of the job, and the plan compensates for nothing.
- This reply corrects the faults of the previous one: it gives the spec delta, real texts in place of the placeholders, a quote of the probe lines, the four acceptance criteria, and the three overlaps as dependencies.
- Precondition of `load_settings`: a checkout of the repository, because it reads the project configuration layers and the defaults.
- Precondition of `StageTools.tools`: no checkout, no client and no network, because it wraps the bound methods of an instance that a test builds on a temporary directory.
- Precondition of `tool_names` and `check_tables`: no checkout, no client and no network, because they read the module table and take their arguments.
- Precondition of `tools_for_role` and `named_job_tools`: no client and no network, because the caller passes the tool list and the functions read the registry.
- Precondition of `mcp._list_tools` and `build_role_server`: no client and no network, because FastMCP builds the catalogue and the role server in the test process.
- First check against the real system: `uv run devops ci test tests/roadmap/test_roadmap_tools.py`.
- First check against the real system: `uv run devops ci test tests/ai/mcp/test_mcp_roles.py`.
- First check against the real system: `uv run devops openspec check`.
- First check against the real system: `uv run devops ci docs`.

## Existing Tool Considered

pydantic-ai and FastMCP both wrap a plain Python function as a tool, and the project already uses them, but neither gives a shared tool registry, a toolset setting for a job or a cross-check test. The change builds one table, two functions and two settings: about 20k tokens to build, about 3k tokens each month to keep and fix, and about 6 hours of elapsed time. It deletes the two name lists in `src/devops_cli/roadmap/stage/stage_tools.py` and `src/devops_cli/ai/mcp/roles.py`.

## Dependencies

- #3943 changes `src/devops_cli/config/defaults.py`, which this change also edits. The crawl settings of that pull request and the `JobToolset` line sit in different parts of the file, and this change adds no crawl setting.
- #3945 changes `src/devops_cli/ai/mcp/server.py`. This change leaves that file unchanged: it reads the role tables of `src/devops_cli/ai/mcp/roles.py`, so the two pull requests share no line.
- #3948 changes `src/devops_cli/config/defaults.py`, which this change also edits. The web-search defaults and the toolset type are different lines, and this change adds no search provider.
