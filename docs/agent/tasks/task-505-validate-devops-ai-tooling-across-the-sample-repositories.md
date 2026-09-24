# Task 505: Validate devops ai Tooling Across the Sample Repositories

**Issue**: [#505](https://github.com/dan-petty/devops-cli/issues/505)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/feature`, `scope/ai`, `priority/p1-high`

---

## 1. Description & Objectives

Nothing shows whether AST parsing, repomaps, analysis and reviews work on projects that are not Python: which parser runs, whether pages and labels are right, and whether the reviewer finds defects in each language.

### Key Deliverables Completed:

- [x] **`devops review samples validate [NAMES] [--category] [--review] [--all] [--seed]`** runs
  the tooling over the fetched samples (#502). It saves one JSON report per category under
  `.data/reviews/sample-validations/<run>/`, recording:
  - which parser read each file (tree-sitter, the regex fallback, or none) and its symbols;
  - what file analysis made of each file: its language, symbols and dependencies;
  - how many files and symbols the multilingual repository map shows of each sample;
  - with `--review`, the category's synthetic defect corpus (#503, #504), reviewed with the default
    persona (or all with `--all`) and scored.
- [x] **Problems per category**:
  - a language the engine claims but reads with the regex fallback;
  - files with no symbols;
  - code types with no AST support;
  - code the file analysis reads as plain text or labels C++ as C;
  - an empty repository map;
  - a review that found nothing, lost everything to verification, or failed.

  A failed review is recorded in its report instead of ending the run. Samples not fetched at
  their commits are named, with the command that fetches them.
- [x] **`--category` is repeatable** on `samples list`, `fetch` and `validate`; it kept only the last.
- [x] **Documentation**: a Sample Repositories section in `docs/SELF_IMPROVEMENT.md`; command
  references regenerated.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_sample_validation.py`:
    - a category report with the regex fallback, a file without symbols, unsupported C# and C++,
      mislabelled C++ and an ignored licence file;
    - every review problem;
    - the command writing its report;
    - `--review` injecting, reviewing (a stand-in review) and scoring;
    - a failed review recorded;
    - unfetched samples;
    - repeated categories.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. First Full Run

`devops review samples validate --review`, run `20260924-205901`. All 16 samples at their pinned
commits, reviewed with the default persona through the cluster gateway. It took 64 minutes, nearly
all of it in the 12 reviews.

| Category | Files | Parser | Symbols | Repomap files | Review found / reported / injected |
| :--- | ---: | :--- | ---: | ---: | :--- |
| Python | 18 | fallback 17 (the stdlib parser) | 623 | 16 | 0 / 0 / 2 |
| TypeScript/JavaScript | 37 | fallback 37 | 54 | 102 | 4 / 3 / 20 |
| Go | 5 | fallback 5 | 191 | 18 | 1 / 1 / 4 |
| Rust | 37 | fallback 37 | 763 | 27 | 2 / 2 / 6 |
| Java | 85 | fallback 85 | 1,649 | 90 | 5 / 4 / 24 |
| C#/.NET | 116 | none | 0 | 0 | 3 / 2 / 14 |
| C/C++ | 24 | none | 0 | 1 | 1 / 1 / 10 |
| Terraform | 5 | fallback 5 | 439 | 41 | 0 / 0 / 2 |
| Kubernetes/Helm | 59 | none 57, fallback 2 | 7 | 14 | 6 / 5 / 8 |
| Dockerfiles | 14 | none | 0 | 0 | 5 / 3 / 14 |
| Shell | 3 | none | 0 | 0 | 0 / 0 / 2 |
| Documentation | 13 | none | 0 | 78 | 1 / 1 / 3 |

The reviews found 28 of the 109 injected defects (26%), and 22 were still reported after
verification.

### Failures, each filed

| Failure | Evidence | Issue |
| :--- | :--- | :--- |
| Findings located by a bare file or function name are not tied to their file | 36 of 208 candidates; resolving bare file names alone lifts the run to 33 found, 24 reported | #535 |
| The verifier invalidates findings its own reason confirms | all 3 unpinned `:latest` image findings | #536 |
| The defect generator injects into code examples inside block comments | 9 of 78 brace-language injections, all `drop-await` in ky's JSDoc | #537 |
| The AST engine never uses tree-sitter: no grammar is installed | every TS, JS, Go, Rust, Java and HCL file read by the regex fallback; 16 of 31 TypeScript and 10 of 37 Rust files yield no symbols | #538 |
| No AST support for C#, C/C++, shell and Markdown | 113 C#, 24 C/C++, 13 shell and 18 Markdown files; empty repository maps for serilog, fmt and nvm | #506 (open) |
| No AST support for YAML, Dockerfiles and Helm templates | 42 YAML files, 5 Dockerfiles, a Helm template; empty maps for the Docker samples | #539 |
| File analysis labels C++ as C and Helm templates as plain text | fmt's 4 `.cc` files, the chart's `_helpers.tpl` | #540 |
| `contradict-documented-default` cannot be judged without the code | both documentation injections drew no finding; kind's docs corpus holds no code | #541 |

The remaining misses are the model not finding or not keeping a defect. Examples are the Python,
Terraform and shell corpora (0 of 2 each), C# (3 of 14), and a Java guard found and then refuted
with false reasoning. #475 measures that per backend. The
TypeScript row counts 9 injections inside comments (#537); of the 11 real ones, 4 were found.
