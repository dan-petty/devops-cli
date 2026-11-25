## Problem

The live GitHub Pages site of the repository has three defects, found while #2001 was built (2026-10-24):
- `https://dan-petty.github.io/devops-cli/` returns 404, because `docs/` has no `index.md` or `README.md`.
- The Architecture link in `docs/_layouts/default.html` goes to `/ARCHITECTURE.html`, which returns 404, because `ARCHITECTURE.md` is at the repository root, not in `docs/`.
- Pages publishes each source `.md` file next to its `.html` page. The `remove_originals` option of jekyll-optional-front-matter controls this.

## Proposed fix

- Add a home page under `docs/` that routes to the main documents.
- Point the layout's links only at pages that the site builds, and add a check (for example, a link checker such as lychee on the built site in the `Docs Site Build` job) so that a broken link fails before the merge.
- Set `optional_front_matter.remove_originals: true` in `docs/_config.yml` if the github-pages gem version supports it.

## Acceptance criteria

- [ ] The built site has an index page, and the CI build fails on a broken internal link.
- [ ] The built site has no copies of the source `.md` files.

<!-- devops-roadmap-refine:start -->
<!-- checked-at: sha=aece067ac6610b68bfe58c8a0de418c03e94519a -->
## Proposed design

### Problem statement
The GitHub Pages site for devops-cli has a missing home page, broken links, and publishes source markdown files. Users cannot access the main documentation page, and internal links fail.

### Acceptance criteria
- Criterion 1: The built site has an index page that users can access without getting a 404 error
  Verification: Visit `https://dan-petty.github.io/devops-cli/` and verify it loads the home page
- Criterion 2: Internal links in the documentation site work correctly and do not return 404 errors
  Verification: Run a link checker such as lychee on the built site in the Docs Site Build job and confirm no broken internal links
- Criterion 3: The built site has no copies of source .md files published alongside their .html pages
  Verification: Check that no .md files are present in the published site directory, only .html files with corresponding content

### Key questions
- **Does the repository have an ARCHITECTURE.md file at the root?**: Yes, the repository has ARCHITECTURE.md at the root. [sources: ARCHITECTURE.md]
- **What is the current Jekyll configuration for publishing source files?**: The documentation does not specify the current configuration, but the proposed fix mentions using the remove_originals option of jekyll-optional-front-matter. [sources: docs/_config.yml]
- **Should the site build process be modified to avoid publishing source .md files?**: Yes, according to the issue description, Pages publishes each source .md file next to its .html page. The fix should set remove_originals option of jekyll-optional-front-matter to true if supported. (proposed)

### Fit
Fits in one pull request.

### Suspected block
None.

### Dependencies
None.
<!-- devops-roadmap-refine:end -->
