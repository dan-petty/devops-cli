# Task: Group Analysis Is Profiled as Its Own Stage, and analysis.json Counts Dispatched, Replayed and Failed Jobs Apart (#482)

**Issue**: [#482](https://github.com/dan-petty/devops-cli/issues/482)
**Scope**: scope/review, scope/ai
**Feasibility**: Confirmed in `src/devops_cli/ai/review/pipeline.py`, `src/devops_cli/ai/review/profile.py`, and `src/devops_cli/review/analysis.py`. Group analysis ran during report generation, but lacked a dedicated stage context. Nested stages did not subtract inner time from the enclosing stage. Model calls were stored as a single count rather than tracking dispatched, replayed, and failed jobs separately.

## Description

- [x] Run group analysis inside `review_stage("group_analysis")` in `ReviewPipelineOrchestrator._run_group_analysis_stage`.
- [x] Update `review_stage` to subtract inner stage elapsed wall time from the enclosing outer stage, and clamp stage wall seconds to non-negative values in `ReviewProfiler.build()`.
- [x] Credit model calls and replays to `group_analysis` stage in `profile.json`, with none to `report` or `unstaged`, subtracting inner wall time from `report`.
- [x] Update terminal profile line to show replayed count next to calls when replayed calls exist (`({s.llm_calls} calls, {s.cached_calls} replayed)`), and list stages that only replayed (`if s.wall_seconds >= 1 or s.llm_calls or s.cached_calls`).
- [x] Replace `model_calls` in `AnalysisReport` with `dispatched`, `replayed`, and `failed`, removing `model_calls` with no backward compatibility aliases.
- [x] Update `render_model_analysis_markdown` to print `- **Jobs**: {report.dispatched} dispatched, {report.replayed} replayed, {report.failed} failed (groups: {len(report.groups)})`.
- [x] Ensure `LLMClient` with `cache_enabled=False` isolates the cache instance so requests do not hit or write cache entries.
- [x] Add offline deterministic unit tests: two-run cache replay test, failure count separation test, nested profile subtraction test, and terminal summary formatting test.
- Pending a person: Run `devops review` twice on a target with findings and group analysis enabled; verify the second run shows `replayed` matching the group count and zero dispatched model calls in `analysis.json`.
