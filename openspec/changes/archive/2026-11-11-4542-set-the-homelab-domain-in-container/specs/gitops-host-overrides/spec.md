## ADDED Requirements

### Requirement: deploy-stack sets the configured domain in container environment values
For each Deployment in the render of a homelab Application, `host_patches` SHALL test and then replace each `env[].value` of a container or init container that holds the placeholder domain. It SHALL change no other value, and the Argo CD gate SHALL allow the placeholder in such a value only.

#### Scenario: A Deployment holds the placeholder in three env values
- **WHEN** `host_patches` reads a Deployment with the placeholder in an init container value, two container values, an argument and an annotation, and with a value without it
- **THEN** the patch has a `test` and a `replace` operation for each of the three env values with the placeholder, and none for the argument, the annotation or the other value

#### Scenario: The Argo CD gate reads such a Deployment
- **WHEN** the Application `devops` renders a Deployment with the placeholder in an env value and in an argument
- **THEN** the gate refuses only the argument
