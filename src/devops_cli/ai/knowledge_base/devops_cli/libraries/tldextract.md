# Code Library: TLDExtract (Domain Parsing & Network Reference Extraction)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [github.com/john-kurkowski/tldextract](https://github.com/john-kurkowski/tldextract) |
| **Public Git Repository** | [github.com/john-kurkowski/tldextract](https://github.com/john-kurkowski/tldextract) |
| **Official PyPI Package** | [pypi.org/project/tldextract](https://pypi.org/project/tldextract/) (`5.3.2`) |
| **DevOps CLI Integration** | [`src/devops_cli/security/`](../../../../../../src/devops_cli/security/) • [`src/devops_cli/http/broker.py`](../../../../../../src/devops_cli/http/broker.py) |

---

## 2. General Information & Architecture

**TLDExtract** accurately separates the subdomain, domain, and public suffix of a URL using the Public Suffix List (PSL). Unlike naive string-split operations (`url.split(".")`), `tldextract` understands complex multi-part suffixes like `.co.uk`, `.github.io`, and `.org.au`.

In `devops-cli`:
- **Network Reference Extraction**: `security/reference_extractor.py` reports only hosts that the URL parser (`urllib.parse`) and `ipaddress` recognise, and uses a snapshot-only `TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)` for the public-suffix and RFC 2606 / special-use checks on those hosts; HTTP egress validation (`http/broker.py`) uses `ipaddress`-based checks.
- **Endpoint Classification**: Identifies internal homelab addresses versus public cloud endpoints.

---

## 3. Comparable Projects & Tradeoffs

| Parser | Strengths | Weaknesses | Why `devops-cli` Chose TLDExtract |
| :--- | :--- | :--- | :--- |
| **`tldextract`** | Uses official Public Suffix List, accurately handles multi-part suffixes (`.co.uk`), caches snapshot offline. | Requires cached PSL file. | **Selected**: The only reliable method to parse public suffixes without false positives. |
| **`urllib.parse`** (Stdlib) | Built into standard library. | Only extracts `netloc` (e.g. `foo.co.uk`), cannot distinguish domain from TLD or multi-part suffix. | Rejected: Naive splits cause security misclassifications. |
| **Custom Regex Splitters** | Zero dependencies. | High error rate on internationalized TLDs and multi-level cloud domains. | Rejected: Violates robust parser rules in `AGENTS.md`. |

---

## 4. Key Concepts & Core Patterns

1. **`tldextract.extract(url)`**: Returns an `ExtractResult(subdomain, domain, suffix)`.
2. **Offline Snapshot Caching**: Uses a snapshot-only configuration `TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)` to ensure offline execution without network roundtrips.

---

## 5. Common & Advanced Usage Examples

### Extracting Verified Network References
```python
import ipaddress
import urllib.parse
import tldextract

extractor = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)


def parse_and_validate_host(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname
    if not host:
        return None
    ext = extractor(host)
    return ext.registered_domain or host
```

---

## 6. Best Practices & Security Standards

1. **Use Offline Snapshot**: Instantiate `tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)` to avoid live downloads of the PSL during runtime.
2. **Combine with IP Validation**: Combine `tldextract` with standard library `ipaddress.ip_address(host).is_private` to ensure comprehensive loopback and private network coverage.
