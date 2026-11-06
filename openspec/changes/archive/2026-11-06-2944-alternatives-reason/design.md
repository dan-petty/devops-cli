# Design

## Decisions

- The model writes `reason`; the job writes the rest. The reason is the model's judgement, so the model must write it. The job runs it through `_clean`, like `covers` and `lacks`, so it holds no live link, mention or marker.
- `reason` is required with at least one character. A reply with no reason fails the schema of the output tool, and pydantic-ai asks the model again. No default and no empty comment line.
- `AlternativesTools.searches` replaces the list of queries. A `Search` holds the query and the result count. A property `queries` keeps the list of strings for the checks that only need them.
- The result count is the number of results with an http or https URL. A failed search answers as text and counts zero.
- The list of tools considered is every entry of `AlternativesTools.facts`, in the order the run read them. It includes the chosen tool, which also has its own section, so the list is complete on its own.
- The bound on sources is a constant (5), not a setting. The block in the issue body lists no sources, so it needs no bound.
- A URL is a link when it is bare: GitHub turns it into one. A source is always a URL that a tool returned, so the job has no need to wrap it.

## Rejected alternatives

- A markdown link `[title](url)` for each source. The job keeps no result title for a source, and a bare URL is a link on GitHub. A title would need a second store of text from the search, and the sanitizer would need to treat it.
- A job-written reason from the verdict and the lists. The reason is the model's judgement of why a tool does or does not cover the need. A template would repeat `Covers:` and `Lacks:`.
- A setting for the bound of sources. The bound only keeps the comment short. No person has asked to change it.
- Edit the earlier comment in place. The issue forbids it, and a new comment keeps the history of the checks.
