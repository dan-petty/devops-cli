# Design

## Decisions
- The code's git gets the same isolation as the git that builds the repository: `GIT_CONFIG_NOSYSTEM=1` and `GIT_CONFIG_GLOBAL=os.devnull`. Then no host file changes a recording.
- The three new tests lock the behavior: the environment, the recorded complexity fact, and the idempotence of the recorder.

## Rejected alternatives
- Record again on each host: the file would differ between the devcontainer, the runner image and CI, so the `git` row would fail on one of them.
- Record inside the container image only: the devcontainer and the runner image still record on their own hosts, so the drift stays.
- Change the code to give the recorded commands: no source shows that the code is wrong, and the recorded order does not match the code.
