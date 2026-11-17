# Tasks

## 1. The block and the comment

- [x] 1.1 Change the alternatives tests to the new form: the block holds the reason, the covers and the lacks; the comment holds the change line and the folded evidence; a skip class posts no comment; a contract test fails when a line of the comment is in the block
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_recheck.py tests/roadmap/test_roadmap_alternatives_project_facts.py`
- [x] 1.2 Move the reason, the covers and the lacks to the block, make the comment the event, and post no comment for a skip class
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_alternatives.py tests/roadmap/test_roadmap_alternatives_recheck.py tests/roadmap/test_roadmap_alternatives_project_facts.py`

## 2. The dry-run plan

- [x] 2.1 Change the dry-run test: the comment has the condition that the item is no skip class
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`
- [x] 2.2 Add the condition to the comment of the alternatives plan
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_dry_runs.py`

## 3. Refine reads the block and the whole comment

- [x] 3.1 Add a refine test: the request holds the block with the reason and the lacks, and a comment longer than the reply cap whole
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_covers_check.py`
- [x] 3.2 Remove the cut of the comment, and name the block as the source in the proposal and investigation prompts
  - Verification: `$ uv run devops ci test tests/roadmap/refine/`

## 4. Intake compares the text of a person

- [x] 4.1 Add an intake test: the embedding and the excerpt of an item hold no job text, and a duplicate is still flagged
  - Verification: `$ uv run devops ci test tests/roadmap/intake/test_roadmap_intake_duplicates.py`
- [x] 4.2 Compare `text_of_a_person` of each item
  - Verification: `$ uv run devops ci test tests/roadmap/intake/`

## 5. Documents

- [x] 5.1 Update `docs/roadmap/alternatives.md` and `docs/roadmap/intake.md`
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
