# Proposal: #5443

## Why

On 2026-11-13 the owner asked for three project specs: SRE service implementation, Kubernetes performance tuning, and agentic workflow implementation and tuning. This change is the third spec (#5443). The rules of the agentic jobs are in many documents and in owner decisions that are only in issues: the job grades in `docs/roadmap/job-success.md`, the evals in `docs/ROADMAP_WORKFLOW.md`, the decision points in ADR 0019 and ADR 0020, the step rows in ADR 0021, and the decisions of 2026-11-13 to double the limits of a job under 80 % and to traverse configuration values until a job works. No document gives the target in numbers, the measured state, one tuning loop and the gaps with their issues.

## What Changes

- Add `docs/AGENTIC_WORKFLOWS.md`, a normative spec in the form of `docs/DESIGN.md`: purpose and scope, principles, the target with numbers, the baseline of 2026-11-13 from the result lines in Loki and the counters in Prometheus (with each query), the method (the job model, the measure of success, the tuning loop with its trials, the model choice, the context, the tools, the safety, the telemetry and cost, and the evaluation process), the rules for agents and jobs with the prefix `AW-`, and a gap table that maps each of 36 gaps to an open issue.
- The spec owns only the new rules: the tuning loop, the default of one branch run, the live proof, the line of a new job, the funnel, the context and tool rules, the cost of a result and the agreement of the spend counters. Each other rule is a link to its owner.
- `docs/roadmap/job-success.md` and the docstring of `src/devops_cli/roadmap/job_result.py` said that the owner tunes the caps only after 80 % success. The owner decision of 2026-11-13 gives a job under 80 % larger limits. Both now say that a job under 80 % gets larger limits and only a job that holds 80 % gets smaller limits for cost, with a link to the tuning loop.
- `CONTEXT.md` gets the term **Branch run** for the parallel runs of one job, because a candidate is an issue that intake has not placed. `docs/ROADMAP_WORKFLOW.md` gives the live plans of an acceptable stage score the window of 28 days, so the target of Table 3-1 can be measured.
- Intake files the gaps that no open issue covered: #5472 (G14, a live defect of the nested limits), #5474 (the tracker of the pipeline split, G30, with G11 and G31), #5476 (G3), #5479 (G12) and #5481 (G36, `devops roadmap eval grades` cannot reach Loki from a workstation). G5 joins #4724 and G28 joins #3109.
- `docs/ROADMAP_WORKFLOW.md` (Purpose) links the spec. The docs site lists the spec in the Guides tab (`.nav.yml`), and `docs/index.md` lists it.
- The change alters only documents and one docstring, so it has no spec delta (`skip_specs: true`). It fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No spec holds the rules of this document.

## Impact

- Documents: `docs/AGENTIC_WORKFLOWS.md` (new), `docs/roadmap/job-success.md`, `docs/ROADMAP_WORKFLOW.md`, `docs/index.md`, `.nav.yml`, `CONTEXT.md`.
- Code: the docstring of `src/devops_cli/roadmap/job_result.py`. No behavior changes.
- `CONST_DOCS_INVENTORY` needs no entry: a Markdown file that no class lists is hand-written (`src/devops_cli/docs/inventory.py`).
- `AGENTS.md` gets no routing row. It has 4,222 of 4,500 characters, and the two sibling specs (#5444, #5445) can need the room. `docs/ROADMAP_WORKFLOW.md`, which `AGENTS.md` routes to, links the spec.
- The spec names the SRE service spec (#5445) and the Kubernetes performance spec (#5444) by issue, because their files are not on `main`.

## Feasibility

Checked on 2026-11-13 against origin/main (release 0.129.1):

- Loki, through the Grafana datasource `loki`, an instant query at 2026-11-13T16:00:00Z with the base query of `docs/roadmap/job-success.md`: 372 result lines of the Service in 7 days, and 2 `fix_plan` lines of the Job stream `roadmap-fix-plan-validation`. The first line is from 2026-11-12T12:58Z (release 0.118.0). Item #4697 has two `implement` lines 8 s apart.
- `uv run devops roadmap eval grades --dry-run` prints the same base query, with the selector `app_kubernetes_io_name="roadmap-service"` only.
- Prometheus: `devops_cli_ai_spend_usd_total` 81.76 USD and `litellm_spend_metric_total` 119.35 USD in 7 days. By `user_agent`, devops-cli clients spent 119.35 USD of it and other clients 0.0012 USD. Over the 27 hours of lines, the spend of `stage` is 2.22 USD and of `implement` 0.48 USD, and the prompt tokens of `stage` are 212.11 M and of `implement` 94.41 M; `devops_cli_roadmap_tool_calls_total`, `devops_cli_roadmap_tool_limit_hits_total` and `devops_cli_decision_point_total` give Table 4-3.
- `kubectl get configmap -n devops devops-cli-config` (read only): the doubled limits of Table 4-4, with `deadline_stall_seconds` 8,400 and `deadline_extension_seconds` 10,800. The defaults come from `src/devops_cli/config/defaults.py`, and the ceilings from the `le=` bounds and the model checks of `src/devops_cli/config/settings.py`. `k8s/devops/roadmap-service/admissionpolicy.yaml` refuses `activeDeadlineSeconds` above 14400.
- `kubectl get runtimeclass` shows `gvisor` with the handler `runsc`.
- `src/devops_cli/roadmap/decision_registry.py` registers one point, `stage.verify_screen`.
- The case counts of Table 4-5 come from `find <dir> -mindepth 1 -maxdepth 1 -type d` of each fixture folder (`split.json` deals the 59 stage cases as A 29 and B 30) and the `cases` lists of the two intake JSON files.
- The issue states of the gap table come from `uv run devops gh api repos/dan-petty/devops-cli/issues/<n>` on 2026-11-13. A search found no open issue for G3, G12, G14 and G30, so intake filed them. G5 matches #4724 and G28 matches #3109.
- The design of the pipeline split (24 jobs, `due_jobs`, the branch runs and the judge, the divide rule) is the plan that the owner approved on 2026-11-13. Tracker #5474 holds it, so the spec cites the tracker as its source.
- `uv run devops roadmap eval grades --window 24h` stops with "Loki at http://localhost:3100 did not answer" when `loki.url` is not set (#5481).
- The primary sources were read on 2026-11-13: the four Anthropic engineering articles, the prompt caching page, the DeepSeek context caching page, the pydantic-ai agent and evals pages, the Kubernetes Job page, the Argo Workflows retries page, and the SRE workbook chapter "Alerting on SLOs".

## Existing Tool Considered

The spec is a document, not code. It names the open tools that the jobs use or adopt: pydantic-ai `UsageLimits` for the limits of a run, Pydantic Evals for the eval cases, statsmodels for the Wilson interval, Loki and Prometheus for the measures, Kubernetes Jobs and Argo Workflows `retryStrategy` for the retries. Cost to write: about 0.6 M tokens and 3 hours of elapsed time. Keep: one update for each changed job rule or measurement. Fix: about 0.05 M tokens for each wrong rule.
