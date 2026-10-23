# Task: Review Pre-Analysis Reads Only the Files Under Review (#1919)

**Issue**: [#1919](https://github.com/dan-petty/devops-cli/issues/1919)
**Feasibility**: Verified against the code and by a measurement of the real branch review path (`_prepare_branch_content`, `review_worktrees_context`, `_execute_review_workflow` with `--pre-analysis-only`) on fixture repositories in a temporary directory, with no model and no cluster. On `origin/main`, a branch that changed 5 files of 500 analyzed all 500 files in 49 s, and 5 files of 2,339 analyzed all 2,339 files in 3 min 56 s. The per-file analysis takes about 12 ms. The `ReviewWorkerPool` rate limit for model calls (10 starts each second, `DEFAULT_REVIEW_RATE_LIMIT`) set the pace: 2,339 files at 10 each second is 234 s, which is the four minutes of the issue.

## Summary

Pre-analysis analyzed every file of the checkout, because it listed the target directory with `list_repo_files`. The runner now gives the stage the files under review, and the stage analyzes those files and no other file. The stage calls no model, so it now runs its file analysis on a thread pool with no rate limit for model calls. On the same fixtures, the review workflow takes 1.2 s for 5 changed files of 500, and 1.3 s for 5 changed files of 2,339. Three output lines also told the user wrong facts, and the profile line ended in a separator with nothing after it.

## Deliverables

- [x] `ReviewPipelineOrchestrator.run_pre_analysis_refresh` takes the files under review (`files`) and refreshes the metadata of those files only. A file whose content hash matches its cached metadata reuses that metadata.
- [x] `_execute_review_workflow` gives the stage the files of the review pages.
- [x] The stage analyzes its files on `ThreadPoolExecutor`, not on `ReviewWorkerPool` with its model-call rate limit. The worker count no longer depends on the Ollama endpoints, because the stage calls no model.
- [x] The stage summary line says how many files it analyzed and how many it reused from the cache. It no longer says "refreshed with AI metadata", as the stage uses no AI.
- [x] The session line says "without a model" when the review has no analysis client, not "via LLM server".
- [x] The line "Content spans N pages to ensure full coverage" is removed. Each page is one file, and the session line already gives the file count.
- [x] The profile line no longer ends in "; " when no stage took a second.
- [x] `docs/SELF_IMPROVEMENT.md` and the knowledge base page `ai_code_review.md` say that pre-analysis reads only the files under review and calls no model.
- [x] `tests/ai/review/test_pre_analysis_scope.py` shows that the stage returns and caches only the files under review, counts analyzed and reused files, and never waits on a rate limit. `tests/commands/test_review_pre_analysis_only.py` drives `devops review branch --pre-analysis-only` and checks the files and the output lines.
- Linked files in each review payload now come from the other files under review, not from the whole checkout. No reader of the session uses `linked_files` today.
