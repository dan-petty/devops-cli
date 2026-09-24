# Task 515: Review Prompts Apply This Repository's Rules to Every Project

**Issue**: [#515](https://github.com/dan-petty/devops-cli/issues/515)
**Status**: In Progress
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

### Parts 2 and 3 (Backlog)

- [ ] Verifier: a confirmed defect with an asserted mitigation is not a refutation. Mitigation must
  cite the line that provides it, and a mitigated finding is reported with the mitigation stated
  rather than dropped.
- [ ] Persona and shared review prompts: PEP 758 as universal, the unnamed "this repository"
  section, house rules (split timeouts, symlink-safe walks, RFC 1918 in docs, `http://` in
  config), and roadmap mandates emitted as findings. Absence bans that assume linked context the
  generation prompt never receives.
- [ ] Scope:
  - lockfiles excluded from review and never passed to Trivy;
  - `requirements.txt`, `CMakeLists.txt` and HTML templates classified as documentation;
  - `diff_map` matching file names as substrings;
  - PR reviews scanning the local checkout;
  - page splits without overlap.
