# Design

## Decisions

### Drop job comments before the cap

A job comment in the last `CONST_ROADMAP_REFINE_MAX_REPLIES` comments would otherwise push a person
reply out of the request. The filter runs first, so the cap counts person replies only.

### One shared filter

`comments_without_jobs` in `refine.py` removes every comment that holds a marker of
`CONST_ROADMAP_JOB_COMMENT_MARKERS`. Refine already uses the same `_comments_without` filter for
its own job comments. Alternatives imports the public helper, so one copy keeps the behavior equal.

### The author type stays trusted

The owner account and the Service bot write both person replies and job comments, so the author
association cannot tell them apart. The marker tells them apart.

## Rejected alternatives

- **Filter by author type or association:** the intake reason comment is trusted, so a trusted
  author keeps it.
- **Add a filter in `alternatives.py`:** two copies drift.
- **Make `replies_after_marker` drop job comments:** it answers which comments follow a marker, a
  different question.
- **Cap, then drop job comments:** a job comment in the last N pushes a person reply out.
