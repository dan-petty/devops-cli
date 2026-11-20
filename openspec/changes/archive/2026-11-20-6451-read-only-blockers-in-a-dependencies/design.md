# Design

## Decisions

- **Keep the Dependencies section of the body as the source of a dependency and add a strict blocker rule to it.**: The held items declare their blockers as text, and the GitHub blocked-by links hold none of those mentions, so a switch of the source would release no held item.
- **A line under Dependencies names a blocker when it is a list item whose first word is `#N`, a line that holds issue references only, or a line that starts with `Merge first`; every other mention names no dependency.**: The forms that the issue names keep working, a body that lists references keeps every reference, and the phrases that cause the false dependencies open no line: a parent, a child, a related issue, a reverse link and the source line all carry other words.
- **Keep a line that holds issue references only as a blocker line, because a refine round writes its dependencies as exactly such a line.**: `src/devops_cli/roadmap/refine/refine.py:2107:lines.append(", ".join(f"#{d}" for d in proposal.dependencies))` writes the dependencies of a round as `#4550, #4691`, and `tests/roadmap/test_roadmap_consolidate_shortlist.py:174:assert [Signal.LINK in signals(lists, 3, n) for n in (2, 4, 5)] == [True, True, False]` asserts both references of one such paragraph.
- **Accept that a blocker written in prose in the person's Dependencies section, such as `#4550 puts the dependencies in their own image layers first.`, names no dependency after this change.**: No wording test tells a prose blocker from the prose that names a parent, a related issue or a reverse link, and the issue's design chose the line-start rule; the person writes a blocker as a list item, and refine writes its own dependencies as a line of references.
- **Put the blocker rule in `body_dependencies` and leave `_issues` as the generic reader of `#N` words.**: Every dependency path reads `body_dependencies`, and the quoted-title read needs `_issues` to tell a line that names issues by number from one that names them by title.
- **File the source of a candidate under a `## Source` heading after the body, and move the two test assertions that pin the filed-body form with it.**: A heading ends the Dependencies section that `_section_tokens` reads, so the source leaves the section for every source form, and a URL source and a `#N` source need no special case.
- **Read the section with markdown-it-py, which the repository already depends on, and write the blocker rule on its inline tokens.**: The parser tells a heading, a paragraph and a list item apart, so the first word of a line is known, and no new dependency joins the project.
- **Change no caller of `body_dependencies`: the live callers in `src/devops_cli/roadmap/consolidate_shortlist.py`, `src/devops_cli/roadmap/dependencies.py`, `src/devops_cli/roadmap/refine/refine.py` and `src/devops_cli/roadmap/stage/stage.py` each read the one reader.**: Each of the four takes the list of the reader and writes no rule of its own, so each keeps the blocker rule with no change of its own.
- **Keep the retry match of `_new_subject` as it is, because it compares the issue body with `filed_body()` of the same candidate.**: Both sides of the comparison come from `filed_body`, so the `## Source` heading changes both together and a run that stopped after filing still finds its issue.
- **Carry the related item #6450 as a related item and not as a dependency of this change.**: The comment of intake names it as a different change that excludes open trackers, and this change excludes every non-blocker mention, so neither delivers the other.

## Rejected alternatives

- **Read the GitHub issue dependencies API (`issues/<n>/dependencies/blocked_by`) as the source of a dependency.**: The API holds typed links only. The items that the issue lists name their blockers as text, so the API would drop each text blocker that an item uses today.
- **Keep every `#N` mention of the section, as the code does now.**: That is the defect: `src/devops_cli/roadmap/refine/refine.py:1239:return [int(word[1:]) for word in words if word.startswith("#") and word[1:].isdigit()]` keeps each word of each inline token, so a parent, a related issue and a source line hold an item.
- **Refuse a blocklist of the words that open a parent link, a child link, a related issue or the source line.**: A new phrase or a reverse link with another wording escapes the list, and the section holds free text that a person writes.
- **Keep only the first word of a line, whatever the line is.**: `tests/roadmap/test_roadmap_consolidate_shortlist.py:174:assert [Signal.LINK in signals(lists, 3, n) for n in (2, 4, 5)] == [True, True, False]` asserts both references of one paragraph, so that rule would break the test and drop a real blocker.
- **Filter the numbers inside `open_dependency`.**: Refine and the stage request read `body_dependencies` with no `open_dependency`, so the false numbers would stay in those paths.
- **Change `_issues` itself to keep only a blocker word.**: The quoted-title read calls `_issues` to tell a line that names issues by number from one that names them by title, so the title read would change with it.
- **Write the source as a markdown link at the end of the body.**: A link text can hold `#N`, and a source may be a path rather than a URL, so the link form fixes no case that the heading does not.
- **Leave the source line at the end of the body and rely on the reader to ignore it.**: The line stays inside the Dependencies section, so each later reader of the section meets it again; the heading removes it for every reader.

## Unchanged references

- `src/devops_cli/roadmap/dependencies.py` (caller): Calls `body_dependencies`, so it keeps the blocker rule with no change of its own.
- `src/devops_cli/roadmap/stage/stage.py` (caller): Builds its dependency list from `body_dependencies`, so it keeps the blocker rule with no change of its own.
- `src/devops_cli/roadmap/consolidate_shortlist.py` (caller): Reads the same reader for its Dependencies signal, so it keeps the blocker rule with no change of its own.
