# Knowledge Base: tiktoken (Fast BPE Tokenizer & Context Budgeting)

## 1. Overview & Purpose

`tiktoken` is a fast Byte Pair Encoding (BPE) tokenizer by OpenAI designed for client-side token counting, prompt sizing, and context window budgeting. In `devops-cli`, `tiktoken` powers the context budgeting engine (`devops_cli.ai.context_budget`), enabling sub-millisecond token counting, diff hunk partitioning, and context window truncation prior to LLM dispatch across local Ollama and remote AI providers.

---

## 2. Usage Information & Architecture

- **Local BPE Encoding**: Encodes text to tokens locally without making network calls or incurring API latency.
- **Diff Chunk Budgeting**: Automatically calculates diff sizes and partitions oversized multi-file git diffs into cohesive token-budgeted chunks (`budget_diff_chunks`).
- **Context Truncation**: Truncates prompts and file outlines to fit strictly within model context limits (`truncate_to_token_limit`).
- **CLI Subcommand**: Exposes `devops ai token-count` for interactive and CI verification of prompt budgets.

---

## 3. Common & Advanced Commands

### DevOps CLI Token Budgeting
```bash
# Calculate token count for a specific file
devops ai token-count src/devops_cli/main.py

# Calculate token count with custom budget and JSON report
devops ai token-count src/devops_cli/commands/review.py --budget 8192 --json

# Estimate tokens for a raw text string
devops ai token-count "Evaluate security boundaries and network references"
```

### Python SDK Integration
```python
from devops_cli.ai.context_budget import count_tokens, budget_diff_chunks, truncate_to_token_limit

# Count tokens using gpt-4o BPE encoding
n_tokens = count_tokens("def hello(): pass", model="gpt-4o")

# Partition diff into 8k token chunks
chunks = budget_diff_chunks(git_diff_text, max_tokens=8192)
```

---

## 4. Best Practice Guidance

1. **Pre-Calculate Before Dispatch**: Always calculate token counts before sending prompts to avoid 400 Context Window Exceeded errors from LLM backends.
2. **Hunk-Boundary Partitioning**: When splitting diffs, split along file and hunk boundaries (`@@ -... @@`) rather than arbitrary string slices to preserve syntax context.
3. **Model Encoding Selection**: Use `cl100k_base` or `o200k_base` encodings for modern code and chat reasoning models.

---

## 5. Official References & Published Artifacts

- **Project Homepage**: [github.com/openai/tiktoken](https://github.com/openai/tiktoken)
- **Official PyPI Package**: [pypi.org/project/tiktoken](https://pypi.org/project/tiktoken/)
- **DevOps CLI Context Budget**: [src/devops_cli/ai/context_budget.py](../../../../ai/context_budget.py)
