# Tasks

## 1. A job block marker ends a section of the body

Kind: behavior. Reads: `src/devops_cli/roadmap/refine/refine.py`, `src/devops_cli/roadmap/alternatives.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/refine/refine.py`, `tests/roadmap/refine/test_roadmap_refine_dependencies.py`, `tests/roadmap/refine/test_roadmap_refine_questions.py`.
Adds: `_JOB_BLOCK_MARKERS`

- [x] 1.1 Write the failing test `test_a_job_block_marker_ends_the_dependencies_section` in `tests/roadmap/refine/test_roadmap_refine_dependencies.py`, parametrized with the four scenarios of the requirement "A job block marker ends the Dependencies section". Build each marker from its constant in `devops_cli.config.constants`, not from a literal. The ids are `alternatives-after-section` (`None.`, then an alternatives block whose Lacks list holds `- Two-container template integration that #5506 adds`, gives `[]`), `refine-part-then-alternatives` (a refine block whose last part `### Dependencies` holds `- #4989`, then an alternatives block whose Lacks list holds `- A tool that #5506 adds`, gives `[4989]`), `section-after-alternatives` (that alternatives block, then `## Dependencies` and `- #4989`, gives `[4989]`) and `marker-in-code-span` (a paragraph that quotes `CONST_ROADMAP_ALTERNATIVES_START_MARKER` in a code span, then `- #4989`, gives `[4989]`). The ids `alternatives-after-section` and `refine-part-then-alternatives` fail on the base with `[5506]` and `[4989, 5506]`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py` fails on the base
- [x] 1.2 Add the case `alternatives-block` to `test_the_body_questions_follow_markdown` in `tests/roadmap/refine/test_roadmap_refine_questions.py`: the section `- *Which store holds the record?*`, and on the next line an alternatives block (built from the marker constants) whose Lacks list holds `- Which parser reads the marker?`, gives `["*Which store holds the record?*"]`. The case fails on the base, which also gives `Which parser reads the marker?`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_questions.py` fails on the base
- [x] 1.3 In `src/devops_cli/roadmap/refine/refine.py`, add the module-level `_JOB_BLOCK_MARKERS: Final[frozenset[str]]` that holds `CONST_ROADMAP_REFINE_START_MARKER`, `CONST_ROADMAP_REFINE_END_MARKER`, `CONST_ROADMAP_ALTERNATIVES_START_MARKER` and `CONST_ROADMAP_ALTERNATIVES_END_MARKER`. Change `_section_tokens` to end the section also at an `html_block` token whose stripped content is in `_JOB_BLOCK_MARKERS`. Keep the search for the heading as it is, so a heading inside a job block still starts a section. Change the docstrings of `_section_tokens`, `body_dependencies` and `body_questions` to state the new end of the section
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py tests/roadmap/refine/test_roadmap_refine_questions.py` passes
- [x] 1.4 Add the case `refine-part-then-person-text` to `test_a_job_block_marker_ends_the_dependencies_section`: a refine block whose last part `### Dependencies` holds `- #4989`, then, with no alternatives block, the paragraph `Depends on #8888.`, gives `[4989]`. The case fails when `_JOB_BLOCK_MARKERS` does not hold `CONST_ROADMAP_REFINE_END_MARKER`, which gives `[4989, 8888]`
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_dependencies.py` passes

## 2. Set a new version of the rules

Kind: other. Reads: `src/devops_cli/config/constants.py`, `tests/roadmap/refine/test_roadmap_refine_person_wait.py`. Changes: `src/devops_cli/config/constants.py`.

- [x] 2.1 Set `CONST_ROADMAP_REFINE_RULES_SINCE` in `src/devops_cli/config/constants.py` to the UTC time of the commit of this task, and change its comment so that it names the rule of this change: a job block marker ends the Dependencies section (#6613), which removes false dependencies
  - Verification: `$ uv run devops ci test tests/roadmap/refine/test_roadmap_refine_person_wait.py` passes

## 3. State the end of the section in the refine page

Kind: other. Reads: `docs/roadmap/refine.md`, `src/devops_cli/roadmap/refine/refine.py`. Changes: `docs/roadmap/refine.md`.

- [x] 3.1 In the Dependencies paragraph of `docs/roadmap/refine.md`, state that the section ends at the next heading of the same or a higher level, or at the start or the end marker of a job block, and that the Dependencies part inside the refine block still names its blockers. In the paragraph on the new version of the rules, give the time of task 2.1 and name the rule of this change
  - Verification: `$ uv run devops ci docs` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
