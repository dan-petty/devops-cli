# Design

## Context

GitHub Pages publishes `main:/docs` using the Jekyll builder. See `proposal.md` for motivation. Currently, `docs/` has no `index.md`, `docs/_layouts/default.html` links to `/ARCHITECTURE.html`, and source Markdown files are published alongside HTML pages.

## Goals / Non-Goals

**Goals:**
- Provide `docs/index.md` as the site home page.
- Clean up `docs/_layouts/default.html` by removing links to non-existent pages like `/ARCHITECTURE.html`.
- Configure `optional_front_matter.remove_originals: true` in `docs/_config.yml`.
- Add link verification and Markdown file absence verification to the `Docs Site Build` job in `.github/workflows/ci.yml`.
- Add unit tests verifying these invariants in `tests/test_github_pages.py`.

**Non-Goals:**
- Move repository-root documents such as `ARCHITECTURE.md` into `docs/`.
- Change runtime CLI behavior or `devops` command implementations.

## Decisions

### Decision: Create docs/index.md for the site home page
Jekyll builds `docs/index.md` into `index.html` at the site root. This document introduces `devops-cli` and links to the primary guides (`CLI_REFERENCE.md`, `CONFIGURATION.md`, `MCP_TOOLS.md`, `ROUTINE_TASKS.md`, `SDLC.md`, `TESTING.md`).
- *Alternative*: Create `README.md` in `docs/`. Rejected because `jekyll-optional-front-matter` blacklists `README` by default, whereas `index.md` is automatically converted to `index.html`.

### Decision: Remove /ARCHITECTURE.html from default.html layout
`ARCHITECTURE.md` is located at the root of the repository, not inside `docs/`. Jekyll does not compile repository root files. Removing `/ARCHITECTURE.html` from the header navigation and footer ensures layout links resolve only to built pages.
- *Alternative*: Add a symlink from `docs/ARCHITECTURE.md` to `../ARCHITECTURE.md`. Rejected because the Pages builder runs in safe mode, ignoring links outside the source root.
- *Alternative*: Replace with external GitHub link in header navigation. Rejected because header navigation contains internal site sections.

### Decision: Enable remove_originals in docs/_config.yml
The `jekyll-optional-front-matter` gem (v0.3.2) supports `optional_front_matter.remove_originals: true`. Setting this option removes source `.md` files from the Jekyll build target, leaving only `.html` output files.

### Decision: Validate built site in CI with Lychee and file checks
In `.github/workflows/ci.yml`, the `docs-site` job mounts the destination directory `$GITHUB_WORKSPACE/_site`. After Jekyll build:
1. Verify `_site/index.html` exists.
2. Verify no `.md` files exist in `_site`.
3. Run `lycheeverse/lychee:latest` offline against `_site` to verify that all internal links are valid.

## Risks / Trade-offs

- [Lychee flags repository-relative links] → Exclude links ending in `.md`, `.yaml`, or pointing to source directories outside the site build.
