Review and remediate the following Python HTTP webhook dispatcher against Server-Side Request Forgery (SSRF) and DNS rebinding attacks.

```python
import httpx

def dispatch_webhook(url: str, payload: dict) -> int:
    # Sends a webhook notification
    with httpx.Client() as client:
        resp = client.post(url, json=payload, timeout=10.0)
        return resp.status_code
```

Provide the complete hardened Python 3.14+ implementation using `httpx` or standard library `ipaddress`/`urllib.parse`.
