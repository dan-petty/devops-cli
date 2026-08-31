# Code Library: JSON Repair (Resilient LLM Payload Recovery)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/mangiucugna/json_repair](https://github.com/mangiucugna/json_repair) |
| **Public Git Repository** | [github.com/mangiucugna/json_repair](https://github.com/mangiucugna/json_repair) |
| **Official PyPI Package** | [pypi.org/project/json-repair](https://pypi.org/project/json-repair/) (`0.63.4`) |
| **DevOps CLI Integration** | [`src/devops_cli/ai/review/runner.py`](file:///workspaces/devops-cli/src/devops_cli/ai/review/runner.py) • [`src/devops_cli/ai/agents/`](file:///workspaces/devops-cli/src/devops_cli/ai/agents/) |

---

## 2. General Information & Architecture

**JSON Repair** is a lightweight Python module that fixes invalid, unclosed, or truncated JSON emitted by Large Language Models. When LLMs generate JSON payloads, output length limits or abrupt network disconnections frequently result in trailing unclosed quotes (`"`), unclosed brackets (`]`, `}`), missing keys, or trailing commas. `json-repair` analyzes the token stream and synthesizes a well-formed JSON string or dictionary.

In `devops-cli`:
- **AI Review Parsing**: Parses structured JSON finding outputs from multi-persona code review passes without failing when the LLM response is truncated.
- **Agent Output Normalization**: Normalizes tool parameters received from remote MCP agents.

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose JSON Repair |
| :--- | :--- | :--- | :--- |
| **`json-repair`** | Lightning-fast token-based repairing, repairs unclosed brackets, missing quotes, single quotes, trailing commas, returns dict or valid JSON string. | Focused strictly on JSON format repair. | **Selected**: Zero dependencies, extremely resilient against real-world LLM truncation artifacts. |
| **`json`** (Stdlib) | Built into standard library. | Fails immediately on any syntax error with `json.decoder.JSONDecodeError`, zero repair capability. | Rejected: Causes review pipeline crashes on truncated model streams. |
| **Regex String Slicers** | Ad-hoc string manipulation. | Brittle, fails on nested structures, introduces arbitrary data corruption. | Rejected: Violates the zero-boilerplate and robust parser standards in `AGENTS.md`. |
| **`dirtyjson`** | Lenient JSON parser. | Unmaintained, does not handle truncated LLM streams cleanly. | Rejected: Slower and less reliable than `json-repair`. |

---

## 4. Key Concepts & Core Patterns

1. **`repair_json(bad_json_string)`**: Parses and repairs malformed JSON, returning a valid JSON string.
2. **`loads(bad_json_string)`**: Parses and repairs malformed JSON, returning the decoded Python object (`dict`, `list`).
3. **Resilience Heuristics**:
   - Closes open string literals.
   - Balances missing closing brackets `}` and `]`.
   - Converts single-quoted strings and Javascript-style unquoted keys into valid JSON keys.

---

## 5. Common & Advanced Usage Examples

### Repairing Truncated LLM JSON Payloads
```python
import json_repair

# Malformed payload truncated mid-stream by token limit
truncated_output = '{"findings": [{"id": "SEC-01", "title": "Missing TLS cert'

# Automatically repair and parse into a valid dictionary
parsed_data = json_repair.loads(truncated_output)
assert isinstance(parsed_data, dict)
assert "findings" in parsed_data
assert parsed_data["findings"][0]["id"] == "SEC-01"
```

### Defensive Review Parser Pipeline
```python
from devops_cli.ai.review_schema import Finding


def parse_llm_findings(raw_response: str) -> list[Finding]:
    parsed = json_repair.loads(raw_response)
    if isinstance(parsed, list):
        items = parsed
    elif isinstance(parsed, dict):
        items = parsed.get("findings", [])
    else:
        items = []

    return [Finding.model_validate(item) for item in items if isinstance(item, dict)]
```

---

## 6. Best Practices & Security Standards

1. **Always Validate Repaired Payloads with Pydantic**: `json-repair` guarantees syntactical JSON validity, but Pydantic schemas are still required to validate semantic field types.
2. **Handle Empty Decodes Cleanly**: Return empty lists/dictionaries rather than raising unhandled exceptions when incoming responses contain zero valid tokens.
