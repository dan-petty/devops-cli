# Design

## Context

GitHub Pages builds the documentation site from `main:/docs` with the legacy builder. The builder runs `github-pages build --source <docs> --destination <site>`, so Jekyll reads `docs/_config.yml` only. The `Docs Site Build` job of `.github/workflows/ci.yml` runs the same builder image offline on each pull request that changes `docs/`. See `proposal.md` for the evidence.

## Goals / Non-Goals

**Goals:**

- One file holds the site settings, and it is the file that the Pages build reads.
- `devops gh pages verify` checks that file.
- The offline build of the `Docs Site Build` job makes the same links as the published site.

**Non-Goals:**

- Change the layout, the navigation links or the pages of the site.
- Change the Pages source or the build type. These are repository settings, which only a person changes.

## Decisions

### 1. Move the settings into docs/_config.yml and delete the second file

`docs/_config.yml` gets `title`, `description`, `url`, `baseurl`, `repository`, `markdown`, `kramdown`, `plugins` and `defaults`, and keeps `exclude: [agent/]`.

- **Rejected alternative: add the second file to the build with `--config`.** The legacy Pages build has no setting for a configuration file: `entrypoint.sh` of `actions/jekyll-build-pages` v1.0.13 passes `--source` and `--destination` only, and the `build` command of the `github-pages` gem has no `--config` option. A custom Actions workflow could pass the option, but that changes the Pages build type, which is a repository setting, and it keeps two files.
- **Rejected alternative: let `devops gh pages verify` read both files.** The check then passes on settings that the site does not use, which is the defect of #2001.

### 2. Keep url and baseurl in the file

`jekyll-github-metadata` sets `url` and `baseurl` in the Pages build when they are not set, and gives the same values as the file. The offline build of the `Docs Site Build` job has no metadata. Without the two values, a local run of the builder makes each link start with `/pages/dan-petty/devops-cli/`, so the job does not build what Pages publishes.

- **Rejected alternative: delete url and baseurl and use the metadata.** The local run above shows that the offline build then makes different links from the published site.

### 3. Do not move the exclude entries for the repository root

The second file excluded `.venv/`, `.data/`, `tests/`, three cache directories, `uv.lock` and `pyproject.toml`. These are paths at the repository root. The Pages source is `docs/`, which has none of them, and Jekyll ignores names that start with a dot. The entries have no effect, so they are not moved.

### 4. Write the description in ASD-STE100

The description goes into the meta tags of each page, so it is an output string. It replaces the noun cluster "Workstation DevOps CLI & Automated Code Review Platform" with one sentence that agrees with the first sentence of `AGENTS.md`.

## Risks / Trade-offs

- [Risk] The published meta description changes from the repository description to the description of `docs/_config.yml`. → Mitigation: this is the purpose of the setting. The text agrees with `AGENTS.md`.
