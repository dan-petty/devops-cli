# Design

## Decisions

- **Use `--tmpfs /home/devops:mode=1777`.** Docker gives `mode` to the kernel, and Podman accepts the `mode` mount option. Mode 1777 lets every user write the directory, and the sticky bit keeps each user's files safe from other users. Thus user 1000 can write its home under `--read-only`, on both engines.
- **Use one form for both engines.** Each smoke step keeps one `docker run` command, with no branch on the engine.
- **Keep a writable tmpfs home.** `--read-only` makes the `/home/devops` of the image read-only, and the probe runs as user 1000 and writes to its home.
- **Use the same form in `release.yml` and in `ci.yml`.** Both workflows run the same smoke commands, and `tests/commands/test_ci.py` and `tests/invariants/test_runner_image.py` compare them.
- **Keep `exec,size=3g`.** The `uv run` step of the runner image needs an executable home that can hold the project and its virtual environment.

## Rejected alternatives

- `uid=1000,gid=1000`: Podman 5.8.6 refuses `uid=1000` with `unknown mount option`.
- `U`: Podman accepts it, but Docker gives it to the kernel, which refuses it.
- No tmpfs option: the step then does not state the mode that user 1000 needs.
- An engine-conditional `docker run`: it adds a branch to each smoke step and two forms to keep the same.
