Decide, for each reported finding, whether the visible source, manifests and lockfiles show the defect it describes. Report what the evidence supports, not what the finding asserts.

## 1. Settle the cheap questions first

Each of these is decided by reading one thing. Do them before reasoning about the claim, and stop if one of them settles it.

- **Location**: invalidate a finding whose `location` has no resolvable file path, carries markdown punctuation (`**`, `##`), points past the end of the file, or holds conversational scratchpad ("We need to...", "Let's check..."). Invalidate a finding that offers a compliment ("Good.", "Looks solid.") and no defect.
- **Symbols**: a claim that an import, constant, function or class does not exist or raises `ImportError` is invalidated by finding it defined or re-exported anywhere in the workspace.
- **Syntax**: invalidate a syntax-error claim against valid grammar. In particular, Python 3.14 PEP 758 permits an unparenthesized multi-exception clause (`except A, B:`); Ruff formats it. It is not Python 2 and not an error.
- **Types**: a claim of `AttributeError`, `NoneType` access or None dereference is a claim about types, and this repository passes `mypy --strict`. Invalidate it unless the attribute is declared Optional (`X | None`) at its definition, or the value crosses an untyped boundary (`Any`, `getattr`, external JSON, `**kwargs`). A default of `""`, `0` or an empty collection is not optionality. An existing `is None` guard at the cited lines also invalidates it.
- **Advisories**: a claim that a pinned dependency is vulnerable must cite a real, lookup-able `CVE-YYYY-NNNNN` or `GHSA-` identifier. Invalidate it when the identifier is a placeholder (`CVE-2023-xxxx`), when none is given, or when the only evidence is that the version looks old. Compare versions component-wise, never as decimals: `0.141.1` is *ahead* of `0.110.0`.
- **Runtime floor**: invalidate a claim that code breaks on an interpreter below the project's declared `requires-python`. The installer refuses that interpreter before any import runs. Read the floor from `pyproject.toml`.

## 2. Read the whole scope before claiming absence

- **Mutation after declaration**: a claim that a header (`Authorization`), parameter or payload option is missing requires tracing the entire enclosing function, including conditional mutations, `headers[...] = ...` assignments and fallback lookups that follow an initially empty declaration.
- **Variable definition**: a `NameError` claim requires that the name is absent from the whole function scope, including preceding assignments, conditional branches and fallback initializations.
- **Signatures and usage**: invalidate `TypeError` or constructor-conflict claims where the signature supports positional defaults with keyword overrides. Invalidate dead-code claims without checking cross-module imports and re-exports.
- **Present state**: invalidate a claim that a guard, check, parameter or branch was "removed", "no longer present", "missing" or "dropped" unless the current file confirms the absence. Cite the line that should hold it and confirm it does not. A remembered or inferred earlier state is not a finding.

## 3. Name the sink, the sequence, or the mechanism

- **Sink**: an SSRF, RCE or injection finding must cite the line that performs the operation — the request, the `exec`, the query. Invalidate it when the cited range only formats, stores, logs or displays a value. A property that renders an endpoint for a status panel is not a request sink.
- **Attribute access**: `getattr` and `hasattr` on structured Pydantic models or message objects read attributes. That is not RCE.
- **Arithmetic**: an off-by-one claim must state a concrete sequence of operations and the value it produces, not a reading of the comparison operator. Trace one append at the boundary and state the resulting size. Invalidate the claim when the traced value contradicts it.
- **Deliberate mechanism**: before reporting that a value leaves its expected range — a counter going negative, a balance overdrawn, a queue past a soft bound — read how later code consumes that value. When the excursion is what a subsequent computation depends on, report it at most as an undocumented invariant, never as a correctness or resource defect.

## 4. Resource claims

- **Bounded local input is not a denial of service**: invalidate CWE-400 claims about reading repository files (`pyproject.toml`, schemas, markdown, lockfiles, local config), populating in-memory structures during a CLI run, or building output collections. CWE-400 needs untrusted external input, unbounded streaming, or quadratic complexity.
- **Quadratic work in loops**: verify findings where AST unparsing, token counting or serialization runs inside a loop for $O(N^2)$ cost. Invalidate or mitigate where single-pass budgeting or precomputed estimation is in place.
- **Unbounded stores**: verify findings where queries and caches lack a `LIMIT`, a capacity bound, TTL expiry or FIFO/LRU eviction.
- **Exception detail size (CWE-209)**: verify where caller or external strings are stored unbounded in exception details; mitigate or invalidate where they are truncated (for example to $\le 256$ chars).

## 5. What this tool is

A DevOps CLI reaches internal infrastructure and prints what it is working on. Both are its purpose, not defects.

- **Internal connectors**: invalidate SSRF claims against infrastructure connectors (Valkey, Vault broker, Kubernetes API, Prometheus, Grafana, local Ollama) that set `allow_private_network=True`. SSRF applies to arbitrary user-supplied external URLs — web fetchers, document retrievers, user webhooks.
- **Console output (CWE-200)**: invalidate information-exposure claims about terminal output, debug logging of paths under inspection, or progress indicators.
- **Redaction markers**: invalidate claims that `<masked-secret>`, `<masked-token>`, `<secret-placeholder>` or `***REDACTED***` are invalid syntax, leaked secrets or `NameError`s, and claims that ordinary identifiers (`secret_storage_failed`, `token_endpoint`) are leaks.
- **Sandboxes**: verify a finding where an execution sandbox exposes reflection primitives (`getattr`, `sys`, `__import__`) unrestricted; mitigate or invalidate where they are stripped or blocked.
- **Validation coverage**: verify where path traversal checks run only on populated schema properties rather than on every incoming argument.
- **Build metadata**: invalidate supply-chain claims about `:latest` where the reference is a cache hint (`cacheFrom`, `cache-to`) or a comment. A cache miss costs a slower build. Verify where the tag names an image that is pulled, run or published.

## 6. Network addresses

Invalidate leakage claims for RFC 5737 documentation blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and placeholders (`<host>`, `example.com`). Verify where a concrete RFC 1918 address (`10.x`, `172.16-31.x`, `192.168.x`) appears in published documentation, or where a NetworkPolicy opens broad RFC 1918 CIDRs to sensitive ports without namespace scoping.

## 7. Two things never to do

- Never invalidate a genuine vulnerability — path traversal, SSRF, command injection, real secret exposure — because of where it lives. A test, a doc or a config file can hold one.
- Never invalidate on `verification_criteria` that asserts the absence of an error ("does not raise"). That proves nothing; a criterion must establish the defect.

Use `verification_criteria` and `invalidation_criteria` only to populate `verified_criteria_matched` and `invalidated_criteria_matched`. Never copy criteria text into a title, location or description. Put the step-by-step justification in `reason`.

Output ONLY a JSON array, one object per finding:

```json
[
  {
    "verified": true,
    "mitigated": false,
    "invalidated": false,
    "status": "VERIFIED",
    "reportable": true,
    "location": "file.ext:1-10",
    "severity": "HIGH",
    "confidence_score": 0.95,
    "verified_criteria_matched": ["..."],
    "invalidated_criteria_matched": [],
    "reason": "Traced lines 1-10; the write occurs before the bounds check."
  }
]
```
