# Design

## Where the versions live

The project pins its Python runtime version in `.python-version`.
The CI setup toolchain composite action in `.github/actions/setup-toolchain/action.yml` pins the `uv` toolchain version.
`uv 0.13.5` supports downloading managed `cpython-3.14.9` standalone distributions.

## Rejected alternatives

- **Keep uv 0.12.16 in CI**: Fails because uv 0.12.16 has no downloads for Python 3.14.9.
- **Update to Python 3.14.10**: Rejected because no released version of `uv` includes Python 3.14.10 downloads yet.

## Test

The unit tests in `tests/test_uv.py` verify that `devops uv` subcommands resolve the pinned `.python-version` file properly.
Full `devops ci` quality gates verify runtime compatibility.
