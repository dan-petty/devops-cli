# Proposal: #5443

## Why

Closes #5443. The owner asked on 2026-11-13 for three project specs: SRE service implementation, Kubernetes performance tuning (#5444), and agentic workflow implementation and tuning. This change is the agentic workflow part.

The first draft of this change was a spec with the measured state of the roadmap jobs: a baseline of 2026-11-13 with the grades, the tokens, the spend, the tool calls, the live configuration and the size of each eval set, its queries, and a table of 36 gaps. Later on 2026-11-13 the owner gave three directions ([comment on #5443](https://github.com/dan-petty/devops-cli/issues/5443#issuecomment-6862798400)): split the details of one environment from the guidelines for each managed project, let programs give the metrics, and let no agent update each measured value by hand. The owner also decided that the gaps live in GitHub tracker issues, not in tables in git, and that live values and dated snapshots stay out of git. These directions replace the measured baseline of the issue. The owner also asked that the jobs run asynchronously and be ready for event-driven triggers.

## What Changes

- Move the spec to `docs/guidelines/agentic-jobs.md`, the agentic jobs guideline. It keeps only the parts that apply with no change to each managed project: the scope, 10 principles, the default targets, the job model, the measure of a job, the tuning loop with its trial, the model choice, the context, the tools, the telemetry and cost, the evaluation process and the rules `AW-*`. Each rule that pointed to another document gets a one-line rule text.
- Move the method parts of `docs/roadmap/job-success.md` into the guideline: why a log line, the ratio `p`, the Wilson interval, the efficiency, the 80% rule and the LogQL form of the ratio. `job-success.md` keeps the contract of devops-cli: the result line, the attempt and the intended result of each job, the grade table and its bullets, with links to the dashboard and to `devops roadmap eval grades --dry-run` in place of the queries.
- Add principle P10 and rule AW-J7: an event or a schedule starts each job, no caller waits for it, a reconcile pass finds the work of a lost event, and a unit name from the input makes a repeated event start no second run.
- Remove the baseline (the grades, the tokens, the spend, the tool calls, the configuration in force, the eval set sizes and the queries) and the gap table. `devops roadmap eval grades`, the devops-cli Telemetry dashboard, `docs/CONFIGURATION.md`, `devops roadmap eval <set> --dry-run` and the project review give these values.
- Add the section "Agentic jobs in devops-cli" to `docs/ROADMAP_WORKFLOW.md`: the programs that give the values, the targets that devops-cli adds, the document or the code that applies each rule, and a link to gap tracker #5543. It holds no gap row.
- Add the line of this guideline to `docs/guidelines/index.md`. PR #5567 added the index, the "Guidelines" tab of `.nav.yml` and the guideline test `tests/invariants/test_guidelines.py` first, with the same bytes as this change, so this change keeps their `main` versions. PR #5492 adds its own line of the index.
- Fix the stale text of the first draft: the closed duplicate #5474 becomes tracker #5482, the branch runs point to #5533, the ceilings that #5440 made settings are no longer constants, the eval set sizes go, and `devops roadmap explain --trace` shows only the trace of the implement job.
- Point the links to `docs/AGENTIC_WORKFLOWS.md` at the guideline: `CONTEXT.md` (term **Branch run**), `docs/ROADMAP_WORKFLOW.md`, `docs/roadmap/job-success.md` and the docstring of `src/devops_cli/roadmap/job_result.py`.
- Carry no spec delta: the change moves documents and adds a test of documents. No command, option, message or manifest changes.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/guidelines/agentic-jobs.md` (moved from `docs/AGENTIC_WORKFLOWS.md`), `docs/guidelines/index.md` (one line), `docs/roadmap/job-success.md`, `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`.
- Code: the docstring of `src/devops_cli/roadmap/job_result.py`. No behavior changes.
- Tests: none. `tests/invariants/test_guidelines.py` of PR #5567 checks the guideline.
- Gaps: tracker #5543 holds the gaps of the first draft as sub-issues and reference lines.

## Feasibility

- `uv run devops ci test tests/invariants/test_guidelines.py` fails on the first draft (issue numbers, dates, `today`, `currently` and the ids `S1` to `S4` of the safety rules), and passes on the guideline. The safety rules are `AW-G1` to `AW-G4`, because the test refuses a state row id `S<n>`.
- `docs/commands/roadmap.md` says that `devops roadmap explain --trace` prints the trace of the last run of the implement job.
- `src/devops_cli/config/settings.py` holds `gate_returns`, `gate_return_extensions`, `verify_repair_rounds` and `verify_repair_rounds_ceiling` as settings with bounds, and `k8s/devops/roadmap-service/admissionpolicy.yaml` sets the ceiling of a Job deadline.
- ADR 0021 section 2 gives the event-driven start of the roadmap jobs: only the webhook router and the sweep create units, a unit sets a due mark, and a unit name fixed by its input makes a second create get 409.
- Issue states read with `uv run devops gh api repos/dan-petty/devops-cli/issues/<n>` on 2026-11-13: #5474 closed as a duplicate of #5482; #5440 and #5445 closed as completed; #5533, #5543, #5494, #5427, #5199, #5241, #4843, #5168, #4724, #5164, #5173 and #5466 open.

## Existing Tool Considered

The guideline is a document, not code. It names the open tools that the jobs use: pydantic-ai `UsageLimits`, Pydantic Evals, statsmodels for the Wilson interval, Loki and Prometheus, Kubernetes Jobs, Argo Workflows `retryStrategy` and Argo Events. The guideline test is the test of PR #5492, with no change. Cost of this amendment: about 0.3 M tokens and 2 hours.
