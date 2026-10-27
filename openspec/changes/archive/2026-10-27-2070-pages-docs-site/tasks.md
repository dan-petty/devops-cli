# Tasks

## 1. Documentation site home page and clean layout links

- [x] 1.1 Add failing unit tests in `tests/test_github_pages.py` asserting that `docs/index.md` exists, `docs/_config.yml` configures `remove_originals: true`, and `docs/_layouts/default.html` contains no `/ARCHITECTURE.html` link, and verify that `uv run devops ci test tests/test_github_pages.py` fails on the unpatched repository
- [x] 1.2 Add `docs/index.md` as the home page that routes visitors to primary documentation guides
- [x] 1.3 Configure `optional_front_matter.remove_originals: true` in `docs/_config.yml`
- [x] 1.4 Remove `/ARCHITECTURE.html` from header navigation and footer in `docs/_layouts/default.html`
- [x] 1.5 Verify that `uv run devops ci test tests/test_github_pages.py` passes

## 2. Docs site build workflow validation

- [x] 2.1 Update the `docs-site` job in `.github/workflows/ci.yml` to mount the destination directory, assert `index.html` exists, assert no `.md` files exist, and check internal links with `lychee`
- [x] 2.2 Verify that `uv run devops openspec check` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
- Pending a person: after the Pages build of the merge commit, verify that `https://dan-petty.github.io/devops-cli/` loads the home page.
