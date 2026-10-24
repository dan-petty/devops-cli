# Tasks

## 1. Failing tests for C++ and Helm template language detection

- [ ] 1.1 Write failing table tests for C++, .h headers, Helm .tpl templates, Dockerfiles, and YAML with an empty mimetypes database in tests/test_analyze.py (`uv run pytest tests/test_analyze.py -k test_detect_language_table`)
- [ ] 1.2 Write failing sample validation test asserting no mislabelled files for C/C++ and Kubernetes/Helm in tests/test_review_sample_validation.py (`uv run pytest tests/test_review_sample_validation.py -k test_sample_validation_categories_have_no_mislabelled_files`)

## 2. Implementation of C++ and Helm template classification

- [ ] 2.1 Implement C++ extension mapping, header content inspection, and Helm template chart traversal in src/devops_cli/ai/analyze/scanner.py (`uv run pytest tests/test_analyze.py -k test_detect_language`)
- [ ] 2.2 Wire repo_root into file outline analysis in src/devops_cli/ai/analyze/outlines.py and sample file inspection in src/devops_cli/ai/review/sample_validation.py (`uv run pytest tests/test_review_sample_validation.py`)
- [ ] 2.3 Synchronize CLI documentation (`uv run devops docs generate --sync-readme`)

## 3. Verification and CI gates

- [ ] 3.1 Verify complete CI quality gates pass (`uv run devops ci`)

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
