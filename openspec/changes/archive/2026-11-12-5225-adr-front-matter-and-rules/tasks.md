# Tasks

## 1. The reader of the ADRs

- [x] 1.1 Write failing tests: an ADR keeps its front matter, a front matter that is not valid names the file, only an ADR in force reaches the check, and the entry names the amending ADRs
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives.py`
- [x] 1.2 Read the front matter in `src/devops_cli/roadmap/adr.py` with the `front_matter` plugin and `yaml.safe_load`, delete `_STATUS_VERB`, `_SUPERSEDED_BY` and `_SUPERSEDES`, and move mdit-py-plugins to the runtime dependencies
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_adr.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_project_facts.py`

## 2. The rules of the records

- [x] 2.1 Write failing tests: the body hash, the index, the synced block of the README and each problem of a record
  - Verification: `$ uv run devops ci test tests/docs/test_docs_adr_records.py tests/docs/test_docs_synced_blocks.py`
- [x] 2.2 Add `src/devops_cli/docs/adr_records.py` and the index block of `docs/adr/README.md` to `DocGenerator.synced_blocks`
  - Verification: `$ uv run devops ci test tests/docs/test_docs_adr_records.py tests/docs/test_docs_synced_blocks.py tests/docs/test_docs_inventory.py`

## 3. The records

- [x] 3.1 Give records 0001 to 0025 their front matter, move their notes and Status sections word for word into `## Status History`, add the dated lines, and mark ADR 0003 superseded by ADR 0017 and ADR 0021
  - Verification: `$ uv run devops ci test tests/invariants/test_adr_records.py`
- [x] 3.2 Write `docs/adr/README.md` with the rules, the template and the generated index, link it from `CONTRIBUTING.md`, and update `docs/roadmap/alternatives.md`
  - Verification: `$ uv run devops docs check`
- [x] 3.3 Give each status a title in `zensical.toml` and an icon in `overrides/main.html`
  - Verification: `$ uv run devops docs site build --strict`

## 4. The scope

- [x] 4.1 Declare the scope `adr` in `.github/labels.yml` and in the scopes of `.github/workflows/pr-title.yml`
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
