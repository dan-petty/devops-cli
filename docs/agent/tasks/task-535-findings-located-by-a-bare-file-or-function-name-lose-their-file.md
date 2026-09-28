# Task 535: Findings Located by a Bare File or Function Name Lose Their File

**Issue**: [#535](https://github.com/dan-petty/devops-cli/issues/535)
**Status**: Done
**Milestone**: `v0.2.23`
**Priority**: `priority/p1-high`
**Scope**: `type/bug`, `scope/review`, `priority/p1-high`

---

## 1. Description & Objectives

The first run of `devops review samples validate --review` (#505) found 36 of 208 candidate
findings with a location naming no directory:
- a bare file name: `flag_groups.go:111-116`, `read.rs:905-906`, `Dockerfile:7`;
- a function name: `getBodySize:18-24`, `nvm_alias_path() { 1368-1374`.

The review knows the file of the page each finding came from, but kept the model's text, so:
- a reader of `Dockerfile:7` could not tell which Dockerfile was meant;
- corpus scoring could not match the finding;
- deterministic checks that read the file at the location could not run.

Resolving bare file names alone raised that run from 28 to 33 injections found, and from 22 to 24
reported, of 109.

### Key Deliverables Completed:

- [x] **`anchor_location(location, file_path, page_text)`** (`review_schema.py`) ties a location
  that names no directory to the file under review, keeping its lines or target, when it names:
  - that file, case-insensitively (`Dockerfile:7`, `read.rs`);
  - or a symbol the page shows (`getBodySize:18-24`, `nvm_alias_path() { 1368-1374`).

  A bare name with an extension that is not this file's (`config.yaml:3`) may be another file, so
  it is left alone, and so is a symbol the page never shows. A location with a directory is never
  changed.
- [x] **The per-file review anchors each page's findings** (`_anchor_page_findings` in
  `pipeline.py`) as the page's reply is read. Locations it cannot tie to the file are kept and
  listed in the payload's `unanchored_locations`, so they are counted, not silently rewritten.
  The ones it ties are listed as the model wrote them in `anchored_locations`.
- [x] **Automated Tests & Quality Gates**:
  - `tests/test_review_location_anchoring.py`:
    - bare file names with lines, a different case, no lines, symbol names with a colon or a
      spaced range, and an empty location;
    - left alone: a path, another file named on the page, a symbol the page lacks;
    - a page review whose reply mixes an anchored and an unanchored location.
  - 100% passing status across Gated CI validation suite (`uv run devops ci`).

## 2. Verification on a Live Cluster

`devops review samples validate --review -c csharp-dotnet -c go -c kubernetes-helm -c rust`, the
categories where the first run (#505) had bare locations:

| Category | Candidates | Anchored | Unanchored | Without a directory |
| :--- | ---: | ---: | ---: | ---: |
| C#/.NET | 16 | 12 | 0 | 0 |
| Go | 5 | 2 | 0 | 0 |
| Kubernetes/Helm | 30 | 5 | 0 | 0 |
| Rust | 24 | 2 | 0 | 0 |

The model still writes bare names: 21 of 75 candidates (28%) were anchored, e.g.
`PropertyValueConverter.cs:101-102` and `redis-replica-controller.yaml:19`. None is left without
its file, where the first run had 36 of 208 (17%).
