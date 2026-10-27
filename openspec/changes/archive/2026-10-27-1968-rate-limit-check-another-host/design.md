# Design

`run_gh` decides `reads_quota` from `_prints_rate_limit_answer`.
That function checks the host from `GhApiArgs.hostname`.
It returns false when the hostname is set and differs from `CONST_GITHUB_HOST`.
With `reads_quota` false, `_post_process_run` stores no quota from the answer.
The github.com quotas stay unchanged.

The rate-limit check still executes and remains exempt from pacing.
It consumes no quota on either host.
Only quota storage behavior changes.

## Rejected alternatives

- **Reject any explicit `--hostname` flag**: This rejects checks that name `github.com` explicitly. It hides the real rule that the answer must belong to the paced host. Rejected.
- **Key stored quotas by host**: This adds a multi-host quota storage system that no consumer needs. Only `github.com` requests are paced by devops-cli. Rejected.
