# Proposal: #1643

## Why

The `service` stage of `Dockerfile` uses `python:3.14-slim-trixie`, while `.devcontainer/Dockerfile` uses `debian:sid`. Tests in the devcontainer run on `sid`, and CI `test-shard` runs on `ubuntu-26.04` with a standalone `uv` Python build. Neither environment runs the test suite against the Debian `trixie` userland, interpreter path, or non-editable `/app/.venv` wheel of the shipped service image. The repository owner selected Direction B on #1643: keep `python:3.14-slim-trixie` in `Dockerfile` and run the test suite inside the built service image in CI. Closes #1643.

## What Changes

- Add the sharded CI job `service-image-test` in `.github/workflows/ci.yml` to build `./Dockerfile` (`target: service`) and run the test suite inside `devops-cli-service:local` across 6 shards.
- Add Debian base-image alignment invariants and mutation tests in `tests/invariants/test_architectural_invariants.py` (`-k debian`) across `Dockerfile`, `.devcontainer/Dockerfile`, and `.github/workflows/ci.yml`.
- Register the new CI steps and job contract assertions in `tests/commands/test_ci.py`.
- Fix five host-layout and editable-install assumptions in `tests/sandbox/test_host_sandbox.py`, `tests/support/git_recording.py`, `tests/docs/test_docs_source_argv_collector.py`, `tests/docs/test_docs.py`, and `tests/ai/test_run_store.py` uncovered inside `devops-cli-service:local`.
- No internal product code is deleted. The change alters only CI workflows and tests, which no consumer observes, so `.openspec.yaml` sets `skip_specs: true`.
- The change fits one pull request.

## Capabilities

None (`skip_specs: true`: CI workflow and test-only change).

## Impact

- Pull requests that change paths outside an active plan folder run all 6 shards of `pytest` inside `devops-cli-service:local` on Debian `trixie`.
- `tests/invariants/test_architectural_invariants.py` fails offline if `Dockerfile` or `.devcontainer/Dockerfile` stages drift or if their Debian releases differ without the CI service-image test job.
- The shipped `service` stage keeps its minimal package set (`no uv`, `no gcc`, `no pytest`) and its `USER 1000:1000` read-only security posture.

## Feasibility

- Confirmed on 2026-11-10 against Docker Engine and `Dockerfile`: `docker build -t devops-cli-service:local .` exits `0` and builds `Python 3.14.8` on `VERSION_CODENAME=trixie`.
- Confirmed Direction A fails the security gate: Debian `trixie` ships `python3.13` only, and Trivy `0.75.0` reports `0` advisories on `debian:sid` (`trixie` reports real CVEs).
- Confirmed `tests/test_architectural_invariants.py` moved to `tests/invariants/test_architectural_invariants.py` in #2167.
- Confirmed by running all 4 shards (~22,491 tests) inside `devops-cli-service:local` with locked dev packages mounted read-only, `kubectl` and `promtool` mounted read-only, and `-o pythonpath=`.
- That container run exposed five host-only test assumptions (`/usr/bin/python3`, ambient `jq`, username `devops` in `host_data_in`, and editable `src/` paths in docs and `run_store` tests).

## Existing Tool Considered

`docker/build-push-action` (v6), `docker run`, `uv export --locked --only-dev`, `uv pip install --target --require-hashes`, `devops install-tools`, and `pytest-xdist` cover the CI container test execution. `tests.support.dockerfile.stages` and `PyYAML` cover the offline Dockerfile and workflow invariant checks without adding a library or custom parser. Internal code deleted: none.
