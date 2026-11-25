## ADDED Requirements

### Requirement: One cached CommonMark parser factory
The roadmap SHALL provide a cached factory, `commonmark_parser()`, in `src/devops_cli/roadmap/markdown.py`, that returns a `MarkdownIt("commonmark")` instance.

#### Scenario: The factory returns one parser
- **WHEN** A test clears the cache of `commonmark_parser`, counts returns of `MarkdownIt.__init__` with `sys.setprofile`, and calls `commonmark_parser()` two times
- **THEN** The test asserts that both calls return the same object and that `MarkdownIt.__init__` ran one time

### Requirement: Plain roadmap readers use the cached factory
Every roadmap reader that parses plain CommonMark MUST use `commonmark_parser()` and MUST NOT build its own `MarkdownIt("commonmark")`.

#### Scenario: A source scan finds one plain construction
- **WHEN** A test reads each Python file under `src/devops_cli/roadmap` and collects each line that holds `MarkdownIt("commonmark")` without `.use(`, `.enable(` or `.disable(`
- **THEN** The test asserts that every collected line is in `src/devops_cli/roadmap/markdown.py`

### Requirement: Refine readers build one parser
The refine readers `body_questions`, `body_dependencies` and `title_dependencies` MUST parse with `commonmark_parser()` and MUST NOT build a parser on each read.

#### Scenario: Three refine reads build one parser
- **WHEN** A test clears the cache of `commonmark_parser`, counts returns of `MarkdownIt.__init__` with `sys.setprofile`, and calls `body_questions`, `body_dependencies` and `title_dependencies`
- **THEN** The test asserts that `MarkdownIt.__init__` ran one time across the three calls
