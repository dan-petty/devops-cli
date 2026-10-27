# Design

## Architecture Overview

The LiteLLM AI gateway routes requests for virtual model groups to standardized Ollama backend tiers. The `qwen3.8:27b` and `devops-chat` groups previously routed requests across three tiers: `ollama-16gib-fast`, `ollama-48gib-fast`, and `ollama-64gib-standard`.

The deployment on `ollama-16gib-fast` used the quantized model `hf.co/ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF:IQ3_S`. This deployment fails on chat requests without a user query and oversubscribes the 16 GiB GPU memory. Removing this deployment leaves `ollama-48gib-fast` and `ollama-64gib-standard` to serve `qwen3.8:27b` and `devops-chat`. Both tiers provide sufficient VRAM to run `qwen3.8:27b` without CPU offloading.

## Rejected Alternatives

### 1. Reduce `max_input_tokens` on `ollama-16gib-fast`

Evidence that rejected it: the failures occurred on short requests with small prompt token counts. The chat template crashed because the messages contained no user message, not because the prompt was too long. Reducing `max_input_tokens` does not prevent chat template execution errors.

### 2. Modify the tier profile in `k8s/llm/profiles/`

Evidence that rejected it: physical GPU VRAM on `ollama-16gib` nodes is 16 GiB. Ollama calculates that Qwen 27B requires 20.7 GiB with the configured context size. Tuning context length cannot fit the model and its KV cache into 13.3 GiB of usable VRAM without severe CPU offloading. Changing the hardware profile cannot change physical GPU VRAM.

### 3. Keep the deployment in `devops-chat` but remove from `qwen3.8:27b`

Evidence that rejected it: `devops-chat` uses the same backend model and deployment. Any tool interaction request sent to `devops-chat` triggers the same chat template crash and high CPU latency. Removing the deployment from all groups eliminates the failure completely.
