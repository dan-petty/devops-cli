# Design

## Decisions

- One flag decides both lock rules: `locked` is true only for the new branch of a Planned item. Then uv runs `--locked` and npm runs `npm ci`; else uv locks again and npm runs `npm install`, as `uv run` and `npm install` do in the devcontainer.
- The seed hash covers `uv.lock` only, so the offline sync runs only with `--locked`, where a stale lock fails anyway. Without it, the seed still fills the cache, so a current lock installs from the cache.

## Rejected alternatives

- Hash `pyproject.toml` into the seed too: #4814 builds the seed, and the bootstrap would still need an online path for a branch that changes `pyproject.toml`.
