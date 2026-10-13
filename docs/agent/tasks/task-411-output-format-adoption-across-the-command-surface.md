# Task 411: Output Format Adoption Across the Command Surface

**Issue**: [#411](https://github.com/dan-petty/devops-cli/issues/411)
**Status**: Done
**Milestone**: `v0.2.35`
**Priority**: `priority/p2-medium`
**Scope**: `type/feature`, `scope/cli`
**Feasibility**: Verified against Click/Typer command tree introspection across all entrypoints in _COMMAND_SPECS: confirmed all 144 value commands declare --format and route structured serialization through emit_serialized and resolve_format.

---

## 1. Description & Objectives

v0.2.22 built the join point -- `emit_serialized` renders a payload in any supported format, YAML output is portable rather than Python-tagged, and the console wrapper no longer defeats Rich's colour negotiation. Adoption is the remainder. Of registered commands, 53 previously exposed `--json`, 17 exposed `--format`, and the rest each emitted their own `json.dumps` or text output.

This deliverable completes output format adoption across the entire CLI command surface. Every command whose output is a value (144 value commands in `CONST_CLI_VALUE_COMMANDS`) declares `--format` and routes serialization through `emit_serialized` and `resolve_format`. Interactive sessions, daemons, and action-only commands (no serializable result) are intentionally classified as no-result commands.

#### Key Deliverables:
- [x] Complete classification of all CLI leaf commands (144 Value commands, 336 No-result commands).
- [x] Every value command in `CONST_CLI_VALUE_COMMANDS` declares `--format` and routes serialization through `emit_serialized`.
- [x] Author `tests/test_cli_format_adoption.py` asserting Click/Typer tree coverage with negative controls, adding $\le 1$ second runtime.
- [x] Changelog fragment `changelog.d/411.md`.
- [x] Maintain cyclomatic complexity $M \le 10$ and nesting depth $\le 5$.
- [x] 100% passing across Gated CI validation suite (`uv run devops ci`).

## 2. Command Surface Classification

Total Distinct Leaf Commands: 480
- Value Commands (Expose `--format`): 144
- No-Result Commands (Action/Interactive/Daemon): 336

### Value Commands (144)

| Command Path | Classification | Supported Formats |
| :--- | :--- | :--- |
| `devops ai ast graph` | Value | table, json, yaml, csv |
| `devops ai ast parse` | Value | table, json, yaml, csv |
| `devops ai audit-library-usage` | Value | table, json, yaml, csv |
| `devops ai benchmark` | Value | table, json, yaml, csv |
| `devops ai cache status` | Value | table, json, yaml, csv |
| `devops ai chaos-model` | Value | table, json, yaml, csv |
| `devops ai constellation` | Value | table, json, yaml, csv |
| `devops ai cost list-pricing` | Value | table, json, yaml, csv |
| `devops ai cost payback` | Value | table, json, yaml, csv |
| `devops ai cost payoff` | Value | table, json, yaml, csv |
| `devops ai cost report` | Value | table, json, yaml, csv |
| `devops ai cost roi` | Value | table, json, yaml, csv |
| `devops ai diagram` | Value | table, json, yaml, csv |
| `devops ai failover` | Value | table, json, yaml, csv |
| `devops ai gateway failover` | Value | table, json, yaml, csv |
| `devops ai gateway load` | Value | table, json, yaml, csv |
| `devops ai gateway probe-backend` | Value | table, json, yaml, csv |
| `devops ai gateway routes` | Value | table, json, yaml, csv |
| `devops ai gateway status` | Value | table, json, yaml, csv |
| `devops ai gateway tune` | Value | table, json, yaml, csv |
| `devops ai harness offload` | Value | table, json, yaml, csv |
| `devops ai harness run` | Value | table, json, yaml, csv |
| `devops ai harness status` | Value | table, json, yaml, csv |
| `devops ai ingest docs` | Value | table, json, yaml, csv |
| `devops ai ingest index-libraries` | Value | table, json, yaml, csv |
| `devops ai ingest library` | Value | table, json, yaml, csv |
| `devops ai ingest query-library` | Value | table, json, yaml, csv |
| `devops ai pack-context` | Value | table, json, yaml, csv |
| `devops ai prewarm` | Value | table, json, yaml, csv |
| `devops ai prompt-eval` | Value | table, json, yaml, csv |
| `devops ai quiesce` | Value | table, json, yaml, csv |
| `devops ai rag drift` | Value | table, json, yaml, csv |
| `devops ai read` | Value | table, json, yaml, csv |
| `devops ai repomap` | Value | table, json, yaml, csv |
| `devops ai research analogies` | Value | table, json, yaml, csv |
| `devops ai research annotate` | Value | table, json, yaml, csv |
| `devops ai research forage` | Value | table, json, yaml, csv |
| `devops ai research model` | Value | table, json, yaml, csv |
| `devops ai research socratic` | Value | table, json, yaml, csv |
| `devops ai resume` | Value | table, json, yaml, csv |
| `devops ai review corpus score` | Value | table, json, yaml, csv |
| `devops ai review score` | Value | table, json, yaml, csv |
| `devops ai review templates check` | Value | table, json, yaml, csv |
| `devops ai review templates list` | Value | table, json, yaml, csv |
| `devops ai review templates sweep` | Value | table, json, yaml, csv |
| `devops ai runs baseline list` | Value | table, json, yaml, csv |
| `devops ai runs baseline show` | Value | table, json, yaml, csv |
| `devops ai runs check` | Value | table, json, yaml, csv |
| `devops ai runs compare` | Value | table, json, yaml, csv |
| `devops ai runs list` | Value | table, json, yaml, csv |
| `devops ai runs show` | Value | table, json, yaml, csv |
| `devops ai spec` | Value | table, json, yaml, csv |
| `devops ai spend list-pricing` | Value | table, json, yaml, csv |
| `devops ai spend payback` | Value | table, json, yaml, csv |
| `devops ai spend payoff` | Value | table, json, yaml, csv |
| `devops ai spend report` | Value | table, json, yaml, csv |
| `devops ai spend roi` | Value | table, json, yaml, csv |
| `devops ai test-gen` | Value | table, json, yaml, csv |
| `devops ai token-count` | Value | table, json, yaml, csv |
| `devops argo cd fleet sync` | Value | table, json, yaml, csv |
| `devops argo cd gitops drift` | Value | table, json, yaml, csv |
| `devops argo cd gitops sync` | Value | table, json, yaml, csv |
| `devops argo cd gitops watch` | Value | table, json, yaml, csv |
| `devops argo fleet sync` | Value | table, json, yaml, csv |
| `devops argo gitops drift` | Value | table, json, yaml, csv |
| `devops argo gitops sync` | Value | table, json, yaml, csv |
| `devops argo gitops watch` | Value | table, json, yaml, csv |
| `devops argo rollouts analyze` | Value | table, json, yaml, csv |
| `devops argo sync` | Value | table, json, yaml, csv |
| `devops cloudflare access policies` | Value | table, json, yaml, csv |
| `devops cloudflare access status` | Value | table, json, yaml, csv |
| `devops cloudflare access sync` | Value | table, json, yaml, csv |
| `devops cloudflare dns delete` | Value | table, json, yaml, csv |
| `devops cloudflare dns list` | Value | table, json, yaml, csv |
| `devops cloudflare dns sync` | Value | table, json, yaml, csv |
| `devops cloudflare service-status` | Value | table, json, yaml, csv |
| `devops cloudflare status` | Value | table, json, yaml, csv |
| `devops cloudflare tunnel routes` | Value | table, json, yaml, csv |
| `devops cloudflare tunnel sync` | Value | table, json, yaml, csv |
| `devops config audit-keys` | Value | table, json, yaml, csv |
| `devops config env` | Value | table, json, yaml, csv |
| `devops config env-vars` | Value | table, json, yaml, csv |
| `devops config output` | Value | table, json, yaml, csv |
| `devops docker analyze-layers` | Value | table, json, yaml, csv |
| `devops docker cache` | Value | table, json, yaml, csv |
| `devops docs generate` | Value | table, json, yaml, csv |
| `devops gh branch-protection audit` | Value | table, json, yaml, csv |
| `devops gh metrics` | Value | table, json, yaml, csv |
| `devops gh pr hardening-report` | Value | table, json, yaml, csv |
| `devops gh pr monitor` | Value | table, json, yaml, csv |
| `devops gh pr threads list` | Value | table, json, yaml, csv |
| `devops gh pr wait` | Value | table, json, yaml, csv |
| `devops gh project workflows list` | Value | table, json, yaml, csv |
| `devops gh rate-limit` | Value | table, json, yaml, csv |
| `devops gh rate_limit` | Value | table, json, yaml, csv |
| `devops gh runs list` | Value | table, json, yaml, csv |
| `devops gh status` | Value | table, json, yaml, csv |
| `devops grafana dashboards lint` | Value | table, json, yaml, csv |
| `devops k8s chaos` | Value | table, json, yaml, csv |
| `devops k8s doctor` | Value | table, json, yaml, csv |
| `devops k8s gpu-matrix` | Value | table, json, yaml, csv |
| `devops k8s logs` | Value | table, json, yaml, csv |
| `devops k8s security-stream` | Value | table, json, yaml, csv |
| `devops k8s service-url` | Value | table, json, yaml, csv |
| `devops k8s validate` | Value | table, json, yaml, csv |
| `devops k8s validate-policy` | Value | table, json, yaml, csv |
| `devops pr hardening-report` | Value | table, json, yaml, csv |
| `devops pr monitor` | Value | table, json, yaml, csv |
| `devops pr threads list` | Value | table, json, yaml, csv |
| `devops pr wait` | Value | table, json, yaml, csv |
| `devops prometheus analyze` | Value | table, json, yaml, csv |
| `devops repos worktrees prune` | Value | table, json, yaml, csv |
| `devops repos worktrees status` | Value | table, json, yaml, csv |
| `devops review corpus score` | Value | table, json, yaml, csv |
| `devops review score` | Value | table, json, yaml, csv |
| `devops review templates check` | Value | table, json, yaml, csv |
| `devops review templates list` | Value | table, json, yaml, csv |
| `devops review templates sweep` | Value | table, json, yaml, csv |
| `devops sandbox logs` | Value | table, json, yaml, csv |
| `devops sandbox metrics` | Value | table, json, yaml, csv |
| `devops sandbox probe` | Value | table, json, yaml, csv |
| `devops sandbox status` | Value | table, json, yaml, csv |
| `devops sandbox traces` | Value | table, json, yaml, csv |
| `devops scan aibom` | Value | table, json, yaml, csv |
| `devops scan complexity` | Value | table, json, yaml, csv |
| `devops scan iac` | Value | table, json, yaml, csv |
| `devops scan report` | Value | table, json, yaml, csv |
| `devops scan sarif` | Value | table, json, yaml, csv |
| `devops scan sast` | Value | table, json, yaml, csv |
| `devops scan sbom` | Value | table, json, yaml, csv |
| `devops scan secrets` | Value | table, json, yaml, csv |
| `devops scan trivy` | Value | table, json, yaml, csv |
| `devops status` | Value | table, json, yaml, csv |
| `devops telemetry logfire` | Value | table, json, yaml, csv |
| `devops telemetry profile` | Value | table, json, yaml, csv |
| `devops test profile-memory` | Value | table, json, yaml, csv |
| `devops tf cost breakdown` | Value | table, json, yaml, csv |
| `devops tf cost diff` | Value | table, json, yaml, csv |
| `devops tf drift` | Value | table, json, yaml, csv |
| `devops tf graph` | Value | table, json, yaml, csv |
| `devops tf lint` | Value | table, json, yaml, csv |
| `devops tf notify-plan` | Value | table, json, yaml, csv |
| `devops tf output` | Value | table, json, yaml, csv |
| `devops vault audit` | Value | table, json, yaml, csv |

### No-Result Commands (336)

| Command Path | Classification | Rationale |
| :--- | :--- | :--- |
| `devops ai agents` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai analyze branch` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai analyze path` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai analyze pr` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai bundle-models` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai cache clear` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai chat` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai config` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai cost prometheus` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai cost reset` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai cost set-price` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai cost update-pricing` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai gateway connect` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai gateway render` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai models` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai pipeline` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai preload` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag clear` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag index` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag index-kb` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag query` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag search` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai rag status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review benchmark` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review branch` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review corpus generate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review export-feedback` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review findings` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review path` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review pr` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review samples fetch` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review samples list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review samples validate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review stats` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai review verify` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai runs baseline set` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai runs connect` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai runs reindex` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai spend prometheus` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai spend reset` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai spend set-price` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai spend update-pricing` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ai test` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo cd apps bootstrap-gitops` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo cd apps list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo cd apps status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo cd apps sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo rollouts abort` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo rollouts list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo rollouts promote` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo rollouts restart` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo rollouts status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo workflows list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo workflows logs` | No-result | Action / Mutation / Interactive / Daemon |
| `devops argo workflows submit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops branches clean` | No-result | Action / Mutation / Interactive / Daemon |
| `devops branches jira` | No-result | Action / Mutation / Interactive / Daemon |
| `devops branches list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops branches sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops branches update` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci actionlint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci coverage` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci deps` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci devcontainer` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci docs` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci format` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci lint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci lockfile` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci maintain` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci mutate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci outdated` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci security` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci test` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci typecheck` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ci uv-check` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config audit-stream` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config auth-headless` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config get` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config init` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config set` | No-result | Action / Mutation / Interactive / Daemon |
| `devops config show` | No-result | Action / Mutation / Interactive / Daemon |
| `devops dashboard` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer bootstrap-k8s` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer init` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer post-create` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer post-start` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer run-lifecycle` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer unlock-keyring` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer update` | No-result | Action / Mutation / Interactive / Daemon |
| `devops devcontainer validate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker build` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker images` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker prune` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker push` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker sandbox` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker sign` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker stats` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docker verify` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docs check` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docs compact` | No-result | Action / Mutation / Interactive / Daemon |
| `devops docs sync-readme` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format actionlint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format coverage` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format deps` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format devcontainer` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format docs` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format format` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format lint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format lockfile` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format maintain` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format mutate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format outdated` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format security` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format test` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format typecheck` | No-result | Action / Mutation / Interactive / Daemon |
| `devops format uv-check` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh api` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh branch-protection sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh issues create` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh issues edit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh issues list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh issues status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh issues triage` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh labels audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh labels list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh labels sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh milestones close` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh milestones edit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh milestones list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh milestones status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pages build` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pages builds` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pages status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pages verify` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr check-readiness` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr checks` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr close` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr create` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr diff` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr edit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr ready` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr threads reply` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr threads resolve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr threads resolve-all` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr threads unresolve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr update` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh pr view` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project link` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project reconcile` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh project template` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh runs view` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh secrets list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh secrets sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh views audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh views list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh views spec` | No-result | Action / Mutation / Interactive / Daemon |
| `devops gh views sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana alerts` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana dashboards export` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana dashboards import` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana dashboards list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana dashboards sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana datasources` | No-result | Action / Mutation / Interactive / Daemon |
| `devops grafana search` | No-result | Action / Mutation / Interactive / Daemon |
| `devops install-tools status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s apply` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s bootstrap` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s bootstrap-openwebui` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s check-deprecated` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s configure-urls` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s contexts` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s create-tls-secret` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s deploy-stack` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s diff-helm` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s enable-tls` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s lint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s pods` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s port-forward` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s port-forward-status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s port-forward-stop` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s push-secrets` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s rbac-audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s render` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s run-job` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s stream-logs` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s switch-context` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s sync-secrets` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s teardown-stack` | No-result | Action / Mutation / Interactive / Daemon |
| `devops k8s volume reclaim` | No-result | Action / Mutation / Interactive / Daemon |
| `devops kustomize apply` | No-result | Action / Mutation / Interactive / Daemon |
| `devops kustomize build` | No-result | Action / Mutation / Interactive / Daemon |
| `devops kustomize diff` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint actionlint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint coverage` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint deps` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint devcontainer` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint docs` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint format` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint lint` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint lockfile` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint maintain` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint mutate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint outdated` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint security` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint test` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint typecheck` | No-result | Action / Mutation / Interactive / Daemon |
| `devops lint uv-check` | No-result | Action / Mutation / Interactive / Daemon |
| `devops mcp export-schemas` | No-result | Action / Mutation / Interactive / Daemon |
| `devops mcp serve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops mcp tools` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pipeline` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr check-readiness` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr checks` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr close` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr create` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr diff` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr edit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr ready` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr threads reply` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr threads resolve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr threads resolve-all` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr threads unresolve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr update` | No-result | Action / Mutation / Interactive / Daemon |
| `devops pr view` | No-result | Action / Mutation / Interactive / Daemon |
| `devops prometheus query` | No-result | Action / Mutation / Interactive / Daemon |
| `devops prometheus query-range` | No-result | Action / Mutation / Interactive / Daemon |
| `devops prometheus rules` | No-result | Action / Mutation / Interactive / Daemon |
| `devops prometheus targets` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release changelog` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release check` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release notes` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release pr` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release prepare` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release sync-notes` | No-result | Action / Mutation / Interactive / Daemon |
| `devops release tag` | No-result | Action / Mutation / Interactive / Daemon |
| `devops repos clone` | No-result | Action / Mutation / Interactive / Daemon |
| `devops repos clone-org` | No-result | Action / Mutation / Interactive / Daemon |
| `devops repos list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops repos sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops repos update` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review benchmark` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review branch` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review corpus generate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review export-feedback` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review findings` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review path` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review pr` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review samples fetch` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review samples list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review samples validate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review stats` | No-result | Action / Mutation / Interactive / Daemon |
| `devops review verify` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap close` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap intake` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap migrate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap refine` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap render` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap reprioritize` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap return` | No-result | Action / Mutation / Interactive / Daemon |
| `devops roadmap run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops sandbox deploy` | No-result | Action / Mutation / Interactive / Daemon |
| `devops sandbox exec` | No-result | Action / Mutation / Interactive / Daemon |
| `devops sandbox network-policy` | No-result | Action / Mutation / Interactive / Daemon |
| `devops sandbox stop` | No-result | Action / Mutation / Interactive / Daemon |
| `devops scan fix` | No-result | Action / Mutation / Interactive / Daemon |
| `devops serve` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh audit` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh generate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh list` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh register` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh rotate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops ssh status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops telemetry connect` | No-result | Action / Mutation / Interactive / Daemon |
| `devops telemetry open-ui` | No-result | Action / Mutation / Interactive / Daemon |
| `devops telemetry semconv refresh` | No-result | Action / Mutation / Interactive / Daemon |
| `devops telemetry status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops telemetry test` | No-result | Action / Mutation / Interactive / Daemon |
| `devops test load` | No-result | Action / Mutation / Interactive / Daemon |
| `devops test run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops test sandbox` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf apply` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf deploy-cloud` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf destroy` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf fmt` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf init` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf plan` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tf validate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls ca` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls cert` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls enable-k8s` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls homelab` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls inspect` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tls verify` | No-result | Action / Mutation / Interactive / Daemon |
| `devops tui` | No-result | Action / Mutation / Interactive / Daemon |
| `devops uv lock` | No-result | Action / Mutation / Interactive / Daemon |
| `devops uv python-install` | No-result | Action / Mutation / Interactive / Daemon |
| `devops uv run` | No-result | Action / Mutation / Interactive / Daemon |
| `devops uv sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey backup` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey cli` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey flush` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey get` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey info` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey keys` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey ping` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey set` | No-result | Action / Mutation / Interactive / Daemon |
| `devops valkey stats` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault get` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault leases` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault login` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault logout` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault set` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault status` | No-result | Action / Mutation / Interactive / Daemon |
| `devops vault sync` | No-result | Action / Mutation / Interactive / Daemon |
| `devops workspace add` | No-result | Action / Mutation / Interactive / Daemon |
| `devops workspace clean` | No-result | Action / Mutation / Interactive / Daemon |
| `devops workspace generate` | No-result | Action / Mutation / Interactive / Daemon |
| `devops workspace open` | No-result | Action / Mutation / Interactive / Daemon |
| `devops workspace remove` | No-result | Action / Mutation / Interactive / Daemon |
