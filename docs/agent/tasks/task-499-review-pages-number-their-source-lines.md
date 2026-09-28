# Task 499: Review Pages Number Their Source Lines

**Issue**: [#499](https://github.com/dan-petty/devops-cli/issues/499)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

Review pages give the model source text without line numbers, and a part of a split file starts
mid-file with no offset, so every reported line range is the model's own count. The synthetic
defect corpus (#415) caught it: an injected `mkdir(mode=0o777)` at line 248 of
`crypto/known_hosts.py` was reported at lines 106–108 and 112–115. Locations drive patching,
duplicate consolidation by line overlap and the verifier's out-of-range check.

Split pages lost more than the offset. The orchestrated pipeline joined a file's pages and cut
anything over its page budget at arbitrary lines, so a later page had no file header, no fence and
no overlap with the page before it, and a defect at the boundary was never seen whole (from #515).
The verifier's excerpt counted lines from the top of the first page naming the file, so a finding
in a later part was shown other code, or none.

### Key Deliverables Completed:

- [x] **Numbered lines**: every page line carries its line number in the file and a tab
  (`number_source_lines`). The number is part of the line, so any page cut from the file still
  shows where it is. Lines are counted at newlines only, as git and editors count them; a form
  feed no longer adds a line.
- [x] **Numbered diffs**: context and added lines carry their new-file numbers, and removed lines
  carry the tab alone (`number_diff_lines`). Hunk lengths from the `@@` headers decide where a
  hunk ends, so a removed line reading `--- x` is not taken for a file header.
- [x] **Split pages keep their header and overlap**: `split_review_pages` cuts each file block
  of a page into overlapping windows that repeat the `### File:` title and fence, or the diff
  preamble. A diff page cut mid-hunk ends its preamble at the first numbered line. Path, branch
  and PR reviews and the pipeline's re-split share one windowing helper, and a single-file path
  review is paged like a directory's files.
- [x] **The verifier sees the numbers**: the excerpt for a finding is found by line number across
  every part of its file, and one path's lines are never mixed with another file sharing its name.
  The orchestrated verifier reads the whole file numbered.
- [x] **Prompts cite the numbers**: the code, configuration and documentation review prompts and the
  paginated protocol tell personas to cite the shown numbers and never copy them into code or a
  fix; the verifier checks a finding's lines against them.
- [x] **Contract grounding reads through the numbers**: imports are taken from page text with the
  number column stripped (`strip_line_numbers`).
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_page_line_numbers.py`:
    - numbering of source and diff lines, including a removed `---` line and form feeds;
    - stripping back to the original text;
    - every line of every part carries its own file number, and the #415 defect at line 248
      appears as `248` in a later part;
    - parts overlap and cover the file, for the first split and the pipeline's re-split, which
      repeats header and fence;
    - split diffs keep numbers and preamble;
    - the verifier excerpt is found by number in a later part, still counts unnumbered code, and
      does not mix same-named files;
    - imports are found through the numbers;
    - every page prompt asks for the numbers.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

The #415 corpus (seed 1, 10 injected defects, 10 files, 2,796 lines), reviewed with all personas
before and after on the same gateway:

| | Before | After |
| :--- | ---: | ---: |
| Injections found | 7 | 7 |
| Found at their line | 4 | 7 |
| Still reported after verification | 6 | 6 |
| Prompt tokens, whole review | 505,376 | 520,891 (+3.1%) |
| Prompt tokens, persona review | 453,908 | 446,487 |
| Prompt tokens, verification | 51,468 | 74,404 |

Where the matched findings were reported, for the injections found by content:

| Injection | Before | After |
| :--- | :--- | :--- |
| `crypto/known_hosts.py:248` | 127-130, 154-156 | 248-250 |
| `core/repo.py:250` | 100-101, 106-110 | 245-250 |
| `security/suppression.py:200` | 140-147 | 186-217, 201-217 |
| `core/audit.py:95` | 58-78 | 89-95 |

Two baseline findings had a class method for a location and no file; none did after.

The numbers add 14.5% to the source text itself (3,303 tokens over 2,796 lines, `o200k_base`),
about 1.2 tokens a line. Source text is a minority of each prompt, and the whole review rose 3.1%.
Verification rose more: it now reads the numbered file, and that run had 78 candidates to check
against 41. Candidate and reported counts vary widely between runs of the same corpus (41 to 80
candidates across this release's runs), so the rise in reported findings beyond the injections
(24 to 37) is not attributed to numbering.
