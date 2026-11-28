# Proposal: #7560

## Why

In #7560, Trivy `config` reports HIGH misconfiguration `KSV-0118` (code-scanning alert `1258`) on `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml` because `DaemonSet/ollama-16gib` uses the default pod security context without `securityContext`. Per `SECURITY.md` ("Judging a Trivy-config Alert"), fixing the committed test fixture at source is the first choice.

## What Changes

- Add a non-root pod `securityContext` (`runAsNonRoot: true`, `runAsUser: 10001`, `runAsGroup: 10001`, `fsGroup: 10001`, `seccompProfile.type: RuntimeDefault`) to `spec.template.spec` in `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml`.
- No behavior a consumer observes changes (test fixture only), so this change sets `skip_specs: true` in `.openspec.yaml`.

## Capabilities

None (`skip_specs: true`).

## Impact

- Fixture: `tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml`.
- Closes code-scanning alert `1258` on `main` after merge when `Security Scan` runs.
- Fits in one pull request.

## Feasibility

- `trivy config --severity HIGH,CRITICAL tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml` on `origin/main` reports 1 failure: `KSV-0118 (HIGH): daemonset ollama-16gib in llm namespace is using the default security context, which allows root privileges` at `ollama-profiles.yaml:11-19`.
- `uv run devops gh api repos/dan-petty/devops-cli/code-scanning/alerts/1258` reports `state: "open"`, `rule.id: "KSV-0118"`.
- After adding pod `securityContext`, `trivy config --severity LOW,MEDIUM,HIGH,CRITICAL tests/fixtures/k8s_environment/llm/profiles/ollama-profiles.yaml` exits 0 with 0 misconfigurations across 24 checks, and `ollama_tiers` (`src/devops_cli/k8s/gpu_placement.py:54-73`) still reads `spec.template.spec.affinity`.

## Existing Tool Considered

Aqua Trivy (`trivy config`), already installed and run by `devops scan report` and the CI `Security Scan` workflow (`TrivyConfigScanner` in `src/devops_cli/security/trivy.py:223-246`). No custom code is built or deleted.
