## MODIFIED Requirements

### Requirement: The valkey-devops pod loads its ACL users from a Secret
The push of Secret `llm/valkey-devops-auth` SHALL build the aclfile of key `users.acl`. The aclfile SHALL keep the `default` user on with the password of key `password` of that Secret, and SHALL define the users `sweep`, `brain`, `agent` and `metrics`, each with a password of its own.

#### Scenario: Rendered aclfile
- **WHEN** a test plans `llm/valkey-devops-auth` with an empty keyring
- **THEN** the planned `users.acl` holds `user default on` and one `user <name> on` line for each of `sweep`, `brain`, `agent` and `metrics`, and no other user line

## REMOVED Requirements

### Requirement: The cache Valkey and the run index refuse writes at a memory bound below their container limits
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: devops-cli's cache Valkey evicts the least recently used key at a bound below its container limit
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: devops-cli's cache Valkey requires its password and admits only namespace devops
**Reason**: The environment repository holds this manifest, values file or dashboard, and devops-cli holds no copy of it (#7290).
**Migration**: Change the file in the environment repository, which checks it.

### Requirement: A Valkey that refuses writes at its bound alerts before it reaches it
**Reason**: The environment repository holds this alert rule and its cases (#7290).
**Migration**: Change the rule in the environment repository.

### Requirement: The k8s row rejects a Valkey bound above three quarters of its memory limit
**Reason**: The `k8s` row and the `charts` row no longer read an environment file, and devops-cli holds none (#7290).
**Migration**: The environment repository checks its own tree.
