# Proposal: #5293

## Why

The homelab environment moves to a private repository (tracker #5120, phase 2, plan step 3). `k8s/README.md` is an environment document, but three of its sections tell how the product works: "devops-cli in the cluster", "Image Pins" and "Service Image Updates". The alert rules, the manifests, the source, the tests, the specs and the documents of devops-cli point to these sections. When a later step deletes the environment files from devops-cli, these pointers break. Closes #5293.

## What Changes

- Add `docs/CLUSTER.md`, "devops-cli in the cluster". It holds the text of the three sections with no change, one heading level higher: the roadmap Service (with Runner Jobs, Webhook route, Mattermost slash command, Alerts, Go-live check and Stop switch), Crawl4AI, SearXNG, MCP server, Image Pins and Service Image Updates. A short lead names what the document holds and links `k8s/README.md` for the cluster set-up. Its links to the environment sections (Cluster Secrets, Receiver, LLM Gateway, Pausing an Application) go to `k8s/README.md`.
- Remove these sections from `k8s/README.md`. The subsection "Agent sessions" stays in `k8s/README.md` as its own section, because it tells about `k8s/agents/`, an environment directory. The references of `k8s/README.md` to the moved sections link `docs/CLUSTER.md`, and the row `all` of the stacks table links it.
- Re-point each live reference to the moved sections: 21 alert descriptions in `k8s/monitoring/prometheus-values.yaml` and their 43 expected descriptions in `tests/fixtures/prometheus_rules/`, the comments of 6 manifests under `k8s/devops/`, `.github/renovate.json`, `AGENTS.md`, `CONTEXT.md`, `CONTRIBUTING.md`, `RELEASE_CYCLE.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/ROUTINE_TASKS.md`, `docs/roadmap/implement.md`, a comment in `src/devops_cli/config/defaults.py`, and the tests and test docstrings that read or name the sections.
- The route of the implement step for `k8s/**` (`src/devops_cli/roadmap/step_rules.py`) gives the sections "Stacks Overview" and "Directory Structure" of `k8s/README.md`, and a second route gives the section "Image Pins" of `docs/CLUSTER.md`. The row "change a manifest, the cluster or OpenTofu" of `AGENTS.md` links `docs/CLUSTER.md`, because a test requires that the row of a route links its document.
- Add `docs/CLUSTER.md` to the Guides tab of the docs site (`.nav.yml`) and to `docs/index.md`.
- The change has spec deltas, because the alert descriptions, a step message and the documented runbook sections are observable: `roadmap-service-alerts`, `crawl4ai-alerts`, `roadmap-service-webhooks`, `searxng-service` (the requirement "The README lists the kept engines" becomes "The cluster document lists the kept engines") and `roadmap-implement-step/inputs`.

## Capabilities

### Modified Capabilities

- `roadmap-service-alerts`: each description points to `(docs/CLUSTER.md, Roadmap service)`, and the section "Roadmap service" of `docs/CLUSTER.md` names each alert.
- `crawl4ai-alerts`: each description points to the section "Crawl4AI" of `docs/CLUSTER.md`.
- `roadmap-service-webhooks`: the subsection Webhook route of `docs/CLUSTER.md` holds the query of the answers of the route.
- `searxng-service`: `docs/CLUSTER.md` lists the kept engines.
- `roadmap-implement-step/inputs`: a group that changes only a manifest gets the section "Image Pins" of `docs/CLUSTER.md` too.

## Impact

- One pull request. It changes no code path but the route table of the step.
- Application `prometheus` syncs new descriptions for 21 alert rules. The rule names, expressions, durations and labels do not change, so no alert state resets.
- The manifests under `k8s/devops/` change only in comments. `kubectl kustomize` gives the same output, and the ConfigMap that `devops k8s deploy-stack` renders drops the comments of the template.
- The second of this pull request and the pull request of #5292 to merge must rebase: #5292 moves the rule groups of these 21 descriptions to another file, and both change requirements of `roadmap-service-alerts` and `crawl4ai-alerts`.

## Feasibility

I checked the premise on `origin/main` at `f9ca1b4de`:

- `git show origin/main:k8s/README.md` holds "## devops-cli in the cluster" (lines 697 to 925), "### Image Pins" (lines 1215 to 1217) and "### Service Image Updates" (lines 1219 to 1237).
- `src/devops_cli/roadmap/step_rules.py:86-87` routes `k8s/**` to the section "Image Pins" of `k8s/README.md`. `tests/invariants/test_runner_image.py:257` and `tests/invariants/test_k8s_searxng.py:23` read `k8s/README.md`.
- To find each reader, I removed the three sections from `k8s/README.md` in the worktree and ran the 77 test files that name a README. 19 tests failed in 8 files: `test_runner_image.py`, `test_k8s_monitoring_alerting.py` (7), `test_roadmap_implement_deadline_settings.py` (6), `test_k8s_roadmap_service.py`, `test_agents_md.py` (the anchor `k8s/README.md#crawl4ai` of `CONTRIBUTING.md`), `test_k8s_searxng.py`, `test_roadmap_step_rules.py` and `test_configmap_rollout_rule.py`.
- A census of the lines of `origin/main` that name `k8s/README.md` with a moved section counts 216 lines: 106 live lines, 104 lines in archived changes and 6 lines in recorded evaluation fixtures (`tests/fixtures/roadmap_eval/`). `k8s/README.md` itself holds 8 more. The archived changes, `CHANGELOG.md` and the evaluation fixtures are records of the past, so they stay as they are. The issue gives about 190.
- `zensical.toml` validates links and anchors (`invalid_links`, `invalid_link_anchors`), and `devops docs site build --strict` fails on a page that no nav tab lists.

## Existing Tool Considered

The change moves text and builds no tool. Zensical (`devops docs site build --strict`) and the link tests of `tests/invariants/test_agents_md.py` find a link to a missing page or anchor, and `git grep` finds the prose pointers. The change deletes no internal code.
