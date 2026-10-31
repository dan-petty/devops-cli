# Tasks

## 1. Write Failing Test
- [x] Add failing tests for `scope/git` declaration and application in `tests/test_pr_title_labels.py` <!-- id: 1-failing-test -->
- [x] Verify test fails against current `origin/main` <!-- id: 1-verify-fail -->

## 2. Declare Label
- [x] Add `scope/git` entry to `.github/labels.yml` after `scope/github` <!-- id: 2-add-label -->
- [x] Verify test passes <!-- id: 2-verify-pass -->

## 3. Verification & PR
- [x] Run `devops ci fail-to-pass --base origin/main` <!-- id: 3-fail-to-pass -->
- [x] Run fast checks, archive change, and open draft PR <!-- id: 3-pr -->
- [x] Monitor checks and mark PR ready <!-- id: 3-ready -->
