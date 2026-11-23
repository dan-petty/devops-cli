# Proposal: #6685

## Why
The environment Secret rows live in homelab `k8s/cluster-secrets.toml` and in `src/devops_cli/k8s/cluster_secrets.py`. The duplicate rows create two sources of truth. The change reads the homelab file into the existing dataclasses, removes the moved rows from product code, and keeps only the product rows in `cluster_secrets.py`. The readers load the file from the environment tree.

## What Changes
- Add a TOML loader using `tomllib` and a Pydantic `TypeAdapter` that reads `cluster-secrets.toml` into existing `ClusterSecret` dataclasses.
- Add `cluster_secrets` property to `EnvironmentTree` resolving `cluster-secrets.toml`.
- Update `push-secrets` and other readers to load environment rows from `cluster-secrets.toml` and append product rows.
- Remove moved environment Secret rows from `src/devops_cli/k8s/cluster_secrets.py`, leaving only product rows (`valkey-devops-auth`, `valkey-runs-auth`, and `devops` stack rows).
- Add fixture file `tests/fixtures/cluster-secrets.toml`.
- Add unit tests verifying loader behavior, removed stack rows, and environment tree push planning.

## Capabilities
- Read `cluster-secrets.toml` into existing frozen dataclasses for `ClusterSecret`, `SecretEntry`, `SecretGenerator`, and sources.
- Support `--k8s-dir` in `push-secrets` to read environment Secret definitions from an environment tree.

## Impact
- Eliminates duplicate secret definitions between devops-cli and homelab.
- Existing dataclass interfaces and CLI behaviors remain intact.

## Feasibility
Confirmed against repository code and tests: `EnvironmentTree` resolves environment paths, and existing dataclasses match the TOML schema.

## Existing Tool Considered
The alternatives check records `not-applicable` for a refactor with no search and `Tool: none found`. The change uses the existing pydantic `TypeAdapter` and standard library `tomllib`.
