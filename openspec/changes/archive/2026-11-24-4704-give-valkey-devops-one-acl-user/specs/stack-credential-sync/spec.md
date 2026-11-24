## ADDED Requirements

### Requirement: The valkey-devops role passwords and aclfile come from one push
Secret `llm/valkey-devops-auth` SHALL hold one generated `hex` 32-byte value for each of the keys `sweep`, `brain`, `agent` and `metrics`, and the key `users.acl` SHALL hold the aclfile that the same push builds from those four values and from key `password`. Secret `devops/devops-cli` SHALL keep `DEVOPS_CLI_VALKEY_PASSWORD` from key `password` of `llm/valkey-devops-auth`.

#### Scenario: The plan of the cache Secret
- **WHEN** The test `tests/k8s/test_cluster_secret_plan.py` plans `llm/valkey-devops-auth` with an empty keyring
- **THEN** The plan generates one 64-character hex value for each of `sweep`, `brain`, `agent` and `metrics`, and the planned `users.acl` holds `user sweep on >` with the generated `sweep` value and `user default on >` with the generated `password` value

#### Scenario: A second push changes nothing
- **WHEN** The test `tests/k8s/test_cluster_secret_plan.py` plans the Secret again with the keyring holding the five values
- **THEN** Every key of the Secret is `unchanged` and the planned `users.acl` equals its live value
