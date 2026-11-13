# Tasks

## 1. The guideline test

Kind: documents. Changes: `tests/invariants/test_guidelines.py`, `docs/TESTING.md`, `tests/docs/test_k8s_performance_spec.py` (deleted).

- [x] 1.1 Write the guideline test, and run it on the text of the first draft, where it fails
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`
- [x] 1.2 Delete the test of the measured rows, and list the new test in `docs/TESTING.md`
  - Verification: `$ uv run devops ci test tests/invariants/test_source_tree.py`

## 2. The Kubernetes guideline and the decisions

Kind: documents. Changes: `docs/guidelines/kubernetes.md`, `docs/guidelines/index.md`, `k8s/README.md`.

- [x] 2.1 Move the spec to `docs/guidelines/kubernetes.md`, keep only its guideline parts, give each target its measure, and add the probe and batch Job rules
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`
- [x] 2.2 Add the index page and the section "Capacity targets" of `k8s/README.md`, with the link to tracker #5542 and no gap row
  - Verification: `$ uv run devops ci test tests/invariants/test_guidelines.py`

## 3. Documents

Kind: documents. Changes: `docs/index.md`, `docs/CLUSTER.md`, `docs/guidelines/sre.md`, `CONTEXT.md`.

- [x] 3.1 Add the Guidelines tab and the index line, point the links at the guideline, and add the terms "Managed project" and "Guideline"
  - Verification: `$ uv run --group docs devops docs site build --strict`

## Workflow follow-up

- #5536 adds the AGENTS.md route to the guideline index.
- #5489 (#5443) adds the agentic jobs guideline, and #5538 adds the SRE and production readiness guidelines, each with its line in the index.
