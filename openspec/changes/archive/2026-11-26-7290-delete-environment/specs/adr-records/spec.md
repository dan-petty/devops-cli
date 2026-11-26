## ADDED Requirements

### Requirement: The pin policy ADR amends ADR 0013
The change SHALL record in `docs/adr/` an accepted ADR amending ADR `0013` (`issue: 5135`, `tracker: 5120`, `amends: ["0013"]`) stating that all four refs track `main` until the cutover (`#5134`), one Renovate group in `dan-petty/homelab` pins the devops `targetRevision`, prometheus `values` ref, dashboards ref, and image tags to one release tag after the cutover (`#6582`), and Image Updater keeps its `argocd` digest write-back with no `writeBackConfig`.

#### Scenario: ADR invariants and index pass
- **WHEN** `uv run devops ci test tests/invariants/test_adr_records.py` and `uv run devops docs check` run
- **THEN** both pass with ADR `0013`'s `body-hash` unchanged, `amended-by` naming the new record, one dated `Status History` line added to ADR `0013`, and the new record listed in `docs/adr/README.md`

## MODIFIED Requirements

### Requirement: k8s README states Decision 1

The `Agent sessions` section of `k8s/README.md` SHALL state that agents apply manifests, restart workloads, and exercise workloads in the lab cluster, and SHALL describe `agents/` of the environment tree as one read-only identity rather than the limit of agent access.

#### Scenario: Agent sessions section agrees with ADR 0038 Decision 1

- **WHEN** a reader opens the `Agent sessions` section of `k8s/README.md`
- **THEN** it states the three permitted lab-cluster actions and does not present read-only access as the overall limit

## REMOVED Requirements

### Requirement: Pin policy ADR
**Reason**: A scenario of it read the Image Updater values of the environment (#7290).
**Migration**: See `The pin policy ADR amends ADR 0013`.
