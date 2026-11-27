## ADDED Requirements

### Requirement: The Argo CD gate reads a plain equals of a path build as a string
The Argo CD gate (`check_argocd_gate`) SHALL load the Kustomize build of a path source with the shared safe loader, which reads a plain scalar `=` as the string `"="`, as Kubernetes reads it.

#### Scenario: A path source builds a CRD with a plain equals
- **WHEN** the path source of an Application builds a CustomResourceDefinition whose enum lists `- =` and `- =~`
- **THEN** the gate passes and names the Application as built
