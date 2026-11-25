### Problem or Motivation

The project standards do not state some ways of working that the owner decided from 2026-10-04 to 2026-11-11. Some documents also state facts that merged pull requests made wrong. Agents and people read the standards first, so they follow old rules or miss decided ones.

Decided ways of working that no document states, or that a document states in a different form:

- Rebase onto `origin/main` right before each push, not only the first push. Do not update an open pull request only to catch up with `main` (owner, 2026-10-25 and 2026-11-11).
- Watch each open pull request until the merge, and fix a failed check or a conflict at once. Agents never request or wait for a Copilot review (owner, 2026-10-23 and 2026-10-24).
- Use a closing keyword only before the issue that the pull request delivers (owner, 2026-10-27; #2339 closed #2336 too early).
- No stacked pull requests; push only when the implementation, the review fixes and the OpenSpec archive are complete; branch push policy (owner, 2026-10-23, 2026-10-28, 2026-11-05).
- A red required check on the release pull request is a defect of `main`. GitHub gives no merge queue to a personal repository and ignores merge drivers (owner, 2026-10-24 and 2026-11-11).
- Nested time limits: each inner limit is shorter than the limit around it (owner, 2026-11-11; #4678 is one known break).
- Service work runs as Jobs or Argo Workflows; GitHub holds the truth and Valkey is a cache; shared capabilities fall back to a local tier; one `RepoRef` names each repository resource (owner, 2026-11-11; ADR 0021 in #4609, ADR 0022 in #4612).
- Connect open tools through standard interfaces; use reputable, maintained, permissive dependencies; prefer Podman, OpenTofu and Valkey (owner, 2026-11-11).
- Decide an open design question with the best-practice answer and report it (owner, 2026-10-22).
- Rules for project artifacts and charts: contrast, color-blind palette, both themes, chart form (owner, 2026-11-11).
- A check that does not apply does not run; every CI job runs in the devcontainer and on a stock runner (owner, 2026-10-20 and 2026-10-24).
- Search before you file, fold a finding into a matching item, start a blocker at once, close a replaced item as not planned (owner, 2026-10-23 to 2026-11-10).
- A tracker has no milestone. Status lives in labels, and no step reads the project board (owner, 2026-10-22 and 2026-10-28).
- A dry run sends no external request (owner, 2026-10-04).
- Project text can go to a hosted provider, but no secret or personal data. The owner holds Sonnet trials (owner, 2026-11-10 and 2026-11-11).
- A new cluster secret is a generated row of the secret table. Live objects that git does not hold are drift (owner, 2026-10-23 and 2026-11-11).
- A Service pull request waits for an independent review with evidence (owner, 2026-11-01).
- ASD-STE100 also covers prompts (owner, 2026-10-22).

Merged functionality that the documents do not state, or state wrong:

- The plugin settings of `.claude/settings.json` (#4468).
- `devops ai fetch-page` and the web search providers (#3900, #3943, #3948, #3980, #3982).
- The dry-run class and its ratchet (#2941, #2954, #2963, #2969, #3129, #3135, #3512).
- The role-scoped MCP server in the cluster (#3233, #4182, #4191).
- The Service image test jobs (#4425).
- The rag-ingest WorkflowTemplate and CronWorkflow (#4180), and the go of ADR 0008 that ADR 0021 records (#4609).
- `devops k8s bootstrap-mattermost` (#2948, #2955).
- The removed k8s and logs dashboard tabs (#3984, #4263).
- The scheduled merge of the release pull request (`release-merge.yml`). Several documents still say that a person merges it.
- The coverage floor is 85 % in `pyproject.toml`, and Ruff caps nesting at 4 blocks. Some documents say 90 % and 5.
- 22 test paths in the documents point to files that moved to the mirror tree.
- Trace propagation and metrics export text that does not match the code.
- Closed rows (#2908, #2913, #2919, #3028) in the Planned changes table of `docs/ROADMAP_WORKFLOW.md`.

### Proposed Solution & Architectural Design

One documents pull request puts each rule in its owning document (AGENTS.md, Where to look) and removes the copies. It changes `AGENTS.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `SECURITY.md`, `CONTEXT.md`, `k8s/README.md`, `docs/SDLC.md`, `docs/ROUTINE_TASKS.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/TESTING.md` and `docs/DASHBOARD_TABS_AUDIT.md`.

- `AGENTS.md` stays under its cap of 6,500 characters.
- No threshold changes. No release file, ADR or generated document gets a hand edit.
- Text about a feature that is not built yet stays with the pull request of that feature.

Acceptance:

- The tests that read these documents pass: `tests/invariants/test_agents_md.py` and the other document tests.
- `uv run devops ci docs` and the pre-commit document checks pass.

### Target Subsystem

SDLC, Git & PR Governance

### Existing Tool Considered

No tool is needed. This is a documents change in Markdown, and the existing checks (markdownlint, `devops ci docs`, the document invariant tests) verify it.


<!-- devops-roadmap-record {"Effort": "High", "Owner": "Agent", "Priority": "P2-Medium", "Status": "In Review", "Value": "High"} -->
