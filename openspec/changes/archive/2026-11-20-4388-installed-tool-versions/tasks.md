# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the doctor reads the installed kubectl; the analysis and the knowledge base read the recorded versions; a native tool records `unknown`; the profile hashes the runs; the rules lock refuses `semgrep_version`; the rules test prints the detected Semgrep version
  - Verification: `$ uv run devops ci test tests/k8s/test_k8s_doctor.py tests/review/test_review_group_analysis.py tests/review/test_kb_manuals_metadata.py tests/review/test_review_tool_binary_digest.py tests/ai/review/test_review_profile.py tests/commands/test_review_rules_pack.py`
- [x] 1.2 Read each version from the installed tool and drop the readers of `tools.lock`
  - Verification: `$ uv run devops ci test tests/core/test_binaries.py tests/commands/k8s/test_k8s.py tests/ai/test_tool_executor_contract.py tests/security/test_scanner_contract.py tests/security/test_security_kubeconform.py tests/roadmap/test_roadmap_alternatives_project_facts.py`
- [x] 1.3 Replay the OpenSpec scenarios with the installed tool
  - Verification: `$ uv run pytest tests/tools_lock/test_openspec_contract.py -m live`
- [x] 1.4 Run the rule pack with the installed Semgrep
  - Verification: `$ uv run devops review rules test --check`

## 2. Workflows and documents

- [x] 2.1 Add the Semgrep pin to the paths of `rule-pack.yml`
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`
- [x] 2.2 Update the profile, testing and alternatives documents, the prompts and the knowledge base
  - Verification: `$ uv run devops ci docs`
