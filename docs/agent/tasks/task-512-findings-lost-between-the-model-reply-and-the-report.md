# Task 512: Findings Lost Between the Model Reply and the Report

**Issue**: [#512](https://github.com/dan-petty/devops-cli/issues/512)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p0-critical`
**Scope**: `type/bug`, `scope/review`, `priority/p0-critical`

---

## 1. Description & Objectives

From the #509 audit: findings were lost between the model's reply and the report, with no model
involved and no trace left.

### Key Deliverables Completed:

- [x] **Scanner findings kept**: Gitleaks, Bandit, Semgrep, Trivy and OSV findings seeded into a
  file's payload were replaced by the persona findings (`pipeline.py`), and every error path
  set `payload.findings = []`.
  - Seeded findings now stay beside the persona findings.
  - A failed page keeps what was found before it.
  - Bringing them back would have reported every historical OSV advisory for each dependency, so
    OSV is queried only for exact versions (a range, an npm wildcard or Cargo's bare version is
    not one).
  - Shodan host findings enter verification unverified instead of VERIFIED HIGH.
- [x] **A reply keeps its valid findings** (`parse_review_response`):
  - One malformed field no longer drops the reply; each finding is validated on its own.
  - Findings under `issues`, `results` or one level down (`{"review": {"findings": [...]}}`) are
    found; that shape had produced an empty APPROVE.
  - A fenced JSON block wins over stray braces in the prose.
  - A literal `<think>` inside a finding no longer truncates the reply. Response repair strips an
    unclosed `<think>` only when it opens the reply; the streaming processor keeps its own rule.
- [x] **Distinct defects stay distinct** (`_are_findings_duplicate`):
  - Filler words ("missing", "potential", "insecure") no longer count as shared words.
  - Findings at overlapping lines merge on agreeing distinguishing words, or on a shared title
    symbol plus one more shared word.
  - Findings far apart merge only with near-identical titles naming the same symbol.
  - A dismissed finding never merges with a live one.
- [x] **Titles survive sanitizing**: praise with a defect word ("Looks good overall, but…"), a
  one-sentence title opening "Checking…" or "Based on…", and "verification criteria" as a subject
  are kept. Only a `Verification criteria:` header counts as leaked prompt text.
- [x] **A persona cannot set its own verification state**: status, reportability and the verified
  and mitigated flags are reset on every persona finding, so a reply cannot skip verification or
  drop its own finding.
- [x] **Redaction masks secrets, not code**:
  - Unquoted code expressions after `password =` or `token =` are left as written: calls, index or
    collection expressions, dotted attribute paths (`hashlib.md5(pw).hexdigest()`,
    `req.query.token`, `os.environ[...]`).
  - URL credentials need a `user:password@` shape, so `host:8080/path?email=a@b.com` is untouched.
  - A masked private key keeps its line count.
  - One accepted edge: an unquoted dotted literal (`password: my.secret.pw`) is left unmasked.
- [x] **Severity names keep their meaning**: BLOCKER, P0 and SEVERE map to CRITICAL, MAJOR to HIGH,
  MINOR to LOW, and SUGGESTION and INFORMATIONAL to INFO. Previously all of them became MEDIUM.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_finding_losses.py`: 53 tests, each reproducing a loss the audit found.
    Scanner findings surviving review and failure fail on the old code.
  - `tests/test_review_loop_calibration.py`: two near-identical titles 40 lines apart are now kept
    as two findings. While pages carry no line numbers (#499), they cannot be told apart from two
    instances of one defect, and a kept duplicate costs less than a lost defect.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The #415 corpus (seed 1, byte-identical to the earlier runs), reviewed with all personas through
the homelab gateway:

| | #415 run | #500 run | This change |
| :--- | ---: | ---: | ---: |
| Injections found | 8 (1 false match) | 7 | 6 |
| Injections still reported | 1 | 1 | **2** |
| Reported findings beyond the injections | 1 | 0 | 2 |

Both `widen-file-mode` injections were reported. The `vault_lease.py` dropped status check was
found by a genuine finding ("HTTP POST helper does not validate response status"), which the
first run had matched only by a false line match. Found counts move by one either way between
runs.

The static scan printed "0 findings" with only Bandit installed. Semgrep, Gitleaks, Trivy,
kube-linter and Pluto are absent here, so the scanner fix is verified by tests. The silent
skip is #516.
