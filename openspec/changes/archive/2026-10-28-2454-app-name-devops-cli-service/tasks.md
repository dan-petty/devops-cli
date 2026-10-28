# Tasks

## 1. Documents

- [x] Name the App `devops-cli-service` in ADR 0015, `k8s/README.md`, `k8s/devops/configmap.example.yaml` and the two knowledge-base entries; add the amendment line, the needed permissions, the owner's grant and its risk to ADR 0015; state what the Service waits on in the "Roadmap service" note
  - Verification: `git grep -n "devops-roadmap\b" -- docs/adr k8s src/devops_cli/ai/knowledge_base`
- [x] Run the checks that read these files
  - Verification: `uv run devops ci test tests/test_k8s_configmap.py tests/test_k8s.py && uv run devops docs check && uv run devops openspec check`

## 2. Archive

- [x] Archive the change
  - Verification: `uv run devops openspec archive 2454-app-name-devops-cli-service`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
