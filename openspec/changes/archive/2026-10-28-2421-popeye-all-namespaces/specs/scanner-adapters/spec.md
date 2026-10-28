# Spec Delta

## MODIFIED Requirements

### Requirement: Popeye reports warnings and errors over the namespace that it gets
The Popeye adapter SHALL run `popeye -o json -l warn`, followed by `-A` when it gets no namespace, by `-n <namespace>` when it gets a namespace, and by `--context <context>` when it gets a context other than the current one. The parser SHALL read `popeye.sections` and SHALL give one finding for each issue: at `k8s:<linter>/<namespace>/<name>`, followed by `/<group>` when the group names a container, with the message as its title, and with the severity MEDIUM for level 2 and HIGH for level 3.

#### Scenario: Popeye reports issues of a resource and of its container
- **WHEN** Popeye runs over the namespace `argocd`, exits 1, and reports a level 3 issue and a level 2 issue of the Deployment `argocd/argocd-applicationset-controller`, and a level 2 issue of its container `applicationset-controller`
- **THEN** the scan ran, the command is `popeye -o json -l warn -n argocd`, and the findings are a HIGH and a MEDIUM finding at `k8s:deployments/argocd/argocd-applicationset-controller` and a MEDIUM finding at `k8s:deployments/argocd/argocd-applicationset-controller/applicationset-controller`

#### Scenario: Popeye gets no namespace
- **WHEN** the adapter runs Popeye with no namespace
- **THEN** the command is `popeye -o json -l warn -A`
