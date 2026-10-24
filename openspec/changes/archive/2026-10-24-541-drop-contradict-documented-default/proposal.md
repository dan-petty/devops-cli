# Proposal

## Why

Issue #541 shows that `contradict-documented-default` mutates documentation prose defaults that no review tool can detect. ADR 0005 places defects that no tool or rule can express out of scope.

## What Changes

- Delete the `contradict-documented-default` template, finder function, and regex definitions.
- Delete test cases for `contradict-documented-default` in `tests/test_review_defects_infra.py`.
- Update `test_a_corpus_of_infrastructure_and_docs_records_each_injection` to use `widen-file-mode` on a fenced code block instead of `contradict-documented-default`.
- Add a test that verifies `select_templates(["contradict-documented-default"])` raises `ValueError`.
- Remove `contradict-documented-default` from the table in `docs/SELF_IMPROVEMENT.md`.
- This change alters no behavior that a consumer observes outside synthetic corpus generation. The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- `src/devops_cli/ai/review/defects.py`: deletes `_DOCUMENTED_DEFAULT`, `_OPPOSITES`, `_contradict_defaults`, and the template entry.
- `tests/test_review_defects.py`: adds rejection test for the deleted template name.
- `tests/test_review_defects_infra.py`: deletes obsolete test cases and updates corpus test.
- `docs/SELF_IMPROVEMENT.md`: removes the template row.

## Feasibility

- Read `src/devops_cli/ai/review/defects.py` lines 871-890 and lines 1226-1231. The regex `_DOCUMENTED_DEFAULT`, dictionary `_OPPOSITES`, and function `_contradict_defaults` exist only for this template.
- Read `tests/test_review_defects_infra.py` lines 223-236, 332, and 365. The test cases verify prose mutations from `_contradict_defaults`.
- Read `docs/SELF_IMPROVEMENT.md` line 683. The template is listed with scope `docs`.
- Verified ADR 0005 (`docs/adr/0005-review-findings-come-from-tools-not-models.md:51`), which excludes prose claims from review findings without tool support.

## Existing Tool Considered

This change deletes dead code and adds no new mechanism. The synthetic defect corpus uses the internal template list in `defects.py`. No external tool replaces this internal template.

Deleted internal code:
- `_DOCUMENTED_DEFAULT` regex in `src/devops_cli/ai/review/defects.py`
- `_OPPOSITES` dictionary in `src/devops_cli/ai/review/defects.py`
- `_contradict_defaults` function in `src/devops_cli/ai/review/defects.py`
- `contradict-documented-default` entry in `TEMPLATES` in `src/devops_cli/ai/review/defects.py`
