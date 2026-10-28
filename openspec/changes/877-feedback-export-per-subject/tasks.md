# Tasks

## 1. The export counts each subject once and keeps every human verdict

- [x] Add failing tests: three sessions of one subject export each finding once; human verdicts from different sessions of a subject are all exported; the newer of two human verdicts on one finding is exported; the status filter reads that verdict; sessions without a subject export all their findings; a later session of an exported subject appends nothing; `devops review export-feedback` prints the count of each subject's findings; a finding without a fingerprint v2 is not matched across sessions
  - Verification: `uv run devops ci test tests/test_review_exporter.py`
- [x] Group sessions by subject key, keep one copy of each finding by fingerprint v2 in the order of a person's newest verdict and then the history rank of its session, filter by the kept verdict, and add `subject_key` and `fingerprint_v2` to `FeedbackRecord` and its dataset identity
  - Verification: `uv run devops ci test tests/test_review_exporter.py tests/test_review_adjudication.py tests/test_review.py`
- [x] Describe the export in the command help, `docs/SELF_IMPROVEMENT.md` and the code review task of the knowledge base, and regenerate the documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 2. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 877-feedback-export-per-subject`

## Workflow follow-up

- A person's VERIFIED verdict sets the admitted finding's stored state to CONFIRMED: #2414.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
