# Tasks

## 1. Take the shared preset from infra

Kind: other (config and manifest). Reads: `.github/renovate/base.json`, `.github/renovate.json`, `k8s/devops/renovate/configmap.yaml`, `renovate/base.json` of dan-petty/infra. Changes: `.github/renovate/base.json`, `.github/renovate.json`, `k8s/devops/renovate/configmap.yaml`.

- [ ] 1.1 Replace the content of `.github/renovate/base.json` with `$schema`, a description that names the old path and the infra preset `github>dan-petty/infra//renovate/base`, and the one `extends` entry `github>dan-petty/infra//renovate/base`
  - Verification: `$ npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict .github/renovate.json .github/renovate/base.json` exits 0
- [ ] 1.2 In `.github/renovate.json`, change the one `extends` entry to `github>dan-petty/infra//renovate/base`. Keep every other key and rule of the file
  - Verification: `$ npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict --no-global .github/renovate.json` exits 0
- [ ] 1.3 In ConfigMap `renovate-config` (`k8s/devops/renovate/configmap.yaml`), change the `extends` entry of `onboardingConfig` to `github>dan-petty/infra//renovate/base`, and make the header comment name the shared preset of dan-petty/infra
  - Verification: `$ uv run devops ci --check --only k8s` passes

## 2. Delete the test that reads the old preset

Kind: other (deletion). Reads: `tests/core/test_renovate_config.py`, `tests/module_durations.json`. Changes: `tests/core/test_renovate_config.py`, `tests/module_durations.json`.

- [ ] 2.1 Delete `tests/core/test_renovate_config.py` and its row in `tests/module_durations.json`
  - Verification: `$ test -z "$(git ls-files tests/core/test_renovate_config.py)"` exits 0

## 3. Name the infra preset in the documents

Kind: other (documents). Reads: `docs/SDLC.md`, `docs/CLUSTER.md`, `CONTRIBUTING.md`, `docs/guidelines/production-readiness.md`. Changes: `docs/SDLC.md`, `docs/CLUSTER.md`, `CONTRIBUTING.md`, `docs/guidelines/production-readiness.md`.

- [ ] 3.1 In the Automated Dependency Updates item of `docs/SDLC.md`, the Renovate section of `docs/CLUSTER.md`, the Dependency Versions item of `CONTRIBUTING.md` and the Repository row of `docs/guidelines/production-readiness.md`, name the shared preset `renovate/base.json` of dan-petty/infra and its `extends` entry `github>dan-petty/infra//renovate/base` in place of `.github/renovate/base.json`
  - Verification: `$ uv run devops ci docs` passes
- [ ] 3.2 Make sure that only the description of the forward names the old path
  - Verification: `$ test "$(git grep -l 'devops-cli//.github/renovate/base' -- . ':!openspec/changes')" = .github/renovate/base.json` exits 0
