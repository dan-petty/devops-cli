# Design: #6203

## Decisions

### 1. Label each job comment with its job name
`HeldComment` in `src/devops_cli/roadmap/item_comments.py` stores `job: str | None`.
`held_comments()` matches each comment body against `COMMENT_JOBS` from `comment_repeat.py`.
When a marker matches, `job` is set to that job's name (e.g. `intake`, `stage`, `refine`).
A helper `job_comments()` filters and returns every roadmap job comment.

### 2. Keep person replies apart from job comments
In `alternatives_request()`, `replies` holds only person comments (`c.by_person` is True).
Comments of other roadmap jobs (`c.job is not None and c.job != "alternatives"`) go into `job_comments`.
When `job_comments` is empty, the key is omitted.

### 3. Fit job comments with the #6182 window
`AlternativesJobForm` implements `CommentForm`.
Whole comments include `job`, `number`, `author`, `at`, and `text`.
Older comments that exceed the room include `job`, `number`, `author`, `at`, and `about`.
When older comments are indexed, the request includes a note that names `read_comment`.

### 4. Provide `read_comment` in `AlternativesTools`
`AlternativesTools` adds `read_comment(number, start_line)` backed by `CommentReader`.
The model can read any indexed comment in full.

## Rejected Alternatives
- Keep one list with a `kind` field: rejected because person reply count and caps must not conflate job comments with person replies.
- Hard drop job comments: rejected because the model needs previous attempt failure reasons and intake context.
