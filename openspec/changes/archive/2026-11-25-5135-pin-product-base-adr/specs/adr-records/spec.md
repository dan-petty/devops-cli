## ADDED Requirements

### Requirement: Pin policy ADR
The change SHALL record in `docs/adr/` an accepted ADR amending ADR `0013` (`issue: 5135`, `tracker: 5120`, `amends: ["0013"]`) stating that all four refs track `main` until the cutover (`#5134`), one Renovate group in `dan-petty/homelab` pins the devops `targetRevision`, prometheus `values` ref, dashboards ref, and image tags to one release tag after the cutover (`#6582`), and Image Updater keeps its `argocd` digest write-back with no `writeBackConfig`.

#### Scenario: ADR invariants and index pass
- **WHEN** `uv run devops ci test tests/invariants/test_adr_records.py` and `uv run devops docs check` run
- **THEN** both pass with ADR `0013`'s `body-hash` unchanged, `amended-by` naming the new record, one dated `Status History` line added to ADR `0013`, and the new record listed in `docs/adr/README.md`

#### Scenario: Image Updater values retain digest write-back
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the check passes and `ImageUpdater` `devops` in `k8s/argocd/image-updater-values.yaml` retains `updateStrategy: digest` and no `writeBackConfig`
