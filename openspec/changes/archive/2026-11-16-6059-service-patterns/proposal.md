# Proposal: #6059

## Why

The rules for a service or a workload of devops-cli are in 27 ADRs, `docs/CLUSTER.md`, `k8s/README.md`, the guidelines, issue comments and owner decisions. No document collects them, so each new service or fix decides again, and a gap shows only in an incident. Examples are the 503 answers during each `Recreate` rollout of the Service (#6058) and the webhook loss at the edge (#5035). Owner, 2026-11-16: "we should create service design pattern standards for the project" (#6059).

## What Changes

- Add `docs/SERVICE_PATTERNS.md`. It gives each pattern as a rule, the reason (an ADR, an owner decision or an upstream document) and the check that holds it. The groups are the checks, ingress and webhooks, workers and singletons, releases, jobs, state, calls, budgets, configuration, security, telemetry, dry runs and tools.
- The document states the owner rules of 2026-11-16 for the checks: a test checks the source code, a schema or policy tool checks a manifest or a configuration file, and a behavior that spans components gets an integration or end-to-end test.
- The document gives the steps of an audit. The audit table of 2026-11-16 is a comment on tracker #5541, because no document holds the state of a workload (production readiness guideline, Readiness record).
- Add one row to the "Where to look" table of `AGENTS.md`. Link the document from `docs/CLUSTER.md`, `ARCHITECTURE.md` section 7.7, `docs/index.md` and the Guides tab of `.nav.yml`.
- This change alters no behavior that a consumer observes: it changes documents only. So it has no spec delta, and `.openspec.yaml` sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `docs/SERVICE_PATTERNS.md` (new), `AGENTS.md`, `ARCHITECTURE.md`, `docs/CLUSTER.md`, `docs/index.md`, `.nav.yml`.
- The change fits one pull request.

## Feasibility

- Read on `origin/main` at `ebc1e68b9`, 2026-11-16: ADRs 0001 to 0027, `docs/CLUSTER.md`, `k8s/README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `docs/DESIGN.md`, `docs/TESTING.md` and the four guidelines.
- The audit read the manifests of `k8s/devops/` and `k8s/llm/` and the live objects with `kubectl get` only. It changed nothing in the cluster.
- Each test that a check names exists on `origin/main`. No check names a test that holds a value of a manifest, by the owner rule of 2026-11-16.
- The log of the Static Analysis job on `main` shows that CI does not run kube-linter or kubeconform ("Scanner 'kubelinter' was not run"). So a rule that only those tools can check names its issue (#6068, #5084).

## Existing Tool Considered

The standards are a document, and no tool writes them. Each check that the document names is an open tool or the code of the project: kube-linter, kubeconform, `trivy config`, promtool, ast-grep, Pod Security Admission and the ValidatingAdmissionPolicies of Kubernetes. The change deletes no code.
