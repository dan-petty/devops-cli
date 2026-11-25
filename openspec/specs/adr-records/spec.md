# adr-records Specification

## Purpose
The citation rule of the ADR process: code, tests and workflows name the record in force, and a test fails on a citation of a superseded record outside the history.

## Requirements

### Requirement: Code, tests and workflows cite the record in force
A test SHALL read the status from the front matter of each `docs/adr/*.md` and SHALL fail on an `ADR <number>` citation in `src/`, `tests/` or `.github/` whose record is superseded. Archived change folders, `CHANGELOG.md` and `docs/adr/` SHALL stay out of the scan.

#### Scenario: A citation of a superseded record
- **WHEN** a source file cites `ADR 0003`, which is superseded
- **THEN** the test fails and names the file and the line

#### Scenario: The history
- **WHEN** a file under `openspec/changes/archive/`, `CHANGELOG.md` or `docs/adr/` cites a superseded record
- **THEN** the test passes

#### Scenario: A citation of a record in force
- **WHEN** a file cites `ADR 0021`
- **THEN** the test passes

### Requirement: ADR records the five owner decisions with dates, limits, and stable anchors

`docs/adr/0038-owner-decisions-on-what-agents-may-do.md` SHALL use MADR 4 format (`status: accepted`, `decision-makers: [owner]`, `issue: 4787`, matching `body-hash`), list Decisions 1 through 5 under `### Decision 1` through `### Decision 5` headings inside `## Decision Outcome` with each decision's date and limit, and reference the `'Only a person'` paragraph of `AGENTS.md` without copying its list.

#### Scenario: ADR invariants and index validate

- **WHEN** `uv run devops ci test tests/invariants/test_adr_records.py` and `uv run devops docs check` run
- **THEN** both exit 0 and `docs/adr/README.md` indexes ADR `0038`

### Requirement: k8s README states Decision 1

The `Agent sessions` section of `k8s/README.md` SHALL state that agents apply manifests, restart workloads, and exercise workloads in the lab cluster, and SHALL describe `k8s/agents/` as one read-only identity rather than the limit of agent access.

#### Scenario: Agent sessions section agrees with ADR 0038 Decision 1

- **WHEN** a reader opens the `Agent sessions` section of `k8s/README.md`
- **THEN** it states the three permitted lab-cluster actions and does not present read-only access as the overall limit

### Requirement: Pin policy ADR
The change SHALL record in `docs/adr/` an accepted ADR amending ADR `0013` (`issue: 5135`, `tracker: 5120`, `amends: ["0013"]`) stating that all four refs track `main` until the cutover (`#5134`), one Renovate group in `dan-petty/homelab` pins the devops `targetRevision`, prometheus `values` ref, dashboards ref, and image tags to one release tag after the cutover (`#6582`), and Image Updater keeps its `argocd` digest write-back with no `writeBackConfig`.

#### Scenario: ADR invariants and index pass
- **WHEN** `uv run devops ci test tests/invariants/test_adr_records.py` and `uv run devops docs check` run
- **THEN** both pass with ADR `0013`'s `body-hash` unchanged, `amended-by` naming the new record, one dated `Status History` line added to ADR `0013`, and the new record listed in `docs/adr/README.md`

#### Scenario: Image Updater values retain digest write-back
- **WHEN** `uv run devops ci --check --only k8s` runs
- **THEN** the check passes and `ImageUpdater` `devops` in `k8s/argocd/image-updater-values.yaml` retains `updateStrategy: digest` and no `writeBackConfig`
