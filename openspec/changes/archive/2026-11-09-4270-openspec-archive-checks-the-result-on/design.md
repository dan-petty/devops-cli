# Design

## Decisions

- Check the disk, not the output of the tool. The failure is that the process did not run or did not move the folder, so only the folders can prove the result.
- Take the archive folders that match `<date>-<change>` before the run and after it. A new name after the run proves this run made it. An older archive of the same name does not hide a run that moved nothing.
- Raise one `ToolExecutionError` per failed check with its own message: the source folder that is still there, or the missing archive folder. The check runs before the validation, so a validation never reports on a tree that was not archived.
- A dry run is handled in the command, before `isolated_openspec` starts. The command lists the two commands with `render_request_plan` and starts no process. The class stays `no-external-request`, as for `openspec new`, because the command declares `--dry-run` and the proxy forwards it.
- The fake `openspec` moves the folder only for a recorded run that succeeds, using the folder name that the recorded output gives. A scripted run moves nothing unless the test passes an `effect`.

## Rejected alternatives

- Read the path from `openspec archive --json`. It changes the failure output and the recorded runs, and it still needs the disk check.
- Make `run_subprocess` refuse to plan a command that has a visible effect. This changes every caller for one command.
- Leave the dry run to run the command normally. A dry run must make no change.
