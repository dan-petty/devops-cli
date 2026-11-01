# Tasks

## 1. Optimize Tests & Coverage job and extend job-time window

Reads: none. Changes: `.github/workflows/ci.yml`.

- [ ] 1.1 Set `save-uv-cache` to `true` in the test job setup-toolchain step. Remove `--no-cache` from the test command. Add a pytest-xdist worker count to split the suite across parallel workers. Update the `job-time` step to pass a 20-run window flag to `devops ci job-time`. Record the step times of one slow run and one fast run in issue #3050, naming the difference, and verify that `actionlint .github/workflows/ci.yml` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
