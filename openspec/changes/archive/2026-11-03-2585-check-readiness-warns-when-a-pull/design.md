# Design

## Decisions

- **Keep the limit and the trailer prefixes as private constants of `src/devops_cli/github/merge_readiness.py`.** The issue says "The limit is one constant beside the rule's reader." The naming table of `CONTRIBUTING.md` section 5 gives `_<NAME>` to a constant that one module reads. So the names are `_PR_BODY_MAX_CHARS` and `_TRAILER_PREFIXES`, and no test imports them: the tests use the numbers 1,000 and 1,001 of the scenarios.
- **Strip trailers with a closed list of five prefixes.** A line that starts with `Closes`, `Change:`, `Fail-to-pass:`, `Co-authored-by:` or `Signed-off-by:` is a trailer line. `str.startswith` takes the tuple. The length is that of the other lines joined with a newline and trimmed at both ends, so the blank line before the trailers does not count. `str.splitlines` also handles the `\r\n` that the GitHub web editor writes.
- **Judge the body in `_judge_body_length`, called after `_judge_draft`.** The function reads `pr_data.get("body") or ""`, because GitHub sends `null` for an empty body. It calls `verdict.warn` once.
- **Write the text of the advisory in `PRMessages`.** The text is `pr_body_too_long`, with the fields `number`, `length` and `limit`, and the numbers are formatted with a thousands separator (`{length:,}`), so that the text names `1,001` and `1,000`. User-facing strings of the verdict live in `MESSAGES.pr`, as `changed_files_unread` does.
- **Test the rule on the verdict and the exit code on the command.** The rows of `tests/github/test_merge_readiness.py` call `assess_merge_readiness` through `_assess`. One row of the table in `tests/commands/test_pr.py` runs `devops pr check-readiness` with a long body and expects exit 0 and the warning in the output.

## Rejected alternatives

- **Use `git interpret-trailers`.** It needs a git process per check, and it reads only the last paragraph of the body. With a body that ends with `Closes #12`, a blank line and two `Key: value` lines, `git interpret-trailers --parse` printed only the two `Key: value` lines. The five known prefixes are a closed list, which `CONTRIBUTING.md` section 1 prefers to a parser here.
- **Put the limit in `src/devops_cli/config/constants.py`.** Only `src/devops_cli/github/merge_readiness.py` reads it. `CONTRIBUTING.md` section 5 keeps such a constant in its module.
- **Reuse `CONST_ROADMAP_IMPLEMENT_BODY_MAX_CHARS`.** It has the same value by chance. It limits the text that the implement job writes, so a change to one limit must not move the other.
- **Name only the length in the advisory.** The writer then has to find the limit and the rule. Naming the limit and `CONTRIBUTING.md` section 4 shows how much to cut and where the rule is.
