# Proposal

## Why

The owner gave the end state of the infrastructure on 2026-11-21: devops-cli keeps the templates of its own deployment, each service repository keeps the templates of its own stack, dan-petty/infra keeps the shared templates and the general settings, and dan-petty/homelab keeps each sensitive value and the configuration of the homelab nodes and cluster. No decision record holds this rule, so agents planned the rows of one site in this repository (#6642 to #6649). ADR 0026 puts a shared module and two root stacks that name private repositories here, ADR 0027 puts the Renovate of every repository in `k8s/devops`, and ADR 0011 point 3 gives the release App to this repository only (#6674).

## What Changes

- A new architecture decision record, `docs/adr/0032-infrastructure-templates-live-in-four-homes.md`, that records the four homes, the placement rule, the release-tag pins and Renovate, the shared CI in infra, the private-data rule of the public infra repository, the onboarding of a service repository with one services entry, and the sequence with #5134.
- The record keeps two owner choices open, with the recommendation as the decision text and a marker that the owner confirms each one in the review: the App that tags infra, and the home of the root stacks of ADR 0026.
- ADR 0026 and ADR 0027 get `amended-by: ["0032"]` and a dated `Status History` line. ADR 0011 is superseded, so it gets no amendment key: it gets a dated `Fact out of date` line that names ADR 0032.
- The index of `docs/adr/README.md` gains the row of the record and the new links of ADR 0026 and ADR 0027.
- The change writes no code and alters no behavior a consumer observes, so it carries no spec delta and sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. The record is documentation, so the change carries no spec delta.

## Impact

- Documents: `docs/adr/0032-infrastructure-templates-live-in-four-homes.md` (new), `docs/adr/0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md`, `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, `docs/adr/README.md`

## Feasibility

- The premise holds at main 4ff4b7c5d. The last record is ADR 0031. ADR 0026 decision 1 names `tf/github/modules/repository` and the root stacks `tf/github/dan-petty` and `tf/github/retric-ai`, and `tf/github/` does not exist yet. ADR 0027 puts the CronJob in `k8s/devops/renovate/`. ADR 0011 point 3 is at line 89, and `.github/workflows/release.yml:33` sets `environment: release`.
- dan-petty/infra is public, MIT, with the default branch `main`, and holds only `.github` and `LICENSE` (infra PR #2 onboarded it).
- The Argo CD page `docs/user-guide/best_practices.md:71` says that a remote base at HEAD "can suddenly change meaning", and line 74 recommends a Git tag or a commit SHA.
- Renovate extracts each of the five pin forms: the `kustomize` manager reads remote resources and components, the `argocd` manager reads `targetRevision`, the `ansible-galaxy` manager reads git collections with the `git-tags` datasource, the `terraform` manager reads git module sources, and the `github-actions` manager reads reusable workflows (`renovatebot/renovate` `lib/modules/manager/`).
- The upstream chart repository `renovatebot/helm-charts` has the license AGPL-3.0, so the move of ADR 0027 to the chart widens its license exception. The record says so.
- ADR 0011 is superseded, and `docs/adr/README.md` says "Do not amend a superseded record". A dated line at the end of its `Status History` is an allowed change, so the record gets a `Fact out of date` line and no `amended-by` key.
- The form rules are those of `docs/adr/README.md`, checked by `tests/invariants/test_adr_records.py`, and `uv run devops docs generate` writes the index.

## Existing Tool Considered

The record needs no tool: MADR 4 is the form, and the repository already holds the records and their check (`src/devops_cli/docs/adr_records.py`). The decision itself uses open tools only: release-please for the tags, Renovate for the pins and the presets, GitHub reusable workflows for the shared CI, Kustomize remote bases, Argo CD multi-source `ref` sources, Ansible collections from git and OpenTofu git sources. The written cost is about 6,000 tokens and about 1 hour.

## Dependencies

- ADR 0011, ADR 0026 and ADR 0027, in `docs/adr/`, done.
- dan-petty/infra exists and is onboarded (infra PR #2), done.
- Owner direction of 2026-11-21: the four homes, and each GitHub App of the account is installed on every dan-petty repository.
