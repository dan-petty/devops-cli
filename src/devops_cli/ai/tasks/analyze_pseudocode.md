Distill the key logic into concise symbolic pseudocode (4-10 lines):
- Focus on core entry points, method calls, decision branches, and state transformations.
- STRICTLY EXCLUDE imports and dependencies (`import`, `from ... import`, `require`, `#include`).
- Do not include explanatory prose or file names; use abbreviated symbols from the source.

EXAMPLE:
Source:
```python
def validate_token(token: str, secret: str) -> bool:
    if not token or len(token) < 32:
        return False
    return hmac.compare_digest(hash_token(token), secret)
```
Output:
```
validate_token(t, s) -> bool:
    if not t or len(t) < 32: r False
    r hmac.compare_digest(hash_t(t), s)
```
