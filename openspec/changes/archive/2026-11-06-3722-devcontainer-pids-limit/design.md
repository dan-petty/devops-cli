# Design

## Decisions

- **Set `--pids-limit=8192` as one `runArgs` element.**: A burst of 98 searches used about 1,600 slots on top of a base of 600 to 1,000, and the old limit of 2048 filled. 8192 leaves a margin of about four times the largest burst, and the test minimum of 4096 is twice the old limit.
- **Add no comment to `devcontainer.json`.**: The file is JSONC, but two tests read it with `json.loads`, which refuses comments. `CONTRIBUTING.md` holds the measure.
- **Put the guard in `tests/invariants/test_devcontainer_config.py`.**: The module already reads the committed files of `.devcontainer/`. The `devops devcontainer validate` command checks the schema of a manifest and reads no run argument.
- **Add `--pids-limit` to the workspace file only.**: `.devcontainer/image/devcontainer.json` holds no `runArgs`, and the template for other repositories is out of the scope of the issue.

## Rejected alternatives

- **Add `files.watcherExclude` for `.data`.**: The issue comment asks for a measure first, and no measure exists: 40 small files under `.data` did not reproduce the scans on an idle host. No run shows that the setting stops the scans, so the setting stays out.
- **Move the agent worktrees out of the workspace folder.**: It changes the layout of every agent job, and a person decides it.
