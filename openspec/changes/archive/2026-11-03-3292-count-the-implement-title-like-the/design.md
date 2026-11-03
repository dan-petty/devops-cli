# Design

## Decisions

- **Keep the whole summary in `delivery_title`, as #3200 decided.**: A cut title ends with `...` and hides the summary. `staging_title` already keeps the whole summary, so the delivery title does the same and the job stops on a title that the form refuses.
- **Check the delivery title with `title_problems` in `_delivery_title` before the job writes it.**: The form check already holds the form, the type, the scope and the 60-unit limit, and `devops pr create` calls it. One caller in the implement job closes the gap between the job and the check, with no second rule.
- **Check before the first push of a Planned item.**: `_publish` now computes and checks the title before `git push`. A refused title leaves no branch on `origin` without a pull request.
- **State the limit in UTF-16 code units in the `roadmap-implement-job` requirement.**: The check runs `^.{1,60}$` in JavaScript and counts an emoji as two. The specification must state the count that the code uses.
- **Test the stop in `tests/roadmap/test_roadmap_implement_job.py` with a patched title.**: The test proves that the job writes no title and stops the item. A long issue title in the fixture would also run every step and slow the suite.

## Rejected alternatives

- **Cut the summary at 60 units, as #3292 first proposed.**: `#3200` and `#3367` decided that a title holds the whole summary. A cut hides it and makes the pull request title differ from the issue title.
- **Let the CI check fail after the push.**: The job has already pushed the branch and spent tokens. A stop before the write names the problem and leaves no branch without a pull request.
- **Count code points in the job and let the check count units.**: The two counts disagree for an emoji, which is the defect of #3292.
