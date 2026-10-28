# Tasks

## 1. An item carries its author's association

- [x] 1.1 Write `test_an_item_carries_its_authors_association_with_the_repository` in `tests/test_roadmap_store_contract.py`, give `seed_issue` of `tests/roadmap_github_fake.py` an `author_association`, and verify that `uv run devops ci test tests/test_roadmap_store_contract.py -k authors_association` fails on the base
- [x] 1.2 Add `author_association` to `Item` and keep it in `item_of` in `src/devops_cli/roadmap/store.py`, open an issue of the in-memory store for the owner by default (`DEFAULT_ROADMAP_MEMORY_AUTHOR_ASSOCIATION`), and verify that `uv run devops ci test tests/test_roadmap_store_contract.py tests/test_roadmap_github_store.py tests/test_roadmap_intake.py` passes

## 2. A round leaves an item from an account without write access to a person

- [x] 2.1 Write `test_a_round_leaves_an_item_from_an_outside_account_waiting_on_a_person_and_item_refines_it` and `test_a_round_takes_an_item_that_the_owner_a_member_or_a_collaborator_opened` in `tests/test_roadmap_refine.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py -k "outside_account or owner_a_member"` fails on the base
- [x] 2.2 Add `_outside_author` to the selection in `src/devops_cli/roadmap/refine.py` with the detail line `refine_outside_author` in `src/devops_cli/lang/en/messages.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py tests/test_roadmap_run.py tests/test_service_limits.py` passes
- [x] 2.3 Give the rule in the help text of `devops roadmap refine` and `--item` and in the docstring of `refine.py`, run `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` passes

## 3. Refine neutralizes the model text that GitHub hides, links or cross-references

- [x] 3.1 Write `test_a_rendered_section_neutralizes_comment_openers_www_links_and_cross_repo_references` and `test_sanitize_text_neutralizes_what_github_hides_links_or_cross_references` in `tests/test_roadmap_refine.py`, and verify that `uv run devops ci test tests/test_roadmap_refine.py -k neutralizes` fails on the base
- [x] 3.2 Neutralize `<!` and `<?` after the tags are removed, put unallowed `www.` links and `owner/repo#N` references in code spans in `sanitize_text`, add the `checked-at` comment after the text is sanitized in `render_proposal_section`, and verify that `uv run devops ci test tests/test_roadmap_refine.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
