# Tasks

## 1. Behavior

- [ ] 1.1 Write the failing test for a named pull request read at its merge commit
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`
- [ ] 1.2 Add the bounded reader of the named pull request files
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`
- [ ] 1.3 Hold the pull request files in the verification input and its quote rule
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py tests/roadmap/stage/test_roadmap_stage_verify.py`
- [ ] 1.4 Put the named pull request files in the verification input of the stage job
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`
- [ ] 1.5 Hold the merge commit in the pull request status of the GitHub client
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`

## 2. Documents

- [ ] 2.1 Name the named pull request files in the verification prompt
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_verify_pulls.py`
- [ ] 2.2 Write the OpenSpec change, its design and its spec delta
  - Verification: `$ uv run devops openspec check`
