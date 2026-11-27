## ADDED Requirements

### Requirement: The stack commands read a plain equals of a path build as a string
`devops k8s deploy-stack` and `devops k8s teardown-stack` SHALL load the Kustomize build of a path source with the shared safe loader, which reads a plain scalar `=` as the string `"="`, as Kubernetes reads it.

#### Scenario: The dry run lists a build that holds a plain equals
- **WHEN** the dry run of `devops k8s deploy-stack` builds a path source whose build holds a NetworkPolicy and a CustomResourceDefinition whose enum lists `- =` and `- =~`
- **THEN** the command exits 0, and `details.path_sources` lists the NetworkPolicy and the CustomResourceDefinition of the build
