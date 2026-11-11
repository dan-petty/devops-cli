## ADDED Requirements

### Requirement: deploy-stack installs cert-manager and the Barman Cloud plugin with stack infra after the operator
The stack `infra` SHALL install Helm release `cert-manager` in namespace `cert-manager`, and Helm release `plugin-barman-cloud` in the namespace of release `cloudnative-pg`, after both `cloudnative-pg` and `cert-manager`. No other stack SHALL list the three releases. Argo CD SHALL sync Application `plugin-barman-cloud` in a later sync wave than Application `cert-manager`.

#### Scenario: The plugin follows the operator and cert-manager in stack infra
- **WHEN** a test reads the Helm releases of `deploy-stack`
- **THEN** stack `infra` lists `cloudnative-pg` and `cert-manager` before `plugin-barman-cloud`, `plugin-barman-cloud` has the namespace of `cloudnative-pg`, and no other stack lists the three releases

#### Scenario: Argo CD syncs the plugin after cert-manager
- **WHEN** a test reads the sync waves of the Applications under `k8s/argocd/apps/`
- **THEN** the wave of `plugin-barman-cloud` is greater than the wave of `cert-manager`, and `plugin-barman-cloud` has the sync option `SkipDryRunOnMissingResource=true`
