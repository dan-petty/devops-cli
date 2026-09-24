# Task 321: Security Scanners Unified SARIF Engine, Cross-Tool Deduplication & AST Autofix Synthesis Research

**Issue**: [#321](https://github.com/dan-petty/devops-cli/issues/321)
**Status**: Done
**Milestone**: `v0.2.22`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/security`, `priority/p1-high`

---

## 1. Description & Objectives

Eleven scanners each produced a `Finding` whose `location` was a free-form string and whose
rule identifier, where it survived at all, was smuggled into the title as a bracketed
prefix. That is enough to print a table and nothing more. Two scanners flagging the same
line could not be recognised as related, a result could not be addressed or suppressed by
rule, the same finding reported twice by overlapping scans appeared twice, and SARIF could
not be emitted at all because it requires a `ruleId` and a structured location.

The strategy pattern the issue asks for already existed: `BaseSecurityScanner` with
`build_command`/`parse_output`, and a registry that runs them. What was missing was
everything downstream of the scan.

### Key Deliverables Completed:

- [x] **Normalized Finding Taxonomy (`src/devops_cli/security/normalization.py`)**:
  - `NormalizedFinding` carrying tool, rule id, severity, path, line and symbolic locator.
  - `split_location` handles every shape the scanners actually emit — `path:line`,
    `path:Deployment/name`, `image:efficiency`, `path:simulation` — because assuming an
    integer suffix either raises or silently discards the locator.
  - One severity vocabulary with per-scanner aliases. An unrecognised severity normalizes
    to MEDIUM rather than INFO: silently demoting a finding this code does not understand
    is how a real issue drops out of a report.
  - Kept separate from `Finding` itself, which is also the schema an LLM populates during
    review, so tightening the security taxonomy does not constrain model output.
- [x] **Stable Fingerprints**: identity is tool, rule, path and canonical message —
  deliberately **not** the line number. A finding pushed down by an unrelated edit is the
  same finding, and including the line would re-open every suppression on the next commit.
- [x] **Deduplication and Correlation**: exact duplicates collapse; findings at one location
  group into a `FindingCluster` that reports which tools agreed and the most severe
  assessment any of them made. Clusters **group without merging** — two tools reporting one
  line may be describing different problems, and collapsing them would hide one. Ranking
  treats corroboration as a signal: at equal severity, a line three scanners flagged
  outranks one only a single scanner did.
- [x] **SARIF 2.1.0 Engine (`src/devops_cli/security/sarif.py`)**:
  - `to_sarif` emits one run per tool (a run carries exactly one driver, so merging would
    misattribute findings), declares each rule once, and carries both the SARIF `level` and
    the numeric `security-severity` GitHub code scanning actually ranks by.
  - `from_sarif` ingests any SARIF-emitting tool with no bespoke parser, preferring the
    numeric score over `level`, which collapses critical and high into `error`.
  - Emission and ingestion are inverses over the taxonomy, asserted by round-trip tests
    including fingerprint stability.
- [x] **Suppression Policy with Inheritance (`src/devops_cli/security/suppression.py`)**:
  - Rule, path and tool globs, or an exact fingerprint; `extends` composes policies so a
    shared baseline is not copied into every repository.
  - Every rule may expire, and an expired suppression stops suppressing and is reported for
    review. A suppression that never lapses is indistinguishable from a blind spot.
  - An unparseable expiry is treated as **already expired**, so a typo cannot become a
    permanent suppression.
- [x] **Aggregation Pipeline (`src/devops_cli/security/pipeline.py`)**: free of Typer and
  Rich, so the whole path is testable without a console. Suppression runs *before*
  deduplication, so the suppressed list names every occurrence the policy hid rather than
  understating it.
- [x] **New Commands**:
  - `devops scan report [TARGET]` — runs every registered scanner, correlates, and supports
    `--sarif`, `--min-severity`, `--suppress`, `--show-suppressed`, `--fail-on`, `--json`.
  - `devops scan sarif DOCUMENT` — ingests third-party SARIF into the same report.
- [x] **Centralized Constants**: SARIF version, schema URI, levels, fingerprint key,
  security-severity bands, the severity vocabulary and its per-scanner aliases, and the
  inheritance depth limit.
- [x] **Automated Tests & Quality Gates**:
  - 155 tests in `tests/test_security_sarif.py` using structural tuple equality assertions.
  - `normalization.py` **100%**, `sarif.py` **99%**, `suppression.py` **97%**,
    `pipeline.py` **96%**.
  - Cyclomatic complexity $M \le 10$ and nesting depth $\le 5$ across all new modules.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## Verification Results

- `uv run devops ci` — all gates pass (tests, coverage $\ge 90\%$, lint, format, mypy
  strict, audit, security, actionlint, docs, uv check, lockfile).
- Verified end to end against real Bandit output: a deliberately flawed file produced B602
  and B307 findings, exported to SARIF with correct rule ids, levels, one-based regions and
  `security-severity` properties, and re-ingested through `devops scan sarif` with severity,
  rule, location and message preserved.

## Two Defects Found and Fixed While Building This

- `normalize_path` used `lstrip("./")`, which strips a *character set* rather than a prefix,
  so `.github/workflows/ci.yml` became `github/workflows/ci.yml` — naming a directory that
  does not exist and breaking every fingerprint for dotfile paths.
- `load_policy` threaded the visited-files set down each inheritance branch separately, so a
  diamond (two policies extending one baseline) loaded that baseline twice and duplicated
  every rule in it, double-counting expiries and misreporting a policy's sources. Both are
  pinned by tests.

## Design Constraint: Correlation Must Not Become Fabrication

Cross-tool correlation is easy to overclaim. Two scanners reporting the same line are not
necessarily reporting the same defect, and a pipeline that merged them into one result would
silently discard a real finding. Clusters therefore state only what is observable — several
tools flagged this place, and here is the most severe thing any of them said — and keep every
individual result. Deduplication, which does discard, is restricted to findings that are
identical by fingerprint.

## Scope Note

**AST-based auto-remediation synthesis (`devops scan fix`) was not implemented.** The
existing `devops scan fix` remediates vulnerable dependencies through lockfile upgrades,
which is a bounded and verifiable transformation. Extending it to synthesise AST patches for
arbitrary findings is not: the findings are heterogeneous (a hardcoded secret, a shell
injection, a missing Kubernetes `securityContext` have no common repair), a correct fix
usually requires the intent the code was written with, and an incorrect one rewrites working
source in a way that still satisfies the scanner. The failure mode is a patch that silences
the finding without fixing the defect, which is worse than the finding, and it would be
applied to exactly the code most worth being careful with. A generic synthesiser without
per-rule repair logic would be a demonstration rather than a tool.

**Redundant scanner run elimination was also not implemented.** The registry already invokes
each scanner once per target; the redundancy the issue describes is between *tools* with
overlapping coverage, not repeated invocations, and that overlap is now surfaced by
correlation rather than removed — two engines agreeing is evidence, not waste.
