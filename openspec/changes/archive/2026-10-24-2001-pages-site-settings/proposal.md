# Proposal

## Why

Issue #2001: `docs/github-pages.config.yaml` said that GitHub Pages reads it, but the Pages build reads `docs/_config.yml` only. Thus the title, description, url, baseurl, plugins, kramdown settings and layout defaults of the second file had no effect. Pages also published the second file as a static file at `/devops-cli/github-pages.config.yaml`. `devops gh pages verify`, `docs/ROUTINE_TASKS.md` and the knowledge base named the second file as the Pages configuration, so the check passed on settings that the site did not use.

## What Changes

- `docs/_config.yml` holds every site setting: the settings of `docs/github-pages.config.yaml` move into it, next to the `exclude: [agent/]` setting that it already held.
- `docs/github-pages.config.yaml` is deleted.
- `devops gh pages verify` reads `docs/_config.yml`. When that file is missing, the check fails and names `_config.yml`. A file with a different name does not pass the check.
- `docs/ROUTINE_TASKS.md` and the GitHub project management guide of the knowledge base name `docs/_config.yml`.

The `devops gh pages verify` result is observable, so the change has a spec delta.

This change fits one pull request.

## Capabilities

### New Capabilities

- `github-pages`: The site settings of the documentation site, and the local check of them that `devops gh pages verify` runs.

### Modified Capabilities

None.

## Impact

- `docs/_config.yml`: holds every site setting.
- `docs/github-pages.config.yaml`: deleted.
- `src/devops_cli/github/pages.py`: `verify_pages_configuration` reads `docs/_config.yml`.
- `tests/test_github_pages.py`: the verify tests write `docs/_config.yml`; two tests are added.
- `docs/ROUTINE_TASKS.md`, `src/devops_cli/ai/knowledge_base/devops_cli/tasks/github_project_management.md`: name `docs/_config.yml`.
- The published site: the meta description, the canonical URL and the links of the `Docs Site Build` job's offline build agree with the published site, and `/devops-cli/github-pages.config.yaml` is no longer published.

## Feasibility

The premise is true. I confirmed it on 2026-10-24 with these sources:

- `GET repos/dan-petty/devops-cli/pages` returns `build_type: legacy` and the source `main:/docs`.
- The GitHub Pages documentation ("About GitHub Pages and Jekyll") says: "You can configure most Jekyll settings, such as your site's theme and plugins, by editing your `_config.yml` file."
- The pinned builder image `ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd...` (v1.0.13, github-pages 232, Jekyll 3.10.0): `entrypoint.sh` runs `github-pages build` with `--source` and `--destination` only. The `build` command of the `github-pages` gem has no `--config` option. `Jekyll::Configuration#config_files` reads `<source>/_config.yml` or `<source>/_config.yaml` when no `config` option is set.
- A local run of that image on `docs/` of the base logs `Configuration file: /github/workspace/docs/_config.yml` and writes `github-pages.config.yaml` into the site as a static file. Its pages have no meta description, and their links start with `/pages/dan-petty/devops-cli/`.
- The published site has the repository description in its meta description, not the description of the second file, and `https://dan-petty.github.io/devops-cli/github-pages.config.yaml` returns HTTP 200.
- After the change, the same local run reads `docs/_config.yml`, writes no `github-pages.config.yaml`, and gives the meta description of `docs/_config.yml`, the canonical URL `https://dan-petty.github.io/devops-cli/CLI_REFERENCE.html` and the stylesheet link `/devops-cli/assets/css/style.css`. The canonical URL and the stylesheet link are the same as on the published site. The page bodies do not change.

## Existing Tool Considered

Jekyll reads `_config.yml`, and the `github-pages` gem and `jekyll-github-metadata` supply the defaults and the url and baseurl of a Pages build. The change uses that file and builds nothing. It deletes `docs/github-pages.config.yaml` and the code path of `devops gh pages verify` that read it.
