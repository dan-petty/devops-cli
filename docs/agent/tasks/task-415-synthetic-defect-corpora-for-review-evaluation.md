# Task 415: Synthetic Defect Corpora for Review Evaluation

**Issue**: [#415](https://github.com/dan-petty/devops-cli/issues/415)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Evaluating a reviewer needs code whose defects are known exactly. Real repositories do not supply
that: a finding is only ever labelled by another judgement, usually the verifier being measured.
Code with a defect injected at a known line gives a recall that is measured rather than inferred.

### Key Deliverables Completed:

- [x] **Generator** (`ai/review/defects.py`, `devops review corpus generate <sources>`): copies the
  files a path review would read and injects one defect into each, chosen per file by a seed, so
  the same seed and files give the same corpus. Nine templates:
  - Python: `drop-bounds-check`, `drop-path-containment` and `drop-await`, found through the AST.
    A dropped guard must leave valid Python.
  - YAML and Dockerfiles: `unpin-image-tag`, `unpin-action-ref`, `disable-tls-verify`,
    `log-secrets`, `widen-file-mode` and `weaken-pod-security`, as line rules.

  Several sources make one corpus, each under its own folder.
- [x] **Answers kept out of the review**: mutated files go under `files/`, and the manifest of
  injections (template, file, line, original and mutated text, and the region where a report
  counts) sits beside that directory. The corpus carries the first source's conventions file.
  Conventions are now read nearest-first, from the target up to its repository root, so a corpus
  inside this repository is not reviewed under this repository's `AGENTS.md`.
- [x] **Every candidate kept**: the report stage writes `candidates.json`, every finding with its
  verification status. `findings.json` keeps only reported findings, so invalidated ones were
  lost, and with them any measure of what verification dropped.
- [x] **Scoring** (`devops review corpus score <corpus>`): a finding matches an injection when it
  names the file and either points into the injection's region (within the line tolerance) or
  names its evidence (the changed value, the key it was set on, or the guard's identifiers). It
  reports:
  - injections found among the candidates, and how many of them by line;
  - injections still reported after verification;
  - injections found and then dropped;
  - injections whose file was named only elsewhere;
  - reported findings beyond the injections.

  Each injection is listed with the titles of the findings it matched, so a false match is visible.
  By default it scores the latest session whose profile shows it reviewed the corpus, rather than
  whichever session ran last. `--json` gives the full outcome per injection.
- [x] **Caveat carried with every number**: the manifest, the score and the command output state
  that synthetic recall measures regression against known injections, not review capability.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_defects.py`:
    - each template's mutation, scoring region and evidence;
    - places without a defect to inject, including guards whose removal would break the code;
    - seeded reproducibility and the answers kept outside `files/`;
    - matching by line and by evidence, and a file-name boundary (`xsite.yaml` is not
      `site.yaml`);
    - found, reported, dropped and extra findings;
    - both commands end to end, including refusing to score a session that did not review the
      corpus.
  - `tests/test_review_pipeline.py`: `candidates.json` keeps the invalidated findings that
    `findings.json` leaves out.
  - `tests/test_review_path.py`: the nearest conventions file wins over the repository root's.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

A corpus from the homelab playbooks and this repository's `core`, `security` and `crypto` modules,
seed 1: 10 injections over 10 files. It was reviewed with all personas through the homelab gateway
(8 min 44 s, 77 LLM calls, 68 candidate findings, 56 invalidated) and then scored:

| Injection | Template | Outcome | Matched findings |
| :--- | :--- | :--- | :--- |
| `playbooks/04_gpu_validation.yaml:41` | `unpin-image-tag` | found, invalidated | Unpinned Image Tag |
| `playbooks/06_cluster_backup.yaml:19` | `widen-file-mode` | found, not kept | Unrestricted Directory Permissions |
| `core/audit.py:95` | `drop-path-containment` | **reported** | Unvalidated audit log destination |
| `core/paths.py:60` | `drop-path-containment` | found, invalidated | Missing Path Containment Check |
| `core/process.py:417` | `drop-await` | missed | — |
| `core/repo.py:250` | `drop-path-containment` | found, invalidated | Potential Path Traversal Vulnerability |
| `security/suppression.py:200` | `drop-bounds-check` | found, invalidated | Missing inheritance depth limit in load_policy |
| `security/vault_lease.py:58` | `drop-bounds-check` | false match | Syntax Error in Header Assignment (by line) |
| `security/vulnerability_lookup.py:614` | `drop-bounds-check` | missed | — |
| `crypto/known_hosts.py:248` | `widen-file-mode` | found, invalidated | Insecure Directory Creation Permissions |

The score reads 8/10 found and 1/10 reported. Reading the matched titles, one match is false, so
the personas found 7 and verification kept 1. Only 3 matched by line. The first run of this
corpus surfaced three defects, now tracked:

- **#500**: the deterministic missing-symbol check invalidated 4 findings of injected defects
  because they contain "missing" and name a function that exists, then recorded them in the
  hallucinations catalog.
- **#499**: review pages carry no line numbers. The `known_hosts.py` defect at line 248 was
  reported at lines 103–132.
- **#498**: a `+` in the corpus name (the first run's `playbooks+core+...`) cut every finding's
  location to `.data/reviews/corpora/playbooks`. Corpus names now join sources with `-`.

This is one review of one corpus. It describes the pipeline as it stands and is not a recall
estimate for the reviewer.
