# Design

## Decisions

- **Put both tests in `tests/roadmap/test_roadmap_implement_job.py`, beside the #3319 test.** The guard is one function, `_delivery_title`, and its tests belong in the module that already holds the refused-title test, so a reader sees every case together and no new module mirrors one helper.
- **Use `planned_world` for the first-push case and assert that `origin` holds no branch, not that the job deletes one.** `_publish` calls `_delivery_title` before `_push`, so a refused title stops the item before the branch reaches `origin`; a deletion assertion would describe code that no longer exists.
- **Set `skip_specs: true` and write no spec delta.** The change adds tests for behavior that `openspec/specs/roadmap-implement-job/spec.md` already states in the requirement `The pull request that delivers the code has the type of the issue`, and a test changes no behavior that a consumer observes.

## Rejected alternatives

- **Keep the planned `specs/roadmap-implement-job/spec.md` delta.** The base spec already holds the requirement, and an ADDED requirement with the same behavior would state one behavior twice.
- **Guard inside `delivery_title` in `src/devops_cli/roadmap/stage_change.py`.** That function is a pure builder that the stage tests call, and `_delivery_title` already holds the stop and the message.
- **Write the title and let the `Semantic PR title` check fail.** The check runs after the job has pushed a branch and spent tokens.
- **Assert a branch deletion after the first push.** `_publish` checks the title before the push, so there is no branch to delete.
- **Create the module that the issue names, `tests/roadmap/test_roadmap_implement.py`.** No commit ever held it, and the implement tests are split by subject.
