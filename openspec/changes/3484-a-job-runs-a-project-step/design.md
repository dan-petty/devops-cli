# Design

## Decisions

- **Declare the steps in `.devops/roadmap.toml` on the default branch.**: The file follows the form of `trusted_config`: a git read of a ref, None when absent. The default branch decides, so an agent cannot add or remove a step in its checkout. `.devops/` already holds the per-repository files of devops-cli.
- **A missing file or key means skip.**: A target repository declares what devops-cli may do in it. This is the safe default for a repository that does not know devops-cli.
- **Gate the step. Do not change the docs path.**: A correct path would write the command reference of devops-cli into a target repository.
- **One predicate, `_runs(step)`, for the docs step and the archive step.**: `_finish_change` and `_scoped_rounds` both reach `_generate_docs`, so one gate there covers both. The predicate records a skipped step once for the comment.
- **A target without the archive step is ready with an unarchived change.**: `ChangeFacts.archive_required` is false then. The check for unticked tasks stays.
- **A new class `read_only_path` with the action `wait`.**: A new attempt or a new image writes to the same path. The table `ACTION_BY_CLASS` already decides which classes the rule `digest` clears, so no edit to `stop_clear.py` is needed.
- **A file that is not valid raises `ConfigurationError`.**: The job stops the item with the path in the reason, and runs no step. A wrong declaration must not turn into a silent skip.

## Rejected alternatives

- **A list in `service.repos`.**: The issue forbids it, and the Service holds the list, not the target repository.
- **Read the file of the checkout.**: An agent can edit it.
- **`.github/roadmap.toml`.**: The file does not exist, and `.github/` belongs to GitHub features.
- **Fail the job when the declaration is absent.**: It repeats the stop of the issue.
- **Reuse `ci_infra` for the read-only stop.**: Its action is `retry`, and the rule `digest` then clears the stop on each new image.
