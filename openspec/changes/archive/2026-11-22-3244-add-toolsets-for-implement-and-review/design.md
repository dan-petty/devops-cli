# Design

## Decisions

- **Put the registry in a new module, `src/devops_cli/roadmap/tools.py`.**: Both the roadmap jobs and the MCP server import it, the module imports nothing heavy, and the MCP package stays one consumer instead of the owner.
- **Key the table by tool name, and hold the tables that name the tool in one `holders` set.**: One name is one entry, so `read_file` of the stage planner and `read_file` of the implement step share one purpose and one read-only flag, and no name list is copied into a second place.
- **Hold no function object in an entry.**: The stage tools are bound methods of `src/devops_cli/roadmap/stage/stage_tools.py:class StageTools`, the implement tools are capabilities of the harness `Coder`, and the role tools are generated from CLI commands, so no single callable exists for every name. The table unifies the names, the purposes and the flags, and the tests compare the tables with it.
- **Make the stage toolset and the three role tables read `tool_names`, in place of their own lists.**: This is what makes the registry the one source: a name that leaves the table leaves every host, and a name that joins it joins the hosts that its holders name.
- **Give the implement and review settings the value `base` only.**: `base` is the tools of each job today, as the issue asks. A later value adds tools without a second list, because the names come from the registry holders.
- **Set the review toolset to the tools of the review role table.**: The review job reaches its tools through the review role server, so one set of sixteen names serves both, with the holders `review`.
- **Leave the persona tool maps in `src/devops_cli/ai/tools/registry.py` alone.**: They choose tools for `devops ai` chat personas, and no roadmap job or MCP role reads them, so the issue's three places stay three.
- **Keep the stage toolset values `base` and `extended` unchanged.**: A plan run keeps its behavior, and the change only moves where its names come from. The setting and its default at `src/devops_cli/config/defaults.py:848:DEFAULT_ROADMAP_STAGE_TOOLSET: StageToolset = "extended"` stay.

## Rejected alternatives

- **Make `src/devops_cli/ai/mcp/roles.py` the registry.**: That module holds the role tables, so every roadmap job would import the MCP package for its own tools. The roadmap jobs load no FastMCP, and `src/devops_cli/ai/mcp/remote.py` is the module that builds the server.
- **Copy the tool names into the settings defaults in `src/devops_cli/config/defaults.py`.**: Two lists drift, which is the defect of the issue. `src/devops_cli/config/defaults.py:847:StageToolset = Literal["base", "extended"]` holds the value, and the names live in `src/devops_cli/roadmap/stage/stage_tools.py:344:methods: list[Callable[..., ToolReturn]] = [`, so a copy would be a third list.
- **Serve the stage tools through the MCP planning role.**: `src/devops_cli/ai/mcp/roles.py:8:The tables name only tools that need nothing from the files of the job.` A stage tool reads the path that the model gives, at `src/devops_cli/roadmap/stage/stage_tools.py:def _checkout_path`, and the server has no checkout of the job.
- **Hold the callable function in each registry entry.**: The stage tools are methods of `src/devops_cli/roadmap/stage/stage_tools.py:class StageTools`, and the implement tools are capabilities that `src/devops_cli/roadmap/implement/implement_step.py:def build_agent` gets from the harness `Coder`, so no one callable exists for each name.
- **Check the tables when the MCP server starts, in place of a test.**: A start-time check misses the job toolsets, and it fails after the process starts. `tests/ai/mcp/test_mcp_roles.py:49` already asserts the three role counts offline, so the table check belongs in the same test pass.
