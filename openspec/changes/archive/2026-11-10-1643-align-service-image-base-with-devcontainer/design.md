# Design

## Decisions

- Keep `Dockerfile` on `python:3.14-slim-trixie` and `.devcontainer/Dockerfile` on `debian:sid` (Direction B chosen by the repository owner on #1643).
- Leave the shipped `service` stage of `Dockerfile` unchanged so it ships without `uv`, `gcc`, `pytest`, `jq`, or dev packages.
- Mount locked dev-only site-packages (`uv export --locked --only-dev --no-emit-project --no-editable` installed with `--require-hashes` against `/app/.venv/bin/python`) and pinned `promtool` and `kubectl` read-only at test time.
- Run `pytest` inside `devops-cli-service:local` with `-o pythonpath=`, `--init`, `--read-only`, `--cap-drop ALL`, `--security-opt no-new-privileges`, a container-owned `/workspace` copy excluding `.venv`, and disk-backed `/tmp`.
- Assert inside each shard before `pytest` starts that `/etc/os-release` names `VERSION_CODENAME=trixie` and `devops_cli.__file__` resolves under `/app/.venv/`.
- Shard `service-image-test` into 6 parallel shards (`--no-cov`) with `cache-from: type=gha` and no `cache-to:` export so each shard finishes within the 300-second budget.
- Enforce the Debian release invariant in `tests/invariants/test_architectural_invariants.py` (`-k debian`): stages inside each Dockerfile agree, and cross-Dockerfile release divergence requires `service-image-test` in `.github/workflows/ci.yml`.

## Rejected alternatives

- Move `Dockerfile` onto `debian:sid` (Direction A). Rejected: Trivy `0.75.0` reports `0` vulnerability advisories for `debian:sid`, which blinds the `service-image` vulnerability gate, and `sid` carries rolling breakage risk.
- Move `.devcontainer/Dockerfile` onto `debian:trixie`. Rejected: Debian `trixie` `apt` provides `python3.13` (`3.13.5`) and has no `python3.14` package, while `pyproject.toml` requires `>=3.14`.
- Install `pytest` and dev dependencies into a new `Dockerfile` stage instead of running `devops-cli-service:local`. Rejected: #1643 requires building the service image and running the test suite inside that built service image.
- Run the full suite unsharded in one `service-image-test` runner. Rejected: one runner takes 355 to 528 seconds on the suite plus image build time, exceeding the 5-minute check budget in `AGENTS.md` rule 5.
- Mount `/tmp` as a small RAM `tmpfs` during container tests. Rejected: `promtool test rules` writes multi-hundred-megabyte WAL segments under `/tmp` and failed with `no space left on device` on a 512 MiB `tmpfs`.
