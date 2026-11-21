## ADDED Requirements

### Requirement: deploy-stack renders the credential-free sandbox ConfigMap
`devops k8s deploy-stack --stack devops` SHALL render and apply ConfigMap `devops-cli-config-sandbox` in namespace `devops` from the active config, on the native path and the Argo CD-managed path.

#### Scenario: Deploy the devops stack on a native cluster
- **WHEN** deploy-stack runs for the devops stack on a native cluster
- **THEN** the second manifest that the command sends to kubectl apply holds metadata.name devops-cli-config-sandbox and metadata.namespace devops

#### Scenario: Deploy the devops stack on an Argo CD-managed cluster
- **WHEN** deploy-stack runs for the devops stack on a cluster that Argo CD manages
- **THEN** the command applies devops-cli-config-sandbox from the active config before it leaves the manifests to Argo CD

### Requirement: The sandbox ConfigMap drops every credential key at any depth
The rendered `devops-cli-config-sandbox` SHALL omit every key of its `devops-cli.yaml` value whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS`, at any depth of maps and lists, and SHALL keep every other key with its value.

#### Scenario: Credential keys at the top level and nested
- **WHEN** the template config holds github_token, api_key, db_password and a nested secret key beside non-credential keys
- **THEN** the rendered value holds none of those four keys and still holds the non-credential keys with their values

### Requirement: The sandbox ConfigMap keeps the name and the data key the run Job mounts
The rendered ConfigMap MUST keep the name `devops-cli-config-sandbox` and the single data key `devops-cli.yaml`, so the planner run Job mounts it at `/config` with `DEVOPS_CLI_CONFIG` unchanged.

#### Scenario: Name and data key are stable
- **WHEN** the sandbox ConfigMap is rendered from any config
- **THEN** metadata.name is devops-cli-config-sandbox and data holds exactly the key devops-cli.yaml

### Requirement: teardown-stack deletes the sandbox ConfigMap
`devops k8s teardown-stack --stack devops` SHALL delete ConfigMap `devops-cli-config-sandbox` with `--ignore-not-found`, as it deletes `devops-cli-config`.

#### Scenario: Tear down the devops stack
- **WHEN** the teardown runs for the devops stack
- **THEN** the command issues kubectl delete configmap devops-cli-config-sandbox -n devops --ignore-not-found and exits 0 when the ConfigMap is absent

### Requirement: A dry run names the sandbox ConfigMap and prints no value of it
`devops k8s deploy-stack --stack devops --dry-run` SHALL name the sandbox ConfigMap with the other rendered resources and SHALL print no value of it.

#### Scenario: Dry run of the devops stack
- **WHEN** the command runs with --dry-run for the devops stack
- **THEN** the details name devops/devops-cli-config-sandbox and hold none of its content

### Requirement: A test walks every key of the rendered config
A test SHALL parse the rendered ConfigMap, walk every key of the `devops-cli.yaml` value at any depth, and fail naming each key whose name `is_secret_parameter_name` matches.

#### Scenario: Credential-free output test
- **WHEN** the test renders the sandbox ConfigMap from a fixture template that holds a credential key at the top level and one nested
- **THEN** the test names each offending key and fails, and the same test on a credential-free fixture passes
