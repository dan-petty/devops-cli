# Proposal

## Why

#3536 reports that `classify_scanner_files` in `src/devops_cli/ai/review/pipeline.py` puts every file that ends in `.lock` or `.lockb` in the lockfile bucket, and the review hands that bucket to osv-scanner as `--lockfile` arguments. osv-scanner reads no such file and stops, so a review that covers `rules.lock` reports a failed scan and loses the advisories of the real lockfiles.

## What Changes

- `classify_scanner_files` in `src/devops_cli/ai/review/pipeline.py` keeps a file in the lockfile bucket only when its name is in `CONST_LOCKFILE_NAMES`, and drops the `.lock` and `.lockb` suffix test.
- `_lockfiles_beside` in `src/devops_cli/ai/review/pipeline.py` adds only files whose name is in `CONST_LOCKFILE_NAMES`, so no other path reaches the lockfile bucket.
- `tests/security/test_review_pipeline_go.py` gains a test that classifies `rules.lock`, `tools.lock` and `uv.lock` and asserts that the bucket holds `uv.lock` alone.
- The `review-tool-databases` spec gains a requirement that the review lockfile bucket holds only known lockfile names, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `review-tool-databases`: The review lockfile bucket holds known lockfile names only

## Impact

- Code: `src/devops_cli/ai/review/pipeline.py`
- Tests: `tests/security/test_review_pipeline_go.py`

## Feasibility

- The probes name the cited paths at the staging commit, word for word: "The path `src/devops_cli/ai/review/pipeline.py` is a file of the staging commit." They also say "The path `src/devops_cli/review/rules/rules.lock` is a file of the staging commit." and "The path `uv.lock` is a file of the staging commit."
- `search_code` for `classify_scanner_files` showed the classifier as `src/devops_cli/ai/review/pipeline.py:1614:def classify_scanner_files(`. It is a public name, and the issue writes the old private name.
- `read_file` of `src/devops_cli/ai/review/pipeline.py` lines 1595-1675 showed the suffix rule and the allowlist test on one line: `src/devops_cli/ai/review/pipeline.py:1646:if (p.name in CONST_LOCKFILE_NAMES or p.suffix in (".lock", ".lockb"))`. The allowlist is already imported at `src/devops_cli/ai/review/pipeline.py:74:CONST_LOCKFILE_NAMES,`, so only the suffix branch has to go.
- `search_code` for `CONST_LOCKFILE_NAMES` showed the list at `src/devops_cli/config/constants.py:4920:CONST_LOCKFILE_NAMES: Final[tuple[str, ...]] = (` and showed that `OsvScanner` judges a lockfile by name alone: `src/devops_cli/security/osv_scanner.py:223:return path.name in CONST_LOCKFILE_NAMES`.
- `read_file` of `tests/security/test_review_pipeline_go.py` showed the module imports the classifier at `tests/security/test_review_pipeline_go.py:15:classify_scanner_files,` and tests it in `tests/security/test_review_pipeline_go.py:35:def test_classify_scanner_files_classifies_go_files(tmp_path: Path) -> None:`, so the regression test fits there.
- `read_file` of the classifier showed `_lockfiles_beside` fills the bucket from `CONST_REVIEW_GENERATED_FILES` at `src/devops_cli/ai/review/pipeline.py:358:{d / name for d in dirs for name in CONST_REVIEW_GENERATED_FILES if (d / name).is_file()}`. That set is a size filter, not the osv-scanner allowlist, so the whole bucket needs the allowlist filter.
- First checks against the real system: `uv run devops ci test tests/security/test_review_pipeline_go.py`, then `uv run devops openspec check`, then `uv run devops review --target .` on a tree that holds `src/devops_cli/review/rules/rules.lock` to read the osv-scanner row of the coverage matrix.

## Existing Tool Considered

osv-scanner 2.6.0, already pinned in `src/devops_cli/tools_lock/tools.lock`, scans the lockfiles it reads, and `CONST_LOCKFILE_NAMES` in `src/devops_cli/config/constants.py` is the maintained allowlist of those names. `OsvScanner` already uses that list through `_is_lockfile`. The change reuses the list in the review classifier and adds no scanner.

## Dependencies

None.
