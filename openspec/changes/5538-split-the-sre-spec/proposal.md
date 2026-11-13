# Proposal

## Why

Closes #5538. `docs/SRE.md` (#5488) mixes three kinds of text: general SRE rules and methods, decisions of the homelab environment, and measured values with a read date. The production readiness extension draft has the same mix: 90 guideline rows and a hand-read state of each row. The owner directions of 2026-11-13 ([comment on #5538](https://github.com/dan-petty/devops-cli/issues/5538#issuecomment-6863311682)) split the guidelines from the details of one environment, let programs give the metrics, and let no agent update each measured value or each detail of the service layout by hand. The owner also decided that live values and dated snapshots stay out of git, that the gaps live in GitHub tracker issues, and that the description of a service lives in one place.

## What Changes

- Move `docs/SRE.md` to `docs/guidelines/sre.md`, the SRE guideline. It keeps only the parts that apply with no change to each managed project: the scope, 9 principles, the catalog method with the tiers and the data classes, the SLO defaults, the burn-rate table, the notifications, the default incident triggers, the incident steps, the postmortems, toil, change safety, the error budget policy, deprecation, the backups and restore tests, capacity planning, the runbook rule, the cadence, rules SRE1 to SRE9 and the sources. Issue numbers, dates and environment paths become roles. Principle 9 and the incident steps answer the owner request of 2026-11-13 that jobs run asynchronously and are ready for event-driven triggers: an alert, a deploy or a schedule starts each automated step, no service waits for it, a scheduled pass finds the work of a lost event, and the key of the incident record makes a repeated notification open no second incident.
- Add `docs/guidelines/production-readiness.md` from the extension draft: the levels, 91 rows in 10 areas with a "Measured by" column (a Scorecard check, a kube-linter check, a command, a query or a file), the readiness record, the review, who decides, the steps of a new service and the sources. It holds no state. The readiness report of the launch branch is the record of a launch. A new row OWN-7 checks that `AGENTS.md` routes to the guideline index.
- Remove the current state, the 16 queries, the gap table and every measured value. The service dashboards, `devops prometheus rules`, `devops roadmap review run` and the readiness report give them.
- Add `k8s/catalog.toml`: one entry for each service of the old Table 2, with its Applications, an optional workload list, its tier, its data class and its dependencies. It holds no SLO id and no dashboard uid. It holds a description only for a service with no Homepage UI (#4600). #5535 renders it.
- Add the section "Service levels" to `k8s/README.md`: a link to the catalog data and no service table, the 5 SLO rows until #4709, the owner value 14.4x of incident trigger 1 until #5477, the page budget of one owner, the accepted exceptions and one line of runbook links. It links gap tracker #5541 and holds no gap row.
- Add the 4 rules for a live value change to "Homelab Values at Deploy Time" of `k8s/README.md`, and the rollout of the roadmap Service to `docs/CLUSTER.md`.
- Add `docs/guidelines/index.md`, the "Guidelines" tab of `.nav.yml`, the guideline test `tests/invariants/test_guidelines.py` and its line in `docs/TESTING.md`. These are the same as in PR #5492 (#5444), which is not merged yet.
- Point the links of `.nav.yml`, `docs/CLUSTER.md`, `docs/DESIGN.md`, `docs/index.md` and `k8s/README.md` at the guideline. Apply the Renovate sentence of the draft to `docs/SDLC.md` with no count and no issue number.
- Carry no spec delta: the change moves documents and adds a data file that no code reads yet.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/guidelines/sre.md` (moved from `docs/SRE.md`), `docs/guidelines/production-readiness.md` (new), `docs/guidelines/index.md` (new), `docs/index.md`, `.nav.yml`, `docs/CLUSTER.md`, `docs/DESIGN.md`, `docs/SDLC.md`, `docs/TESTING.md`, `k8s/README.md`.
- Data: `k8s/catalog.toml` (new).
- Tests: `tests/invariants/test_guidelines.py` (new, the same as in PR #5492).
- Gaps: tracker #5541 holds the gaps of SRE.md Table 8 and of the draft Table 10 as sub-issues and reference lines.

## Feasibility

- `uv run devops ci test tests/invariants/test_guidelines.py` failed on the text of `docs/SRE.md` and of the draft checklist (issue numbers, dates, `k8s/` paths, `today`, state row ids), and passes on the two guidelines.
- Each `applications` value of `k8s/catalog.toml` names an Application of `k8s/argocd/apps/`, and each `depends_on` value names an entry of the file. The workload names come from the manifests of `k8s/devops/` and `k8s/llm/`.
- The kube-linter check names come from `kube-linter checks list` (0.8.3). Each `devops` command that the guidelines name has a `--help` page.
- `devops config set` keeps a copy of `config.yaml` and records the changed keys in the audit log (`save_settings`), as the first live value rule says.

## Existing Tool Considered

The guidelines are documents, not code. Their rows use open tools: OpenSSF Scorecard, kube-linter, kubernetes-mixin, KRR, Sloth, Trivy and kube-bench. The catalog data is TOML, which the Python standard library reads. Backstage holds a service catalog too, but it is a running portal with a database, so #5535 renders the catalog with the renderer of `devops k8s image-pins`. The guideline test is the test of PR #5492.
