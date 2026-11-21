# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests. The answer of `fetch_page` says that a link in the text is not a source. The job refuses a reply that cites a link of a fetched page for reason `url`, and logs the link. It writes a reply that cites the fetched page. It refuses a reply that cites a URL of the item that no tool returned
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_page_links.py tests/roadmap/test_roadmap_page_fetch.py`
- [x] 1.2 Add the sentence to `page_fetch_frame`. Name the URLs that are sources in `roadmap_alternatives.md`, and regenerate the documentation
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives_page_links.py tests/roadmap/test_roadmap_page_fetch.py tests/roadmap/test_roadmap_alternatives.py tests/roadmap/refine/test_roadmap_refine_investigation.py`

## 2. Documents

- [x] 2.1 Say in `docs/roadmap/alternatives.md` which URLs are sources, and in it and `docs/roadmap/refine.md` that the answer of `fetch_page` says that a link in the text is not a source
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Pending a person: after the release, read the alternatives grade with `uv run devops roadmap eval grades` and the `reason=url` result lines in Loki.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
