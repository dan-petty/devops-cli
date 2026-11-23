# Roadmap Tools and Toolsets

The project keeps one tool registry in `src/devops_cli/roadmap/tools.py` (#3244).
The table `TOOLS` names each tool once.
Each entry holds a name, a one-line purpose, a read-only flag, and the holders that name it.

## The Settings

Three roadmap jobs configure their tools with a toolset setting.

| Setting | Variable | Default | Allowed Values |
| --- | --- | --- | --- |
| `roadmap.stage.toolset` | `DEVOPS_CLI_ROADMAP_STAGE_TOOLSET` | `extended` | `base`, `extended`, `research` |
| `roadmap.implement.toolset` | `DEVOPS_CLI_ROADMAP_IMPLEMENT_TOOLSET` | `base` | `base` |
| `roadmap.review.toolset` | `DEVOPS_CLI_ROADMAP_REVIEW_TOOLSET` | `base` | `base` |

Each setting controls which tools the agent receives for that job.
The `base` value contains the baseline tools of the job.

## The Holders

A holder is one tool list of a host:

- `stage`: the nine read-only tools that inspect the staged commit.
- `stage-extended`: the stage base tools plus GitHub issue reads and references.
- `stage-research`: the extended tools plus web search.
- `implement`: the eight tools of the implementation step.
- `planning`: the MCP tools of the planning role.
- `implementation`: the MCP tools of the implementation role.
- `review`: the MCP tools of the review role.

A test verifies that each holder and role table names only tools from the registry.
