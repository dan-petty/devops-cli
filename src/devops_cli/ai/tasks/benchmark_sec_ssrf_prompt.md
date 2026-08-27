Review and remediate the following Python HTTP webhook dispatcher against Server-Side Request Forgery (SSRF) and DNS rebinding attacks using a step-by-step chain-of-thought security analysis:

### Vulnerable Implementation:
```python
import httpx


def dispatch_webhook(url: str, payload: dict) -> int:
    # Sends a webhook notification
    with httpx.Client() as client:
        resp = client.post(url, json=payload, timeout=10.0)
        return resp.status_code
```

### Remediation Steps:
1. **Analyze SSRF Vectors**: Identify risks associated with unvalidated URL schemes, private IP spaces (RFC 1918), loopback (`127.0.0.0/8`, `::1`), link-local (`169.254.0.0/16`), and DNS rebinding.
2. **Implement Pre-Flight IP & Scheme Validation**: Parse URL using `urllib.parse.urlparse`, resolve hostname to IP addresses via `socket.getaddrinfo`, and validate each IP using `ipaddress.ip_address` (`is_private`, `is_loopback`, `is_link_local`, `is_multicast`).
3. **Pin Connection Destination**: Ensure requests connect strictly to validated IP addresses or employ custom transport/pinning to prevent TOCTOU DNS rebinding.
4. **Output Complete Implementation**: Provide the complete hardened, strictly typed Python 3.14+ implementation with defensive timeout and error handling.
