# Proposal

## Why

Issue #2070: The live GitHub Pages documentation site of the repository had three defects found during the build of #2001. The root URL returned HTTP 404 because `docs/` had no `index.md` or `README.md`. The Architecture link in `docs/_layouts/default.html` pointed to `/ARCHITECTURE.html`, which returned HTTP 404 because `ARCHITECTURE.md` lives at the repository root. GitHub Pages published every source `.md` file next to its generated `.html` page.

## What Changes

- Add `docs/index.md` as the home page that routes to the primary documentation pages.
- Update `docs/_layouts/default.html` to remove `/ARCHITECTURE.html` so layout navigation and footer links reach only built pages.
- Set `optional_front_matter.remove_originals: true` in `docs/_config.yml` to remove raw Markdown files from the built site.
- Update `.github/workflows/ci.yml` in the `docs-site` job to mount the destination directory, verify `index.html` exists, verify no `.md` files exist, and check internal links with `lycheeverse/lychee`.
- Add test coverage in `tests/test_github_pages.py` to assert that `docs/index.md` exists, `docs/_config.yml` enables `remove_originals`, and the default layout contains no broken `/ARCHITECTURE.html` link.

This change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-pages`: Specifies that `docs/` contains an index page, site settings configure `remove_originals: true`, and layout links reach built pages only.

## Impact

- `docs/index.md`: Added to serve as the documentation site home page.
- `docs/_config.yml`: Configures `optional_front_matter.remove_originals: true`.
- `docs/_layouts/default.html`: Removes broken `/ARCHITECTURE.html` links from header and footer navigation.
- `.github/workflows/ci.yml`: The `docs-site` job runs link validation and checks for source Markdown absence.
- `tests/test_github_pages.py`: Adds unit tests for the home page, Jekyll settings, and layout links.

## Feasibility

The premise is true. I confirmed it against the system on 2026-10-27:

- The pinned builder image `ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041` includes `jekyll-optional-front-matter` version `0.3.2`.
- Gem inspection shows `optional_front_matter` supports `remove_originals: true` via `CLEANUP_KEY = "remove_originals"`.
- A local Docker build with `remove_originals: true` and `docs/index.md` verified that `index.html` was generated and zero `.md` files remained in the destination.
- Running `lycheeverse/lychee` in offline mode against the built site confirmed that it flags broken links such as `/ARCHITECTURE.html` and passes when links are valid.

## Existing Tool Considered

`actions/jekyll-build-pages` builds the site and `jekyll-optional-front-matter` handles front-matter-free Markdown generation. `lychee` checks links on the built static site. The change uses these open tools and writes no custom parser or crawler.
