# Task 502: Pinned Open-Source Sample Repositories Across Languages

**Issue**: [#502](https://github.com/dan-petty/devops-cli/issues/502)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

devops ai tooling is meant for any technical project, but every live check so far has used this Python repository and one set of Ansible playbooks. The AST engine claims TypeScript, JavaScript, Go, Rust, Java and HCL, and nothing exercises that on real code.

### Key Deliverables Completed:

- [x] **Catalog** (`src/devops_cli/ai/review/samples.json`): 16 repositories covering all 12
  categories, each pinned to a 40-character commit, with its SPDX licence, licence files and
  the paths the tooling is run over:

  | Category | Samples |
  | :--- | :--- |
  | Python | click (BSD-3-Clause) |
  | TypeScript/JavaScript | ky (MIT, TypeScript), express (MIT, JavaScript) |
  | Go | cobra (Apache-2.0) |
  | Rust | serde_json (MIT OR Apache-2.0) |
  | Java | gson (Apache-2.0) |
  | C#/.NET | serilog (Apache-2.0) |
  | C/C++ | cJSON (MIT, C), fmt (MIT, C++) |
  | Terraform | terraform-aws-vpc (Apache-2.0) |
  | Kubernetes/Helm | prometheus-node-exporter chart, kubernetes/examples (Apache-2.0) |
  | Dockerfiles | docker-nginx (BSD-2-Clause), docker-library/python (MIT) |
  | Shell | nvm (MIT) |
  | Technical documentation | kind's user guide (Apache-2.0) |

  Every repository was pushed to within the last seven months, and its working tree is 13 MiB or
  less.
- [x] **Policy enforced by the model** (`samples.py`):
  - licences must be permissive (MIT, Apache-2.0, BSD-2-Clause or BSD-3-Clause, or an SPDX
    expression of them);
  - commits must be full SHAs, never branches or tags;
  - repositories are `https://` (or `file://` for local mirrors), never another git transport;
  - names and paths stay inside the samples directory;
  - names are unique.
- [x] **`devops review samples fetch [NAMES] [--category]`**:
  - fetches only the pinned commit, at depth one and without credential prompts, into
    `.data/samples/<name>`;
  - then verifies the commit, the licence files and the paths;
  - leaves a checkout already at its commit alone, and moves a stale one to the pinned commit;
  - a dry run names what it would fetch.
- [x] **`devops review samples list [--category]`** shows the catalog and whether each sample
  is fetched at its commit.
- [x] **Samples directory setting**: `data.samples_dir` (`DEVOPS_CLI_DATA_SAMPLES_DIR`), default
  `.data/samples`, with the other data directories.
- [x] **Documentation**: command, configuration and environment references regenerated.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_samples.py`:
    - the catalog covers every category from GitHub at exact commits;
    - entries outside the policy are refused;
    - dual licences and selection by name or category work;
    - fetching from a local repository takes the pinned commit only, needs no network once
      fetched, moves a stale checkout, and reports a missing licence file, path or commit;
    - the list, fetch and dry-run commands work.
  - Fetching needs the network, so the tests fetch from local repositories and CI never
    fetches.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification

`devops review samples fetch` fetched all 16 samples from GitHub in 17 s (59 MB), each verified at
its commit with its licence files and paths. A second fetch changed nothing.
