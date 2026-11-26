# Tasks

## 1. Read the host of a URL word

Kind: behavior. Reads: `src/devops_cli/ai/web_search.py`, `src/devops_cli/http/urls.py`, `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/security/reference_extractor.py`, `tests/ai/test_web_search.py`. Changes: `src/devops_cli/ai/web_search.py`, `src/devops_cli/http/urls.py`, `src/devops_cli/roadmap/page_fetch.py`, `tests/ai/test_web_search.py`, `tests/roadmap/references/test_reference_queries.py`.

- [x] 1.1 Add the table tests to `tests/ai/test_web_search.py`: `test_a_host_word_is_read_by_its_host`, `test_a_url_word_is_read_by_its_host`, `test_a_url_word_is_read_by_its_host_in_each_spelling_of_the_host`, `test_a_word_of_a_public_host_reaches_the_provider`, `test_a_word_with_no_refused_host_reaches_the_provider`, `test_a_text_that_the_url_parser_refuses_is_read_part_by_part` and `test_a_url_word_with_user_info_is_refused_by_the_secret_rule`. Add `test_a_code_span_with_a_url_is_read_by_the_host_of_the_url` to `tests/roadmap/references/test_reference_queries.py`
  - Verification: `$ uv run devops ci test tests/ai/test_web_search.py tests/roadmap/references/test_reference_queries.py` fails on the base
- [x] 1.2 Add `url_candidates` to `src/devops_cli/http/urls.py` and call it from `urls_in_order`. Add `_hosts_of` and `_url_hosts` to `src/devops_cli/ai/web_search.py`, and read each host of a word in `_private_part`
  - Verification: `$ uv run devops ci test tests/ai/test_web_search.py tests/roadmap/references/test_reference_queries.py tests/roadmap/test_roadmap_page_fetch.py` passes

## 2. Documents

Kind: other. Reads: `docs/roadmap/alternatives.md`, `src/devops_cli/roadmap/references/queries.py`. Changes: `docs/roadmap/alternatives.md`, `src/devops_cli/roadmap/references/queries.py`.

- [x] 2.1 Correct the sentence of `docs/roadmap/alternatives.md` and of the module text of `src/devops_cli/roadmap/references/queries.py` that says where the check reads the host of a URL
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
