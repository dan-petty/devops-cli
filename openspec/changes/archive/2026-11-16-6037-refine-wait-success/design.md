# Design

## Decisions
- **A wait is a success.** The intended result of refine is that the attempt sets the next step of the item. The docstring of `NextStep` gives each value as a wait, and names only `retry` and `failed` as failures of the job. `none` is no attempt: refine changes no item that is closed, In Progress, Done or Blocked.
- **`edit` is a success.** The docstring says: "refine cannot write a design for the body, and only a body edit ends the wait." The body stops the design, not the job. Refine writes `edit` when a person changed the section of refine, when the body holds a section that refine has no record of, or when the new body is longer than the limit of GitHub (65536 characters). In each case, refine keeps the text of the person and waits, as its rules tell it to do. A grade is for the job, and no change of the job can make these attempts succeed. A repeated failure of the job on the same body logs `error`, not `edit`, so the failures stay counted.
- **The set stays a literal.** `job_result.py` does not import `refine.py`: refine imports `job_result.py`. The test compares the literal with `NextStep`, so the two cannot go apart.

## Rejected alternatives
- **`edit` as a failure.** The grade would go down for a person edit that the job must keep, and the action of a low grade (larger limits) would change nothing.
- **A set that `job_result.py` derives from `NextStep`.** It needs an import cycle or a move of `NextStep`. The test gives the same guard with no move.
