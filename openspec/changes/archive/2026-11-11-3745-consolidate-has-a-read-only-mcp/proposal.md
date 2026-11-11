# Proposal: #3745

## Why

`devops roadmap consolidate` runs by hand only, and an agent has no read-only MCP tool for it. Closes #3745.

The item first asked for a weekly row in the due table of the Service run too. ADR 0021 moves rows out of the Service pod, and the owner rule of 2026-11-11 forbids a loop in a Service pod. The consolidate step of `brain-daily` (#4687, not built yet) will run the judge daily, at most 10 shortlists a run, so the item now holds the MCP tool only.

## What Changes

- A new MCP tool `roadmap_consolidate` mirrors the plan run of `devops roadmap consolidate`. It publishes `repo`, `ref`, `limit` and `dry_run` only. It publishes no `decline` and no `confirm`, so its argv never holds `--decline` or `--confirm`. The command has no `--apply`.
- The tool is read-only (`readOnlyHint: true`). The plan run writes the local plan file under the data directory and nothing on GitHub, as `ai_ingest_library` writes its contract files under the data directory.
- The tool waits at most 900 s, because a run judges up to 10 shortlists at about 60 s each.
- `docs/roadmap/consolidate.md` names the tool. `docs/MCP_TOOLS.md` lists it.
- No due-table row and no Service row.

## Capabilities

- `roadmap-consolidate-plan`: ADDED requirement "An MCP tool mirrors the plan run".

## Impact

- `src/devops_cli/config/constants.py`: one row of `CONST_MCP_EXPOSURE_TABLE`.
- `src/devops_cli/ai/mcp/generator.py`: one entry of `_PATH_PARAM_RESTRICTIONS`.
- The tool listing snapshot, the generated `docs/MCP_TOOLS.md` and the row census of the stage run allow-list (144 to 145 rows). The stage planner may now run the plan path of the command in its sandbox, as it runs the other read-only tools that call a model (`review_branch`, `ai_benchmark`).
- No new dependency.

## Feasibility

- The command exists: `consolidate_cmd` in `src/devops_cli/commands/roadmap.py` has the options `--repo`, `--ref`, `--limit`, `--decline`, `--dry-run` and `--confirm`, and no `--apply`. `--decline` writes only with `--confirm` (`_one_mode`, `consolidate_confirm_needs_decline`).
- The plan path writes `.data/roadmap/consolidate/<date>.json` and its progress file only (`docs/roadmap/consolidate.md`, spec `roadmap-consolidate-plan`).
- The MCP generator already builds a tool from a row of `CONST_MCP_EXPOSURE_TABLE` and narrows its options with `_PATH_PARAM_RESTRICTIONS`. The test `tests/ai/mcp/test_mcp_read_only_write_options.py` finds no write verb in the published options `repo`, `ref`, `limit` and `dry_run`.
- Run time: the plan of 2026-11-10 judged 6 shortlists, and its file times show about 6 minutes from the embeddings to the plan. The default limit is 10 (`DEFAULT_ROADMAP_CONSOLIDATE_JUDGED`).
- The `brain-daily` item #4687 names #3745 as related (read with `devops gh api`).

## Existing Tool Considered

FastMCP (`https://github.com/PrefectHQ/fastmcp`, Apache-2.0, maintained) is the MCP server that the project already uses. It registers the tool and publishes its schema. The project generator adds the argv translation and the option policy. The change adds one exposure row and one restriction entry, with no new code path. Cost: about 150,000 tokens and 1 hour to build; no extra upkeep beyond the existing generator.
