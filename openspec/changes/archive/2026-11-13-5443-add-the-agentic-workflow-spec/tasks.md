# Tasks

## 1. The guideline test

Kind: documents. Changes: `tests/invariants/test_guidelines.py`, `docs/TESTING.md`.

- [x] 1.1 Add the guideline test of PR #5492 with no change, run it on the first draft, where it fails, and list it in `docs/TESTING.md`
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`

## 2. The agentic jobs guideline

Kind: documents. Changes: `docs/guidelines/agentic-jobs.md`, `docs/guidelines/index.md`, `docs/roadmap/job-success.md`, `.nav.yml`.

- [x] 2.1 Move the spec to `docs/guidelines/agentic-jobs.md`, keep only its guideline parts, move the method parts of `job-success.md` into it, and add P10 and AW-J7
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`
- [x] 2.2 Add the index page and the Guidelines tab
  - Verification: `$ uv run --group docs devops docs site build --strict`

## 3. The decisions of devops-cli

Kind: documents. Changes: `docs/ROADMAP_WORKFLOW.md`, `CONTEXT.md`, `src/devops_cli/roadmap/job_result.py`.

- [x] 3.1 Add the section "Agentic jobs in devops-cli" with the owner map and the link to tracker #5543, and point each link to the first draft at the guideline
  - Verification: `$ uv run devops ci test tests/invariants tests/docs`

## Workflow follow-up

- PR #5492 (#5444) adds the same index, tab and test. The second of the two pull requests to merge rebases and keeps both lines of the index.
- #5536 adds the AGENTS.md route to the guideline index.
- #5538 adds the SRE and production readiness guidelines, each with its line in the index.
- #5534 generates the result line contract of `job-success.md` and the bounds of each setting.
