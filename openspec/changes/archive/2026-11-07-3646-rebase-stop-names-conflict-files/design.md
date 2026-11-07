# Design

## Decisions

- `_sync` reads the list before `git rebase --abort`, with `run_subprocess` and `check=False`, in the worktree. Git holds the unmerged paths only until the abort. A failed read gives an empty list, and the stop still happens with the git text.
- The command uses `-z`, so a path with a space or a quote reaches the job whole. Each path goes through `mask_secrets` and `shown`, so a secret or a control character does not leave the job.
- `_StopError` gets a field `conflict_files`. The stop writes the field to the new record key `implement.conflict` as JSON, or clears the key when the field is empty. A retry clears the key in `_start`, with the other marks of the stop.
- The stop passes `FailureClass.CONFLICT` itself. The site knows its cause, and a file name must not change the class.
- The limit is the existing `CONST_ROADMAP_IMPLEMENT_REASON_PATHS`. Its comment already names it as the limit of the paths that a reason of a stop names.

## Rejected alternatives

- Read the files after the abort. The abort clears the conflict, so `git diff --diff-filter=U` returns nothing.
- Make `git_message` read stdout. Git does not promise the text of its output, and other callers expect the error text.
- Keep the files only in the comment. The job cannot read a comment back as a record.
- Cut the reason by characters. A path would be cut in the middle, and the reader would not learn that files were left out.
