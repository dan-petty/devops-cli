# Proposal: #4751

## Why

The owner decided ways of working from 2026-10-04 to 2026-11-11 that the standards do not state, or state in an older form: rebase before each push, no catch-up updates, no stacked pull requests, a closing keyword only for the delivered issue, nested time limits, Service work as Jobs and Workflows, open tools through standard interfaces, permissive dependencies, and others. Merged pull requests also made some facts in the documents wrong: the release merge is scheduled, the coverage floor is 85 %, Ruff caps nesting at 4 blocks, and 22 test paths moved. Agents read these documents first, so they follow old rules. Closes #4751.

## What Changes

- Each decided rule that people and agents can follow now goes into the document that owns its topic (AGENTS.md, Where to look). A copy in another document becomes a link.
- `AGENTS.md`: rule 1 (rebase before each push), rule 6 (no Copilot review request), rule 9 (prompts), and a shorter release paragraph. It stays under its cap of 6,500 characters.
- `CONTRIBUTING.md`: open tools and dependencies, decide and report, artifacts and charts, the plugin settings of Claude Code, the fetch-page command, and the closing keyword rule.
- `ARCHITECTURE.md`: nested time limits, the dry-run class, and a new subsection on Service work and shared state.
- `docs/SDLC.md`: the push rules of Phase 6, where a check runs, the Service image tests, the red release pull request, and filing rules.
- `docs/ROUTINE_TASKS.md`: Cadence B and Cadence C link to `docs/SDLC.md` and `RELEASE_CYCLE.md` and do not copy them; no step reads the project board.
- `SECURITY.md`, `k8s/README.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/TESTING.md`, `CONTEXT.md`, `docs/DASHBOARD_TABS_AUDIT.md` and the feature request template: the stale facts above, the MCP server, rag-ingest, `bootstrap-mattermost` and the Sonnet hold.
- The change alters no behavior that a consumer observes, so it has no spec delta.
- The change fits one pull request.

## Capabilities

None. The change edits documents, one issue template and one test that pins document text.

## Impact

- 11 documents and one issue template. No code, setting or dependency changes.
- `tests/invariants/test_roadmap_stage_measure_doc.py` pins the baseline commands of `docs/ROADMAP_WORKFLOW.md`. They now name `<baseline-model>` and not `claude-sonnet-5-5`, which the owner holds, so the test changes with them.
- Text about a feature that is not built yet stays out. It goes into the pull request of that feature.
- No threshold changes. The 1-minute tolerance over the 5-minute check limit is not written, because only the owner can loosen a threshold.
- No release file, ADR or generated document gets a hand edit.

## Feasibility

Each changed fact was checked against `origin/main` at 05e09dcc:

- `pyproject.toml` has `fail_under = 85` and `max-nested-blocks = 4`.
- Each new test path exists, and each old path does not.
- `.claude/settings.json` turns off `cloudflare`, `mcp-server-dev` and `playwright`.
- `devops ai fetch-page --help` and `devops k8s bootstrap-mattermost --help` show the options that the text names.
- `.github/workflows/ci.yml` has six `service-image-test` shards that run on a pull request and a manual run.
- `k8s/argo-workflows/values.yaml` sets `singleNamespace: true`, and `k8s/devops/cronworkflow-rag-ingest.yaml` is in namespace `devops`.
- ADR 0021 records the go of ADR 0008 with a warm p95 of 11 s.
- The GitHub API shows #2913, #2919 and #3028 closed as completed, and #2867 and #2968 open.

## Existing Tool Considered

No tool is needed: this is a change to Markdown documents. markdownlint, `devops ci docs` and the invariant tests of the documents check it. The change deletes no code.
