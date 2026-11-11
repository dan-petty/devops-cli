# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: the package declares each written label, the file holds no workflow label, a file label keeps the package spec, the colors, and onboard row 4 lists `status/planned`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py tests/roadmap/test_roadmap_onboard.py`
- [x] 1.2 Add `roadmap/workflow_labels.py`, merge it in `declared_label_specs`, read the types from it in intake and the evaluation, and compare it in onboard row 4 and `devops gh labels sync`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py tests/roadmap/test_roadmap_onboard.py tests/roadmap/intake/test_roadmap_intake_labels_file.py`
- [x] 1.3 Remove the workflow labels and the `review/*` labels from `.github/labels.yml`, and give the rest the gray token colors
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_labels_file.py tests/invariants/test_workflow_contracts.py tests/commands/test_pr_title_labels.py`

## 2. Documents

- [x] 2.1 Update the onboard, intake, inbox and workflow pages, CONTRIBUTING.md, SDLC.md and the knowledge base
  - Verification: `$ uv run devops ci docs`
