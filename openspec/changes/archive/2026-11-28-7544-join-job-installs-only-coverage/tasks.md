# Tasks

## 1. The coverage group

Kind: other.

Changes: `pyproject.toml`, `uv.lock`.

- [x] 1.1 Add the dependency group `coverage` with coverage and diff-cover, include it in `dev`, and lock.
  - Verification: `$ uv lock --check`

## 2. The join job installs only the group

Kind: other.

Changes: `.github/actions/setup-toolchain/action.yml`, `.github/workflows/ci.yml`.

- [x] 2.1 Add the input `dependency-group` to `setup-toolchain`. The join job installs only `coverage`, with no bytecode compile and no tooling cache, and sets `UV_NO_SYNC`.
  - Verification: `$ uv run devops ci --check --only actionlint,zizmor`

## 3. Documents

Kind: other.

Changes: `docs/SDLC.md`.

- [x] 3.1 Name the group `coverage` in the paragraph of the required check of `docs/SDLC.md`.
  - Verification: `$ uv run devops ci --check --only docs`
