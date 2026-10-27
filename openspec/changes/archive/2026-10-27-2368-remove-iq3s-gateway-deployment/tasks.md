# Tasks

## 1. Remove IQ3_S Gateway Deployment

- [x] Add failing test in `tests/test_k8s_llm_gateway.py` asserting `qwen3.8:27b` and `devops-chat` exclude `ollama-16gib-fast`
  - Verification: `uv run pytest tests/test_k8s_llm_gateway.py -k test_qwen_and_chat_groups_exclude_16gib_tier`
- [x] Remove `hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S` from `devops-chat` and `qwen3.8:27b` in `k8s/llm/gateway/config.yaml`
  - Verification: `uv run pytest tests/test_k8s_llm_gateway.py`
- [x] Update gateway test expectations and negative controls in `tests/test_k8s_llm_gateway.py`
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Update example snippet in `k8s/llm/profiles/README.md` and regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`
- [x] Run full CI checks
  - Verification: `uv run devops ci`
- [x] Archive OpenSpec change
  - Verification: `uv run devops openspec archive 2368-remove-iq3s-gateway-deployment`
