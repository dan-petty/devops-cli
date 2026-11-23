## ADDED Requirements

### Requirement: Renovate updates no environment path of the homelab repository
Until step 17 of `docs/HOMELAB_REPO_SWITCH.md` deletes the environment files, `.github/renovate.json` SHALL hold a package rule that turns off each dependency of a file under `k8s` outside the product folders `k8s/devops` and `k8s/overlays/homelab/devops`. Renovate of dan-petty/homelab updates the copy of those files. The rule SHALL leave the managers and their file patterns on, so Renovate SHALL still update the pins of the product folders.

#### Scenario: The rule matches the environment paths only
- **WHEN** a person gives the `matchFileNames` patterns of the rule and the paths `k8s/llm/valkey.yaml`, `k8s/argocd/apps/argocd.yaml`, `k8s/devops/renovate/cronjob.yaml`, `k8s/overlays/homelab/devops/kustomization.yaml` and `Dockerfile` to `matchRegexOrGlobList` of Renovate 44.239.2
- **THEN** only `k8s/llm/valkey.yaml` and `k8s/argocd/apps/argocd.yaml` match

#### Scenario: The configuration stays valid
- **WHEN** a person runs `npx --yes --package renovate@44.239.2 -- renovate-config-validator --strict --no-global .github/renovate.json`
- **THEN** the command exits 0
