# Design

## Decisions

### 1. Suffix rules for bytecode
The `.dockerignore` rules use `**/__pycache__` to drop directories and `**/*.pyc` and `**/*.pyo` to drop loose files. Literal suffixes are used instead of character classes for cross-platform compatibility.

### 2. Location of parser directive
`# check=error=true` is placed on line 2 of `Dockerfile`, directly below `# syntax=...`. BuildKit requires parser directives before any build instructions.

## Rejected alternatives

- Character class `**/*.py[co]`: Rejected because literal suffixes provide predictable matching without shell pattern variance.
- Post-instruction check comment: Rejected because BuildKit treats directives after `FROM` as plain comments.
