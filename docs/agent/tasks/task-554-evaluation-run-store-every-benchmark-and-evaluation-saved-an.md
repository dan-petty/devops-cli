# Task 554: Evaluation Run Store: Every Benchmark and Evaluation Saved and Shared

**Issue**: [#554](https://github.com/dan-petty/devops-cli/issues/554)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Benchmarks and evaluations are meant to be repeated over the life of the tool, but only some kept
results, each in its own shape. `corpus score`, `ai gateway tune` and `ai prompt-eval` kept
nothing. `ai benchmark` did save its report to the benchmarks directory, with or without
`--output`; the roadmap said otherwise. Nothing was shared between workstations: the in-cluster
Valkey is reachable only inside the cluster and keeps its data on an `emptyDir`.

### Key Deliverables Completed:

- [x] **Run records** (`ai/run_store.py`). Each run is one JSON file under
  `data.runs_dir/<mechanism>/<run id>.json`, the source of truth. A record holds:
  - the mechanism, run id and time;
  - the devops-cli version and commit, marked `-dirty` when the source has uncommitted changes
    (an installed package reports no commit);
  - the setup, and its `fingerprint`;
  - the subject, and its `subject_key`;
  - the results.

  Both digests depend on content, not key order, so runs with equal setups or subjects match
  across workstations.
- [x] **Every mechanism writes one:**
  - `review benchmark`:
    - setup: personas, pre-analysis, concurrency, models and page size;
    - subject: the corpus digest and target name;
    - results: the full summary.
  - `review samples validate`: one record per category.
    - subject: the samples' pinned commits;
    - the records are shared in one round trip.
  - `review corpus score`: the score with each injection's outcome, and the titles and statuses
    of the findings that matched it.
    - subject: the corpus's injections;
    - setup: as configured when scoring.
  - `ai gateway tune`:
    - setup: levels, rounds, prompt and completion sizes, and each deployment's backend, model,
      weight, engine and GPUs;
    - subject: the model group.
  - `ai prompt-eval`: its subject is a digest of the persona's recorded verdicts, which the
    result now reports.
  - `ai benchmark`: task, suite and embedding runs, by tasks, dataset or document. Dry runs are
    not kept.
- [x] **Review setup** records:
  - the analysis and verification models;
  - the review page size;
  - for gateway providers, each model group's pool (backend, model, weight, input limit), read
    from the gateway's `/model/info`.
- [x] **Shared index**: a dedicated Valkey, `k8s/llm/valkey-runs.yaml`. It is separate from the
  in-cluster cache, whose clients use no password:
  - a password from the `valkey-runs-auth` Secret, created out of band;
  - an append-only file on a PVC;
  - `noeviction`;
  - a NodePort that Kubernetes assigns;
  - a network policy admitting only its port, with no egress.

  Each record is stored as `devops-cli:runs:record:<mechanism>:<id>`, with its id in sorted
  sets by mechanism and by subject.
- [x] **Commands**:
  - `devops ai runs connect` finds the index's NodePort and copies its password from the Secret
    into the keyring, never printing it. It then indexes the runs already kept and saves
    `runs.index_url`.
  - `devops ai runs reindex` rebuilds the index from the data directory.
- [x] **Works without Valkey, saying so.** A run with no index configured, or one that is
  unreachable, is kept locally, and the command says why and what shares it later. Commands
  writing JSON announce the run on stderr, so their stdout stays parseable.
- [x] **Settings**: `data.runs_dir`, `runs.index_url` and `runs.index_password` (keyring).
- [x] **Shared NodePort lookup** (`k8s/node_port.py`), used by `telemetry connect` and
  `ai runs connect`.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_run_store.py`:
    - content digests and the version and commit;
    - records by mechanism, oldest first, skipping unreadable files;
    - the index by mechanism, subject and id, in one round trip;
    - runs kept locally when no index is configured or reachable;
    - reindex, and reindex without an index;
    - connect: the password reaches the keyring and never the config or output;
    - records from review benchmark, prompt-eval (JSON on stdout), gateway tune and AI
      benchmark (dry runs not kept);
    - an installed package reports no commit.
  - `tests/test_review_defects.py`: repeated scores of one corpus share a subject.
  - `tests/test_review_sample_validation.py`: a record per category with its sample commits.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

### Not verified in the cluster

The manifest was checked with `kubectl kustomize`, not applied. To deploy:
1. Create the `valkey-runs-auth` Secret (see the manifest's header).
2. Apply `k8s/llm`.
3. Run `devops ai runs connect`.
