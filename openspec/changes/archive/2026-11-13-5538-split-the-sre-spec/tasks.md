# Tasks

## 1. The guideline test

Kind: documents. Changes: `tests/invariants/test_guidelines.py`, `docs/TESTING.md`.

- [x] 1.1 Add the guideline test of PR #5492, and run it on the text of `docs/SRE.md` and of the draft checklist, where it fails
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`

## 2. The guidelines

Kind: documents. Changes: `docs/guidelines/sre.md`, `docs/guidelines/production-readiness.md`, `docs/guidelines/index.md`.

- [x] 2.1 Move `docs/SRE.md` to the SRE guideline, and keep only its guideline parts
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`
- [x] 2.2 Add the production readiness guideline with the "Measured by" column and no state, and the index page
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`

## 3. The decisions of the cluster

Kind: documents. Changes: `k8s/catalog.toml`, `k8s/README.md`, `docs/CLUSTER.md`.

- [x] 3.1 Add the catalog data, the section "Service levels" with the link to tracker #5541, and the 4 rules for a live value change
  - Verification: `$ uv run devops ci test tests/invariants/test_agents_md.py`

## 4. Documents

Kind: documents. Changes: `.nav.yml`, `docs/index.md`, `docs/DESIGN.md`, `docs/SDLC.md`.

- [x] 4.1 Add the Guidelines tab, point the links at the guidelines, and apply the Renovate sentence
  - Verification: `$ uv run --group docs devops docs site build --strict`

## Workflow follow-up

- #5535 renders `k8s/catalog.toml` into `k8s/CATALOG.md`, and #5537 adds the readiness report.
- #4709 moves the SLO rows of "Service levels" into Sloth specs, and #5477 moves the value of incident trigger 1 into a setting.
- PR #5492 (#5444) and PR #5489 (#5443) add the Kubernetes and the agentic jobs guidelines, each with its line in the index.
