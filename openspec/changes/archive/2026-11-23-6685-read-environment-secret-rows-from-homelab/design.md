# Design

## Decisions
- Use `tomllib.load` and Pydantic `TypeAdapter` over a file model to validate data and build existing frozen dataclasses.
- Re-use the existing dataclasses (`ClusterSecret`, `SecretEntry`, `SecretGenerator`, etc.) as the only row model.
- Resolve `cluster-secrets.toml` via `EnvironmentTree` using `--k8s-dir`, project profile facts, or `infra.repos`.
- Keep only product rows in `CLUSTER_SECRETS` in `cluster_secrets.py`.
- Append product rows to loaded environment rows when resolving the full cluster secrets table.

## Rejected alternatives
- Hand-written TOML parser: Adds bespoke parser logic and does not validate the file schema.
- Second row model: Duplicates dataclasses and creates two row models in product code.
- Hardcoded homelab path: Breaks custom environment trees and profile-based resolution.
