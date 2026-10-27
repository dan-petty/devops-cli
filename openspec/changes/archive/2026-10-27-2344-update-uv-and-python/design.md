# Design

## Where the versions live

`.python-version` pins the Python runtime. uv is pinned in three places: the `version` input in `.github/actions/setup-toolchain/action.yml`, the `FROM` line of the `Dockerfile` (tag and digest) and the `COPY --from` line of `.devcontainer/Dockerfile`.

## Rejected alternatives

- **Keep uv 0.12.23 in the images**: Fails because uv 0.12.23 has no download for Python 3.14.10, and the pins would stay different from CI.
- **Leave the `python:3.14-slim-trixie` image digest as it is**: The image builds its own Python and is outside this change.

## Test

`tests/test_uv.py` checks that `devops uv` reads the `.python-version` file. The full `devops ci` gates check the runtime.
