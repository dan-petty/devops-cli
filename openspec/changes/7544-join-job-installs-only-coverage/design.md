# Design

## Decisions

- **A dependency group of its own.** The pins of coverage and diff-cover stay in `pyproject.toml` and `uv.lock`, and Renovate updates them there. The `dev` group includes the group with `{include-group = "coverage"}`, so `uv sync`, `uv sync --all-groups` and `uv export --group dev` of the `Dockerfile` give the same packages as before.
- **An input of `setup-toolchain`, not a second setup.** The pins of uv and Python stay in one action, which every quality-gate job shares. An empty `dependency-group` keeps the full sync of every other caller.
- **`UV_NO_SYNC` for the whole job.** A plain `uv run` syncs the project and the default group `dev`, which would install the full toolchain again. The job sets `UV_NO_SYNC: "1"`, so the commands of the job stay as the spec `ci-coverage-reports` names them (`uv run coverage xml`).
- **No bytecode compile.** The job runs four commands one time each, so a compile of all files costs more than it saves.

## Rejected alternatives

- **`uv tool run --from coverage==7.17.5` or `uvx coverage==7.17.5` in the workflow.** The workflow would hold a second copy of the pin of `uv.lock`. The owner rule is that a pin lives only in the manifest of its package manager.
- **`uv sync --only-group dev`.** The `dev` group holds 27 direct pins, such as mypy, ruff, zizmor, mutmut and hypothesis, which the job does not run.
- **`uv run --no-sync` in each command.** It changes the commands that the spec `ci-coverage-reports` names (`openspec/specs/ci-coverage-reports/spec.md:23`) for the same effect as the job variable.
