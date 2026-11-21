# Tasks

## 1. Record the four homes

Reads: `docs/adr/0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md`, `docs/adr/0013-releases-use-release-please-as-it-ships-and-agents-stay-out.md`, `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`, `docs/adr/README.md`, `.github/workflows/release.yml`, `k8s/devops/renovate/`.

Changes: `docs/adr/0032-infrastructure-templates-live-in-four-homes.md` (new), `docs/adr/README.md`.

- [ ] 1.1 Write ADR 0032 with the four homes, the placement rule, the release-tag pins and Renovate, the shared CI in infra, the private-data rule of infra, the onboarding with one services entry, the sequence with #5134, and the amendments of ADR 0011, ADR 0026 and ADR 0027
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [ ] 1.2 Mark the two open owner choices, the App that tags infra and the home of the root stacks of ADR 0026, with the recommendation as the decision text
  - Verification: `$ grep -c "Open choice: the owner confirms it in the review" docs/adr/0032-infrastructure-templates-live-in-four-homes.md`
- [ ] 1.3 Regenerate the index of `docs/adr/README.md`
  - Verification: `$ uv run devops ci --check --only docs,domain`

## 2. Amend the older records

Changes: `docs/adr/0011-releases-come-from-trunk-towncrier-uv-and-semver-tags-instead-of-a-bespoke-cut.md`, `docs/adr/0026-github-settings-are-opentofu-code-the-owner-applies.md`, `docs/adr/0027-dependency-updates-come-from-self-hosted-renovate.md`.

- [ ] 2.1 Add `amended-by: ["0032"]` and a dated `Amended by ADR 0032` line to ADR 0026 and ADR 0027
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [ ] 2.2 Add a dated `Fact out of date` line that names ADR 0032 to ADR 0011, with no amendment key
  - Verification: `$ grep -l 0032 docs/adr/0011-*.md docs/adr/0026-*.md docs/adr/0027-*.md`

## Criteria

- Group 1: `ls docs/adr/0032-*.md` SHALL find one file, and `grep -c 0032 docs/adr/README.md` SHALL print 1 or more.
- Group 1: The record SHALL hold no real domain, host or node name, private address, device path or token value.
- Group 2: `grep -l 0032 docs/adr/0011-*.md docs/adr/0026-*.md docs/adr/0027-*.md` SHALL list the 3 files.
- Group 2: The accepted body of ADR 0026 SHALL keep its `body-hash`.

## Workflow follow-up

- The items of the plan build the decision: dan-petty/infra#4, dan-petty/infra#5, dan-petty/infra#6, #6676, #6677, dan-petty/homelab#74 and dan-petty/danielpetty.com#39.
- Pending a person: confirm the App that tags infra, and the home of the root stacks of ADR 0026, in the review.
