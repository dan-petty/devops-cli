# Proposal: #5152

## Why

The owner wrote on 2026-11-12: "my github pages seem out of date or limited as well". The site that Jekyll built from `docs/` showed no version, commit or build date. 53 of its 99 pages had no link path from the home page or the nav, among them all 42 `docs/commands/*.md` pages. The root documents were not on the site, and 183 relative links to repository files went to a 404 page. The site had no search. `docs/MCP_TOOLS.md` had 149 broken anchors, also on github.com. The builder `actions/jekyll-build-pages` v1.0.13 is of 2024-08-06. Closes #5152.

## What Changes

- `zensical==0.1.1` is the site builder, in the `docs` dependency group of `pyproject.toml`.
- New command `devops docs site build [--strict] [--serve] [--root <dir>]`. It stages `docs/` (not `docs/agent/`), the eight root documents and `.nav.yml` in `.data/site-src/pages/` at their repository paths. It changes each relative link to a repository file outside the site into a GitHub link at the build commit. It writes `.data/site-src/zensical.yml`: the settings of `zensical.toml`, the stage folders, the theme overrides and the build data. It runs Zensical, and then checks that each built page is in a nav tab and holds the build commit. With `--strict`, a Zensical warning or a defect of a built page fails the command.
- `zensical.toml` holds the site settings: the URLs, the edit and view buttons, the GitHub heading ids, the Mermaid fence, the palette toggle, link and anchor validation, search and the awesome-nav plugin. `.nav.yml` holds seven tabs, with globs for the command, roadmap, cheatsheet and decision pages.
- `overrides/main.html` adds the `devops-build-commit` meta tag. `overrides/partials/copyright.html` shows the version, the commit, the commit date and the build time in the footer of each page.
- The MCP tool catalog links each tool to the heading id that GitHub writes (`#ai_ask_jev`).
- `devops gh pages verify` checks `zensical.toml` in place of `docs/_config.yml`.
- `pages.yml` builds with `devops docs site build --strict` and deploys `.data/site-src/site/`. It runs on a push to `main` that changes a site source, `pyproject.toml` or the build code. `docs-site.yml` runs the same command on a pull request, and skips the release pull request.
- The Jekyll files `docs/_config.yml`, `docs/_layouts/default.html` and `docs/assets/css/style.css`, the Jekyll container step and the lychee step are removed.

The command, its messages and `devops gh pages verify` are observable, so the change carries a delta of `github-pages`.

## Capabilities

- `github-pages`: REMOVED "The site settings are in docs/_config.yml only", "devops gh pages verify checks docs/_config.yml", "Default layout navigation links reach only built pages" and "The documentation site removes source Markdown files". MODIFIED "The documentation site provides an index home page". ADDED "The built site holds no source Markdown file", the site build, the link change, the build data, the nav check, the strict build, `--serve`, the check of `zensical.toml` and the MCP anchors.

## Impact

The site at https://dan-petty.github.io/devops-cli/ has new page URLs: a page keeps its repository path, for example `docs/SDLC/` in place of `SDLC.html`. Each page shows the version and the commit of its build. The site has search, a sitemap and a nav that reaches all 108 pages. The Pages source of the repository is GitHub Actions, so `pages.yml` is the one deploy path. The change fits one pull request.

## Feasibility

- Zensical 0.1.1 source (`zensical/config.py`): `docs_dir` and `site_dir` must be under the folder of the config file, and `docs_dir` must be relative. So the stage holds the staged config, `pages/` and `site/`. The awesome-nav plugin is native ("Rust owns discovery, YAML parsing, matching and navigation resolution"). `validation` takes `invalid_links` and `invalid_link_anchors`. `build --strict` exits 1 on a warning ("Aborted because --strict flag is set"). A TOML or a YAML config is read by its extension.
- The theme `zensical-ui` 0.0.42 includes `partials/copyright.html` in the footer and has an `extrahead` block in `base.html`.
- Trial build on 2026-11-12 before the link change: 108 pages, 172 "page does not exist" warnings (links to repository files) and 149 "anchor does not exist" warnings (all in `docs/MCP_TOOLS.md`).
- Build after the change: `uv run devops docs site build --strict` exits 0 with "No issues found", 108 pages, 185 changed links, 7 tabs, `search.json` of 3.7 MB and a sitemap of 108 URLs. A check of every relative `href` and `src` of the 109 built HTML files found 0 broken links and 0 broken anchors in 24,395 links.
- `actions/upload-pages-artifact` v5.0.0 runs `tar --directory "$INPUT_PATH"`, so the dot folder `.data` in the path is not in the archive member names.

## Existing Tool Considered

Zensical 0.1.1 (MIT) builds the site, with native search, nav, Mermaid, link and anchor validation and strict mode. Its awesome-nav plugin gives the glob nav. tree-sitter-markdown 0.5.4, a dependency already, finds the link destinations. Zensical runs no MkDocs hooks, so no plugin changes the links: the stage does it, about 120 lines with the checks of the built site, and a 15-line footer template. Cost (estimate in #5152): about 350,000 tokens and 1 day elapsed. The change deletes `docs/_config.yml`, `docs/_layouts/default.html`, `docs/assets/css/style.css`, the Jekyll check of `devops gh pages verify`, the Jekyll container step and the lychee step of `docs-site.yml`.
