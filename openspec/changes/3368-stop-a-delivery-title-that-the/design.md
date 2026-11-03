# Design

## Decisions

- **Run the guard in `_publish` and in `_pull_request`, right after the delivery title is built.**: Those two methods are the only places that write the delivery title to GitHub, and the job owns the stop and the cleanup.
- **Stop the item with the reported problems and the issue title, and write no title.**: A refused title fails the required `Semantic PR title` check after the job has spent tokens, and a repair needs another model step.
- **On a first push, delete the branch with the cleanup that `_publish` already runs when GitHub refuses the draft.**: One cleanup path keeps `origin` free of a branch that has no pull request, and it adds no new deletion code.
- **Add the two tests in a new module `tests/roadmap/test_roadmap_implement_title.py`.**: The issue names `tests/roadmap/test_roadmap_implement.py`, which no commit ever held, and a new test module sits in the folder that mirrors `src/devops_cli/roadmap/`.

## Rejected alternatives

- **Guard inside `delivery_title` in `src/devops_cli/roadmap/stage_change.py`.**: `delivery_title` is a pure builder that the stage tests call, so a stop and a branch deletion inside it would mix construction with job cleanup.
- **Guard inside `create_draft_pull` and `update_pull` in `src/devops_cli/github/client.py`.**: The client is shared with the stage job and `devops pr create`, so it must not hold the project's title rules.
- **Write the title and let the `Semantic PR title` check fail.**: The check runs after the job has pushed a branch and spent tokens, and the draft and the branch stay.
- **Repair the title in a later step.**: A repair needs another model call and does not remove the failed check of the first write.
- **Create the test module that the issue names, `tests/roadmap/test_roadmap_implement.py`.**: The probe says the path is no file of the staging commit and that no commit in the history deleted or renamed it, and the implement tests are split into modules such as `tests/roadmap/test_roadmap_implement_pull.py`.
