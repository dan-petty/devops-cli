Perform a specialized documentation review on '{target}'.

### Documentation Review Rules:
- **What Counts**: a statement the code contradicts (quote the document line, and the code line with its file and line number), a broken relative link, or a command, option, configuration key or environment variable that does not exist. Requests for more explanation, examples or different wording go in `summary`.
- **Zero Information Leakage**: a real credential, token or key in the text. Whether private addresses or host names may appear in the documentation is the project's convention to state.
- **Context-Aware Avoidance Pattern Exemption**: Never flag documentation, security tutorials, or architectural specifications that describe known vulnerabilities or anti-patterns in the context of mitigating, explaining, or avoiding them.
- **Plans and Records**: Roadmaps, changelogs, task files and decision records describe plans and history, not the code. Return no findings for them.
- **Fix**: the corrected text for the cited lines, at `path/to/file.md:start-end`.
- **Line Numbers**: Each line of the file starts with its line number and a tab, counted from the top of the whole file on every page. Cite those numbers in `location`, and never copy them into quoted code or a fix. In a diff, a removed line has no number.
