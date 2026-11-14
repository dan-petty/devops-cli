## ADDED Requirements

### Requirement: The pull request comment names the tools of the job
The implement job SHALL name each tool that a step called, with its count, in the comment of the Job on the pull request. The line of the tool counts SHALL hold no argument, path or file content.

#### Scenario: The comment names each tool of the job
- **WHEN** A Job ends with two calls of `read_file` and one call of `pr_describe`, and one step of it fails a check whose command names a path.
- **THEN** The comment holds the count of each of the two tools, the line of the counts holds no argument of a tool call and no path, and the table of the steps keeps the failing command with its path.
