# Code Library: Tiktoken (BPE Tokenizer & Context Window Budgeting)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/openai/tiktoken](https://github.com/openai/tiktoken) |
| **Public Git Repository** | [github.com/openai/tiktoken](https://github.com/openai/tiktoken) |
| **Official PyPI Package** | [pypi.org/project/tiktoken](https://pypi.org/project/tiktoken/) (`0.14.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/context_budget.py`](file:///workspaces/devops-cli/src/devops_cli/ai/context_budget.py) • [`src/devops_cli/commands/ai.py`](file:///workspaces/devops-cli/src/devops_cli/commands/ai.py) |

---

## 2. General Information & Architecture

**Tiktoken** is a fast Byte-Pair Encoding (BPE) tokenizer developed in Rust by OpenAI. It converts raw text strings into discrete integer token sequences and measures exact token lengths for LLM context window budgeting.

In `devops-cli`:
- **Context Budgeting**: `devops_cli.ai.context_budget` calculates token budgets for diffs, file trees, and prompts before sending them to LLM endpoints.
- **Cost Estimation**: Estimates LLM operational inference costs based on token counts across different model classes (`gpt-4o`, `claude-3-5-sonnet`, `deepseek-r1`).
- **CLI Commands**: Powers `devops ai tokens <target>` to calculate tokens for files or arbitrary strings.

---

## 3. Comparable Projects & Tradeoffs

| Tokenizer | Strengths | Weaknesses | Why `devops-cli` Chose Tiktoken |
| :--- | :--- | :--- | :--- |
| **`tiktoken`** | 3–6x faster than standard Python tokenizers (Rust core), exact BPE counts for OpenAI/Claude-compatible encodings (`cl100k_base`, `o200k_base`). | Focused on OpenAI BPE vocabulary. | **Selected**: The fastest, most robust tokenizer for developer context budgeting. |
| **`transformers` (HuggingFace)** | Supports hundreds of open-source model tokenizers (Llama, Mistral, BERT). | Massive dependency footprint (PyTorch/TensorFlow, Rust/C++ binaries, multi-GB downloads). | Rejected: Far too heavy for a fast, responsive CLI tool. |
| **Character/Word Heuristics (`len(text)/4`)** | Zero dependencies, instant calculation. | Inaccurate (errors of 20%–50% on code diffs, indentation, and unicode symbols), risks context overflows. | Rejected: Code reviews require exact budget bounds. |

---

## 4. Key Concepts & Core Patterns

1. **Encoding Schemes**:
   - `cl100k_base`: Standard encoding for GPT-4, GPT-3.5, and Claude approximations.
   - `o200k_base`: Next-generation encoding for GPT-4o models.
2. **`encoding.encode(text)`**: Converts text string to `list[int]` token IDs.
3. **`encoding.decode(tokens)`**: Reconstructs text string from token IDs.
4. **Cached Encoders**: `get_encoding("cl100k_base")` caches the BPE vocabulary table in memory for sub-millisecond lookups.

---

## 5. Common & Advanced Usage Examples

### Accurate Token Counting in DevOps CLI
```python
import tiktoken


def count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Calculate exact token count for prompt text."""
    try:
        enc = tiktoken.get_encoding(encoding_name)
    except ValueError:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(text))


diff_tokens = count_tokens("git diff output ...")
print(f"Total prompt tokens: {diff_tokens}")
```

### Truncating Context to Budget Limit
```python
def truncate_to_token_budget(text: str, max_tokens: int, encoding_name: str = "cl100k_base") -> str:
    enc = tiktoken.get_encoding(encoding_name)
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens]) + "\n... [truncated by context budget]"
```

---

## 6. Best Practices & Security Standards

1. **Defensive Encoding Fallback**: Always fall back to `cl100k_base` if an unknown model name is supplied.
2. **Zero Inlined Weights**: Use standard public encodings without bundling heavy proprietary vocabulary weights into Git.
3. **Memory Efficiency**: Avoid caching millions of decoded string tokens in memory simultaneously; stream chunk counts when analyzing massive multi-gigabyte repositories.
