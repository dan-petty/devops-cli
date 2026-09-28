# Task 515: Review Prompts Apply This Repository's Rules to Every Project

**Issue**: [#515](https://github.com/dan-petty/devops-cli/issues/515)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

From the #509 audit. The shared prompts carry several of this repository's rules: its Python
version rules, network exemptions, house style rules and roadmap mandates. They also require
linked context that the generation prompt never supplies, and keep lockfiles out of review. Build
files and templates are reviewed as documentation.

The work lands in three parts, the last of which closes the issue:

1. The verifier: project conventions, and a project-agnostic verifier prompt.
2. The persona prompts: house rules and roadmap mandates out, absence rules matched to the context
   actually given.
3. Scope: lockfiles and build files reviewed as what they are, per-file pages, and PR reviews read
   from the PR head.

### Part 1: Verifier (Done)

- [x] **Project review conventions**: a project may keep review rules in `.devops/review.md`. The
  nearest from the target up to its repository root is read in full (up to
  `DEFAULT_REVIEW_CONVENTIONS_MAX_CHARS`) beside the general conventions file.
- [x] **Conventions found the same way everywhere**:
  - The orchestrated review read conventions only from the target directory itself, while the
    legacy path looked up to the repository root. Both now use the nearest-first lookup in
    `review_environment`, cached per target directory.
  - A corpus always carries a `.devops/review.md`, so the lookup stops at the corpus instead of
    reaching the repository around it.
- [x] **The verifier gets the conventions**: `_validate_segment_findings` passes the project's
  conventions into the verification prompt, in an untrusted block to be applied only where they
  settle a finding. The verifier previously received none.
- [x] **A project-agnostic verifier prompt**: `verify_finding_system.md` no longer assumes this
  repository.
  - Removed: `mypy --strict`, the "What this tool is: a DevOps CLI" section (internal connectors,
    console output), RFC 1918 addresses in documentation, and local-file CWE-400 during a CLI run.
  - Now generic: the syntax rule reads the language version the project declares, the runtime
    floor reads any manifest, and nullability is judged at the use.
  - A line number that does not match is a miscounted location. An absence the verifier cannot
    see leaves the finding unverified rather than invalidating it.
- [x] **devops-cli's rules move to its own `.devops/review.md`**, so they still apply when this
  repository is reviewed.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_project_conventions.py`:
    - the shared verifier prompt contains no devops-cli rule;
    - this repository keeps them in its own conventions;
    - nearest review conventions win;
    - verification receives the conventions;
    - the prompt shows them only when they exist.
  - `tests/test_review_verification.py`: the rule-coverage test checks the moved rules in
    `.devops/review.md`.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

#### Part 1 on a Live Cluster

The #415 corpus (seed 1), reviewed with all personas before and after this part, on the release
with #500, #512 and #513 merged:

| | Before | After |
| :--- | ---: | ---: |
| Injections found | 9 | 8 |
| Injections still reported | 6 | 6 |
| Findings reported in all | 34 | 40 |
| Verifier invalidations | 32 | 39 |

On this corpus the change is neutral within run-to-run variance. The rules that moved concern
devops-cli's connectors and console output, which none of the injected defects touch. What it
changes is how other projects are judged.

The verifier's remaining invalidations show one pattern. It confirms the defect, then dismisses
it on a mitigation it asserts, and records that reasoning as invalidation evidence:

- "The `_depth` parameter is never checked against
  `CONST_SUPPRESSION_MAX_INHERITANCE_DEPTH` … the `loaded` set … is sufficient." That stops
  cycles, not deep chains.
- "does not perform a post-resolve containment check, but that is unnecessary because symlink
  rejection already blocks escape." It does not block `../`.

Part 2 separates refutation from mitigation.

### Part 2: Mitigation and Persona Prompts (Done)

- [x] **Refuted or mitigated**:
  - The verifier prompt now defines refutation as the shown code contradicting the claim, with
    the line cited. A mitigation must name its mechanism and cite the line providing it.
  - A verdict whose own reasoning confirms the defect is at most mitigated.
  - A mitigated finding stays in the report, with its mitigation shown in the console panel and
    in `review.md`. It does not drive the recommendation.
  - A mitigation verdict without a reason leaves the finding unverified.
- [x] **Persona and shared prompts hold only general rules**. Moved to this repository's
  `.devops/review.md`:
  - house rules: symlink-skipping walks, split HTTP timeouts, quota and `RLock` rules, sandbox
    network defaults, tool-wrapper masking, RFC 1918 addresses in docs, pre-1.0 legacy hygiene;
  - the "When the target is this repository" section;
  - the internal-connector, console-output and CLI-memory exemptions in the devsecops persona.
- [x] **Rules removed from the prompts**:
  - The instruction to drop findings matching the hallucinations catalog; the model never sees
    the catalog.
  - "Drop the already-mitigated": personas now report a limited defect with its mitigation and
    a lower severity.
  - Roadmap mandates in the shared, path, diff, architect and PM prompts: improvements go in
    `summary`, never in `findings`.
- [x] **Absence rules match the context given**: "omit a missing-check finding unless linked
  context confirms it" applied to context the generation prompt never receives. Personas now
  report it with the unchecked assumption and a lower confidence, and verification settles it.
- [x] **Missing tests**: QA reports a missing regression test only when reviewing a change, not
  for files whose tests it was not shown.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_project_conventions.py`:
    - no shared review or persona prompt carries a project rule (roadmap, homelab, `RLock`,
      Valkey, catalog);
    - this repository's conventions hold them;
    - a mitigated finding is reported with its mitigation.
  - `tests/test_personas.py` and `tests/test_review_verification.py`: rule coverage is split
    between the shared prompt, `.devops/review.md`, and rules removed on purpose.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

#### Part 2 on a Live Cluster

The #415 corpus, against part 1's run on the same release:

| | Part 1 | Part 2 |
| :--- | ---: | ---: |
| Injections still reported | 6 | 6 |
| Candidates invalidated by the verifier | 39 | 16 |
| Reported as mitigated, reason shown | 0 | 16 |
| Reported as verified | few | 24 |

- The verifier now reports what it had dropped as refuted. Some of the mitigations it states are
  wrong, and they are wrong in plain view:
  - `load_policy` "includes a depth check using the `_depth` parameter", the check the corpus
    removed;
  - `resolve_safe_subpath` "includes a check to ensure the resolved target path is within the
    root dir", also removed.

  Before, both findings were silently invalidated.
- Several SSRF mitigations misread `allow_private_network=True`, which enables private access
  rather than limiting it.
- The verifier model's reasoning is #475's to measure.

### Part 3: Scope (Done)

- [x] **A PR review reads the PR**:
  - Its pages came from the PR's diff, but verification, the scanners and dependency extraction
    read files from the local checkout: another version of them, none, or another repository's
    under `--repo`.
  - The changed files are now fetched at the PR's head commit, from the head repository for a
    fork, into a temporary directory the review reads. The repository's conventions files at that
    commit are fetched too (`GitHubClient.get_file_at`, `_materialize_pr_head`). Filenames that
    would escape the directory are refused.
- [x] **Each file gets its own pages**: persona review received every page whose text contained
  the filename, so `a.py` was given `data.py`'s pages. Pages now map to the files their headers
  name.
- [x] **Code and configuration are not reviewed as documentation**:
  - A known name or extension now decides before the content is sniffed. A Python file opening
    with a `# Copyright` comment, or a YAML document opening with `---`, had been classified as
    documentation, whose prompt tells reviewers not to flag the vulnerabilities a text describes.
  - `requirements*.txt`, `constraints.txt`, `CMakeLists.txt`, `Makefile`, `go.mod`, `go.sum` and
    similar are configuration.
  - HTML and template files (`.html`, `.j2`, `.jinja`, `.tmpl`, `.hbs`, `.ejs`, `.vue`, `.svelte`)
    are code, so template injection and XSS are in scope.
- [x] **Lockfiles reach the scanners**: the persona review leaves lockfiles out for their size, and
  the scanners saw only reviewed files. Lockfiles beside the reviewed files now go to Trivy, and a
  finding in a file that was not reviewed attaches to a reviewed file in the same directory,
  preferring the dependency manifest.
- [x] **Page overlap moves to #499**: page splits without overlap belong with numbering the lines
  of review pages.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_scope.py`:
    - the PR head's files and conventions are written, removed and escaping files skipped;
    - the `pr` command reviews against that directory;
    - each file gets only its own pages;
    - lockfiles are scanned and their findings attached to the manifest.
  - `tests/test_review_classification.py`: a known name decides before the first line, across
    ten file kinds.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

#### Part 3 on a Live Cluster

`_prepare_pr_content` for PR #525 against GitHub wrote its 21 changed files at head `836a5814`,
including this repository's `AGENTS.md`, `CLAUDE.md` and `.devops/review.md` at that commit, and
loaded the conventions from them. Trivy is not installed in this devcontainer (#516), so the
lockfile path is verified by tests.
