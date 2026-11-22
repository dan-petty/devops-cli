## ADDED Requirements

### Requirement: deploy-stack renders the credential-free sandbox ConfigMap
The command `devops k8s deploy-stack --stack devops` SHALL render and apply ConfigMap `devops-cli-config-sandbox` in namespace `devops` from the active config, on the native manifest path and on the Argo CD-managed path, and SHALL apply `devops-cli-config` first.

#### Scenario: Deploy the devops stack on a native cluster
- **WHEN** deploy-stack runs for the devops stack on a native cluster
- **THEN** the command sends a manifest on stdin whose metadata.name is devops-cli-config-sandbox and whose metadata.namespace is devops, after the manifest of devops-cli-config

#### Scenario: Deploy the devops stack on an Argo CD-managed cluster
- **WHEN** deploy-stack runs for the devops stack on a cluster that Argo CD manages
- **THEN** the command applies devops-cli-config-sandbox from the active config before it leaves the manifests to Argo CD

### Requirement: The sandbox ConfigMap drops every credential key at any depth
The rendered `devops-cli-config-sandbox` SHALL omit every key of its `devops-cli.yaml` value whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` and whose value is not a number or a boolean, at any depth of maps and lists, and SHALL keep every other key with its value.

#### Scenario: Credential keys at the top level and nested
- **WHEN** the template config holds github_token, api_key, db_password and a secret key beside non-credential keys
- **THEN** the rendered devops-cli.yaml value holds none of those four keys and still holds the non-credential keys with their values

### Requirement: The sandbox ConfigMap keeps a number under a credential-like name
The rendered `devops-cli-config-sandbox` MUST keep a key whose name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` when its value is a number or a boolean, because such a value is a count and not a credential.

#### Scenario: Token budgets of the template
- **WHEN** the sandbox ConfigMap is rendered from the template k8s/devops/configmap.example.yaml
- **THEN** roadmap.stage.step_tokens, roadmap.review.token_budget, roadmap.implement.step_token_budget and roadmap.implement.item_token_budget keep their template values

### Requirement: The sandbox ConfigMap keeps the name and the data key the run Job mounts
The rendered ConfigMap MUST keep the name `devops-cli-config-sandbox` and the single data key `devops-cli.yaml`, so the planner run Job mounts it at `/config` with `DEVOPS_CLI_CONFIG` unchanged.

#### Scenario: Name and data key are stable
- **WHEN** the sandbox ConfigMap is rendered from any config
- **THEN** metadata.name is devops-cli-config-sandbox and data holds exactly the key devops-cli.yaml

### Requirement: teardown-stack deletes the sandbox ConfigMap
The command `devops k8s teardown-stack --stack devops` SHALL delete ConfigMap `devops-cli-config-sandbox` with `--ignore-not-found`, as it deletes `devops-cli-config`.

#### Scenario: Tear down the devops stack
- **WHEN** the teardown runs for the devops stack
- **THEN** the command issues kubectl delete configmap devops-cli-config-sandbox -n devops --ignore-not-found and exits 0 when the ConfigMap is absent

### Requirement: A dry run names the sandbox ConfigMap and prints no value of it
The commands `devops k8s deploy-stack --stack devops --dry-run` and `devops k8s teardown-stack --stack devops --dry-run` SHALL name the sandbox ConfigMap with the other rendered resources and SHALL print no value of it.

#### Scenario: Dry run of the devops stack
- **WHEN** the command runs with --dry-run for the devops stack
- **THEN** the details name devops/devops-cli-config-sandbox and hold none of its content

### Requirement: A test names each credential key of the rendered config
A test SHALL parse the rendered ConfigMap, walk every key of the `devops-cli.yaml` value at any depth, and name each key whose lower-case name holds a word of `CONST_MCP_SECRET_PARAMETER_WORDS` and whose value is not a number or a boolean.

#### Scenario: The walk names a credential key
- **WHEN** the walk runs on a hand-built config that holds github_token at the top level and ai.api_key nested
- **THEN** it names github_token and ai.api_key

#### Scenario: The rendered ConfigMap holds no credential key
- **WHEN** the walk runs on devops-cli-config-sandbox rendered from a template that holds a credential key at the top level and one nested
- **THEN** it names no key
