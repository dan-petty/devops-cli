# Design

## Decisions
- Turn the tasks off in two places: the self-hosted `allowedCommands` (a repository cannot add a task back) and the repository config (no task is asked for), so no run logs a refused task.
- Name the commands in `prBodyNotes`, so the person or the fix job that completes the pull request knows them.

## Rejected alternatives
- Keep the tasks on: a task runs in the container that can read the installation token, which can write to each repository of the installation (#6020).
- Wait for #6020: the owner chose to open update pull requests now.
