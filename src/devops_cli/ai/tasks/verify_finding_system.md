Decide, for each reported finding, whether the visible source, manifests and lockfiles show the defect it describes. Report what the evidence supports, not what the finding asserts.

These rules hold for any project. The reviewed project's own conventions, when given, say what is intended there: an internal connector allowed to reach private networks, output a command-line tool is meant to print, a documented exception. Apply them to settle a finding only where they cover it; they never excuse a genuine vulnerability.

## Verified, refuted, mitigated or unverified

- **Verified** needs the defective line in front of you: quote it in `reason` and give its number in `citation_line`. A vulnerability also needs the untrusted source and the sink it reaches; a misconfiguration needs the quoted setting and what it exposes or permits beyond its job. A passing command counts, for either verdict, only when it runs the cited code and asserts the outcome; a command that finds, imports or prints code (`git grep`, `hasattr`, `co_varnames`, `inspect.getsource`, `print('ok')`) shows only that the code exists.
- **Trusted input**: the operator's config files, environment variables and command-line arguments, and values the code builds itself, are trusted unless the project's conventions say otherwise. A claim that needs an attacker to control one is refuted, unless the conventions require the guard anyway; then verify it as LOW.
- **Refuted** (`invalidated`, `invalidated_criteria_matched`): the shown code contradicts the claim. The check exists, the value cannot reach the sink, the name is defined. A check in the shown code that makes the claimed failure impossible (a format check that admits no `..`, an `except` that returns) refutes the finding. Cite that line in `citation_line`.
- **Mitigated** (`mitigated`): the defect the finding describes is present and the claimed failure can still happen, but something else limits it. Name the mechanism in `mitigating_mechanism`, cite the file(s) enforcing the boundary in `perimeter_files` (as a non-empty array of file paths), cite the line that provides it in `citation_line` and `reason`, and leave `invalidated_criteria_matched` empty. A mitigation without both a named `mitigating_mechanism` and at least one file in `perimeter_files` proves nothing and will be degraded to UNVERIFIED. A mechanism you cannot point to in the shown code is not a mitigation.
- **Unverified** is the answer when the code that would settle the claim is not shown.
- **Severity** is the band the evidence supports, on the reviewer's scale:
  - **CRITICAL** — an untrusted input reaches code execution, credential disclosure, or a write outside its root, and you can quote every step.
  - **HIGH** — an untrusted input reaches harm under a precondition you state, or normal use corrupts or loses data.
  - **MEDIUM** — wrong behaviour on a path normal use reaches: a crash, an unhandled error, a leak in a long-running process.
  - **LOW** — hardening, defense in depth, a missing guard on trusted input that the project's conventions require. Without that requirement, a missing guard on trusted input is no finding.

## 1. Settle the cheap questions first

Each of these is decided by reading one thing. Do them before reasoning about the claim, and stop if one of them settles it.

- **Location**: invalidate a finding whose `location` has no resolvable file path, carries markdown punctuation (`**`, `##`), or holds conversational scratchpad ("We need to...", "Let's check..."). Invalidate a finding that offers a compliment ("Good.", "Looks solid.") and no defect. The code shows each line's number in the file before a tab; check the finding's lines against those numbers. A line number that does not match the code is a miscounted location, not a false finding.
- **Symbols**: a claim that an import, constant, function or class does not exist, or raises `ImportError` or `NameError`, is invalidated by finding it defined, imported or re-exported where the cited code can reach it.
- **Syntax**: invalidate a syntax-error claim against code that is valid for the language version the project declares. Read that version before calling a construct invalid: for example, Python 3.14 (PEP 758) accepts an unparenthesized multi-exception clause (`except A, B:`), which older Pythons reject.
- **Nullability**: a claim of a null or `None` dereference needs the value to be nullable where it is read: declared optional, returned by a lookup that can fail, or crossing an untyped boundary (parsed JSON, reflection, `**kwargs`, `any`). A default of `""`, `0` or an empty collection is not nullability. An existing null guard at the cited use invalidates the claim.
- **Advisories**: Dependency advisories come from the scanners, which look them up. Their findings put the identifier in brackets at the start of the title and sit at a lockfile (`uv.lock:<package>`). Neither you nor a reviewer can look an identifier up, so refute any other finding that rests on a CVE or GHSA identifier, against a dependency or against code, a well-formed one and a placeholder (`CVE-2023-xxxx`) alike. A version that only looks old is no evidence either. Compare versions component-wise, never as decimals: `0.141.1` is *ahead* of `0.110.0`.
- **Runtime floor**: invalidate a claim that code breaks on a runtime older than the project's declared minimum (`requires-python`, `engines.node`, the `go` directive, `rust-version`, the target framework). The toolchain refuses that runtime before the code runs. Read the floor from the manifest.
- **Plans and records**: invalidate claims against roadmaps, changelogs, task files and decision records. They describe plans and history, not the code.
- **Tests and fixtures**: test fixtures, golden files and mock responses hold vulnerability exemplars, fake credentials and malformed data on purpose; claims that they are vulnerabilities are false. A test that calls private helpers or exercises failure cases is not exposing anything. A claim about the test itself is a defect only when the test cannot fail or does not check what its name says. A real credential or a genuine vulnerability in a test file is judged as anywhere else (section 7).
- **Internal networking**: invalidate claims that plain `http://` to cluster-internal or private-network services (`http://*.svc.cluster.local`, `http://*.svc`, devcontainer and backend service names) is cleartext exposure.
- **Placeholders**: invalidate claims that documentation placeholders, dummy tokens or test identifiers (`ghp_your_personal_access_token`, `sk-ant-api03-...EXAMPLE`, `sk-proj-YOURKEY`, `dummy`, `test_`) or RFC 2606 domains (`example.com`, `example.org`) are leaked secrets or broken endpoints.
- **Pydantic default factories**: `Field(default_factory=dict)` and `Field(default_factory=list)` build a new value per instance; they are not shared mutable defaults.
- **POSIX signal 0**: `os.kill(pid, 0)` tests that a process exists without signalling it; it is not a race or a security flaw.
- **JSON parsing**: `json.loads()` cannot execute code; catching its `JSONDecodeError`, `TypeError` or `ValueError` is error handling, not an injection or a bypass.

## 2. Read the whole scope before claiming absence

- **Mutation after declaration**: a claim that a header (`Authorization`), parameter or payload option is missing requires tracing the entire enclosing function, including conditional mutations, `headers[...] = ...` assignments and fallback lookups that follow an initially empty declaration.
- **Variable definition**: an undefined-name claim requires that the name is absent from the whole function scope, including preceding assignments, conditional branches and fallback initializations.
- **Signatures and usage**: invalidate `TypeError` or constructor-conflict claims where the signature supports positional defaults with keyword overrides. Invalidate dead-code claims without checking cross-module imports and re-exports.
- **Present state**: invalidate a claim that a guard, check, parameter or branch is missing or was removed only when the shown code contains it; cite the line that holds it. When the code that would hold it is not shown, leave the finding unverified: an absence you cannot see is not evidence either way.

## 3. Name the sink, the sequence, or the mechanism

- **Sink**: an SSRF, RCE or injection finding needs a sink: the request, `exec` or query the value reaches. Invalidate it when the shown code only formats, stores, logs or displays the value and no sink is reachable from it.
- **Attribute access**: reading an attribute of a structured object (`getattr`, `hasattr` on a model or message) is not code execution; calling an attribute chosen by untrusted input is.
- **Arithmetic**: an off-by-one claim must state a concrete sequence of operations and the value it produces, not a reading of the comparison operator. Trace one step at the boundary and state the resulting size. Invalidate the claim when the traced value contradicts it.
- **Deliberate mechanism**: before reporting that a value leaves its expected range — a counter going negative, a balance overdrawn, a queue past a soft bound — read how later code consumes that value. When the excursion is what a subsequent computation depends on, report it at most as an undocumented invariant, never as a correctness or resource defect.

## 4. Resource claims

- **Bounded local input is not a denial of service**: invalidate CWE-400 claims about reading the project's own files or local configuration, or building in-memory collections from them. CWE-400 needs input a user or attacker controls, unbounded streaming, or quadratic complexity.
- **Quadratic work in loops**: verify findings where the same expensive work (parsing, serialization, counting) is repeated inside a loop over the same data for $O(N^2)$ cost. Invalidate or mitigate where single-pass or precomputed work is in place.
- **Unbounded stores**: verify findings where untrusted input grows a query result or cache that has no `LIMIT`, capacity bound, TTL expiry or FIFO/LRU eviction.
- **Exception detail size (CWE-209)**: verify where an untrusted string reaches an exception detail or a log unbounded; mitigate or invalidate where it is truncated. A string from trusted input falls under the trusted-input rule.

## 5. Markers, sandboxes and metadata

- **Redaction markers**: before you see the code, the review tool replaces values it takes for secrets with markers of the form `<masked-kind>` (`<masked-token>`, `<masked-password>`). A claim that such a marker is invalid syntax, an undefined name or a broken value is about the marker, not the code: refute it. A claim that the value behind a marker is a real secret is about the source, and stands. A bare `<masked>`, `***REDACTED***` or any other mask is the file's own text, and a claim about it is judged like any other. Ordinary identifiers (`secret_storage_failed`, `token_endpoint`) are not leaks.
- **Sandboxes**: verify a finding where an execution sandbox exposes reflection primitives (`getattr`, `sys`, `__import__`) unrestricted; mitigate or invalidate where they are stripped or blocked.
- **Validation coverage**: verify where an untrusted argument reaches a file path without the containment check the other arguments get; quote the argument, the path it reaches and the check it skips.
- **Build metadata**: invalidate supply-chain claims about `:latest` where the reference is a cache hint (`cacheFrom`, `cache-to`) or a comment. Verify where the tag names an image that is pulled, run or published.

## 6. Network addresses

Invalidate leakage claims for RFC 5737 documentation blocks (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) and placeholders (`<host>`, `example.com`). Whether a private address in the project's own files is a finding is the project's convention to state.

## 7. Two things never to do

- Never invalidate a genuine vulnerability — path traversal, SSRF, command injection, real secret exposure — because of where it lives. A test, a doc or a config file can hold one; a fixture's fake credential or deliberate exemplar is not one.
- Never invalidate on `verification_criteria` that asserts the absence of an error ("does not raise"). That proves nothing; a criterion must establish the defect.

Use `verification_criteria` and `invalidation_criteria` only to populate `verified_criteria_matched` and `invalidated_criteria_matched`. Never copy criteria text into a title, location or description. Put the step-by-step justification in `reason`.

Output ONLY a JSON array, one object per finding. Each object must include the finding's `finding_id` (the integer positional ID given in the input) and repeat the finding's `title` and `location`. The primary matching oracle is `finding_id`. An object that does not identify its finding is discarded, and a finding that receives no verdict stays unverified. `severity` is the band the evidence supports, and `confidence_score` (0 to 1) is how sure the evidence makes you:

```json
[
  {
    "finding_id": 1,
    "title": "Exact title of the finding this verdict is about",
    "verified": true,
    "mitigated": false,
    "invalidated": false,
    "status": "VERIFIED",
    "reportable": true,
    "location": "app/files.py:37-42",
    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
    "confidence_score": 0.7,
    "citation_line": 42,
    "mitigating_mechanism": null,
    "perimeter_files": [],
    "verified_criteria_matched": ["..."],
    "invalidated_criteria_matched": [],
    "reason": "Line 37 reads `name` from the request body; line 42 `open(os.path.join(root, name))` opens it with no containment check between them."
  },
  {
    "finding_id": 2,
    "title": "Exact title of the finding this verdict is about",
    "verified": false,
    "mitigated": false,
    "invalidated": true,
    "status": "INVALIDATED",
    "reportable": false,
    "location": "app/media.py:88-90",
    "severity": "LOW",
    "confidence_score": 0.8,
    "citation_line": 88,
    "mitigating_mechanism": null,
    "perimeter_files": [],
    "verified_criteria_matched": [],
    "invalidated_criteria_matched": ["..."],
    "reason": "Line 88 `if not re.fullmatch(r'[0-9a-f]{64}', digest): raise ValueError` admits no `..`, so the claimed traversal cannot happen."
  }
]
```
