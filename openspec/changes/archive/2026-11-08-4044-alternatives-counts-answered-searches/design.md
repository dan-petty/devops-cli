# Design

## Decisions

- **The result is a frozen dataclass with `text` and `answered`.**: The refine tool and the alternatives tools both need the text. Only the alternatives tools need the flag. A frozen dataclass names both fields, and the existing tests for the refine tool change from `str` to `.text` only.
- **`answered` is false for a refused query.**: The guard stops the query before any request, so no search ran. The model gets the refusal text and may search again. The issue names only `SearchFailed`; this keeps one rule: a search counts when a provider answered it.
- **A separate attempt counter limits `search_web`.**: With `searches` holding only answered searches, `len(self.searches)` no longer counts the calls. A failing provider would then allow unlimited calls. The counter keeps the limit of `CONST_ROADMAP_ALTERNATIVES_MAX_SEARCHES` calls and the cost bound of the check.
- **The failure reason and the retry message say "no answered search".**: The model and the person read the true cause. The retry message keeps its first sentence, so the model still sees the call to action.
- **The counter `devops_cli_web_searches_total` does not change.**: It counts requests to providers, by backend and result, and the alert `RoadmapServiceAlternativesNotSearching` reads it. The histogram of the check counts answered searches.

## Rejected alternatives

- **Raise an error from `cited_web_search` for a failed search.**: The refine tool and the alternatives tools answer a failure as text so that no argument the model sends can stop the run (#2398, #3925). An error would end the run.
- **Keep the record of every search and add an `answered` field to `Search`.**: Each reader of `searches` (`queries`, the histogram, the comment, `_refusal`) would filter. One reader that forgets the filter brings the defect back. Recording only answered searches fixes the cause at its source.
- **Count a failed search as a search and refuse the verdict `none` only.**: The comment would still list a search that returned nothing because of an outage, and a verdict `partly` or `covers` would follow a failed search.
