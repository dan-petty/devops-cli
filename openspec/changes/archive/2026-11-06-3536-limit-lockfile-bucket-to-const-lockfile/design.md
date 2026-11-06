# Design

## Decisions

- **Take the lockfile bucket from `CONST_LOCKFILE_NAMES` alone, with no suffix rule.**: The allowlist is the one place that names the files osv-scanner reads, and `OsvScanner` already judges a lockfile by it (#2131), so one rule decides both paths.
- **Apply the allowlist to the whole bucket, including the files that `_lockfiles_beside` adds.**: A file added beside a reviewed file reaches the same osv-scanner command, so a suffix check on the reviewed paths alone would leave a second way in.
- **Keep the regression test in `tests/security/test_review_pipeline_go.py`.**: That module already imports and tests `classify_scanner_files`, so the new case sits beside the cases it protects.
- **Add a requirement to the existing `review-tool-databases` capability.**: Its purpose covers which files the review names to osv-scanner, and its current requirement covers the `OsvScanner` scan and fetch only.

## Rejected alternatives

- **Keep the `.lock` and `.lockb` suffix test and filter the results later.**: The issue records that `osv-scanner scan source ... --lockfile uv.lock --lockfile src/devops_cli/review/rules/rules.lock` printed `could not determine extractor suitable to this file` and exited 127, so a later filter cannot undo the failed scan.
- **Detect lockfiles by reading their content.**: `src/devops_cli/security/osv_scanner.py:223:return path.name in CONST_LOCKFILE_NAMES` shows the repository already decides by name, and osv-scanner names its extractors by file name.
- **Add a separate test module for the classifier.**: `tests/security/test_review_pipeline_go.py:15:classify_scanner_files,` shows the existing module imports the classifier and tests it, so a new module would copy the setup.
