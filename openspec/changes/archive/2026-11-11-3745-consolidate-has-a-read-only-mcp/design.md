# Design

## Decisions

- **Options from the generator.** The tool comes from one row of `CONST_MCP_EXPOSURE_TABLE`. A `_PATH_PARAM_RESTRICTIONS` entry permits `repo`, `ref`, `limit` and `dry_run`. The generator binds only the published options, so a caller cannot put `--decline` or `--confirm` in the argv.
- **Read-only flag.** The plan run writes a local file under the configured data directory and makes no GitHub change. The exposure table marks such a tool read-only, as it marks `ai_ingest_library`. The decline path writes to GitHub, so the tool does not publish it.
- **Timeout 900 s.** A run judges at most `--limit` shortlists (default 10), two model calls each. The plan of 2026-11-10 judged 6 in about 6 minutes, so 10 need about 10 minutes. A run that stops at the timeout keeps each judgement in `<date>.progress.json`, and the next run does not judge them again. A caller that wants a short run passes `limit`.
- **No Service row.** The consolidate step of `brain-daily` (#4687) will run the judge daily. A weekly due-table row would be a loop in the Service pod, which ADR 0021 and the owner rule of 2026-11-11 forbid.

## Rejected alternatives

- **Publish `decline` without `confirm`.** The decline preview writes nothing, but the item asks for an argv with no decline, and the preview has no use for an agent that cannot confirm.
- **Timeout 300 s, as `roadmap_refine`.** A default run of 10 shortlists takes about 10 minutes, so the tool would stop most default runs before the plan file exists.
- **A hand-written tool function.** The generator already builds the schema and the argv from the Click command, so a custom function adds code and a second path.
