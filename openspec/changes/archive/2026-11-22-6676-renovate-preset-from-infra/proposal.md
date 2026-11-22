# Proposal: #6676

## Why
Closes #6676. dan-petty/infra holds the shared Renovate presets in `renovate/base.json` and `renovate/k8s.json` (ADR 0032, section 5). The rules of `renovate/base.json` are the rules of the devops-cli preset `.github/renovate/base.json`. Only the description is different. Thus `.github/renovate/base.json` is a second live copy of the shared rules, and a change to one copy does not go to the other. `tests/core/test_renovate_config.py` asserts values of the preset (`platformCommit`, no `gitAuthor`), but no test asserts a value of a manifest or a config file (#6060): the config validator of Renovate checks the config, and the test script of infra checks the presets.

## What Changes
- `.github/renovate/base.json` holds only one `extends` entry, `github>dan-petty/infra//renovate/base`, and a description that names the infra preset. The repositories that still extend the old path (dan-petty/danielpetty.com, dan-petty/devcontainer-features, dan-petty/devtools and dan-petty/vibes) get the infra rules through it until each one changes its own `extends` line. #6677 deletes the file.
- `.github/renovate.json` extends `github>dan-petty/infra//renovate/base` directly. The rules that only devops-cli uses stay in `.github/renovate.json`: the `vulnerabilityAlerts` automerge, the file patterns of the `kubernetes`, `argocd` and `helm-values` managers, the Grafana plugin datasource, the custom managers and the package rules of the repository.
- The `onboardingConfig` of ConfigMap `renovate-config` (`k8s/devops/renovate/configmap.yaml`) extends `github>dan-petty/infra//renovate/base`.
- `tests/core/test_renovate_config.py` and its row in `tests/module_durations.json` go away. No other test or check reads the old preset.
- The specs, `docs/SDLC.md`, `docs/CLUSTER.md`, `CONTRIBUTING.md` and `docs/guidelines/production-readiness.md` name the infra preset.
- The change alters a manifest (the onboarding config of the Renovate Service) and the source of the rules of the Renovate pull requests of devops-cli. That is observable, so the change carries spec deltas.
- The change fits one pull request.

## Capabilities
- `release-concurrency-and-renovate`: MODIFIED requirements "Renovate manages Terraform, devcontainers, pre-commit, and action digests under taxonomy labels", "Renovate sets no minimum release age", "Renovate updates on a fixed schedule within the CI cap", "Renovate proposes a security fix at once", "Renovate pins no digest of a version input of an action" and "A security fix branch holds one update of each dependency": each one names the infra preset, and each scenario is a live check or a validator command.
- `renovate-service`: MODIFIED requirements "The global config scopes Renovate to the App installation and onboards no repository yet" and "The shared preset merges minor, patch and digest updates after their checks".

## Impact
- The Renovate pull requests of devops-cli keep the same rules: the infra preset has the rules of the old preset.
- The four repositories that extend the old path keep the same rules through the forward. #6677 and dan-petty/danielpetty.com#39 change their `extends` lines.
- A change to a shared rule goes to dan-petty/infra, and its CI job "Renovate presets" checks it.

## Feasibility
- Infra: the contents API of dan-petty/infra on 2026-11-22 lists `renovate/base.json`, `renovate/k8s.json` and `renovate/README.md` (infra PR #22, merged 2026-11-22). The infra README says that the rules of `base.json` are the rules of the devops-cli preset at `4ff4b7c5d`.
- Equality: `.github/renovate/base.json` on origin/main `421498e41` and `renovate/base.json` of infra are equal as JSON when the `description` key is removed (`diff` of the two sorted dumps exits 0). `git log 4ff4b7c5d..origin/main -- .github/renovate/base.json` is empty.
- Readers: `git grep -n 'renovate/base\|test_renovate_config'` on origin/main finds `.github/renovate.json`, `.github/renovate/base.json`, `k8s/devops/renovate/configmap.yaml:53`, `tests/core/test_renovate_config.py`, `tests/module_durations.json`, the two specs, `docs/SDLC.md`, `docs/CLUSTER.md` and `CONTRIBUTING.md`. `git grep -n -i 'renovate preset'` adds `docs/guidelines/production-readiness.md`. No file under `src/` and no workflow reads `.github/renovate/base.json`.
- Validator: `npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict .github/renovate.json .github/renovate/base.json` exits 0 on origin/main. 44.239.2 is the Renovate release of CronJob `renovate`.

## Existing Tool Considered
- Renovate preset `extends` (the `github>owner/repo//path` form) shares the rules and needs no code. The Renovate config validator (`renovate-config-validator --strict`) checks each config, and the CI job "Renovate presets" of infra checks the presets with the validator and a Renovate extract and lookup.
- The change deletes `tests/core/test_renovate_config.py`. It adds no code.
