# Design

## Decisions

- **Gate the rule `digest` on `ACTION_BY_CLASS[class] is FailureAction.RETRY`.**: The table already says whether a new attempt can help. The rule then follows the table, and a class that #3476 adds with the action `retry` clears with no edit here.
- **A stop with no class, or with a class that the table does not know, is not cleared by a digest.**: The rule cannot say that a retry helps, so the stop waits for `implement: retry`.
- **Store the clears in `implement.digest_clears` as a JSON list of `{class, digest, time}` and keep it when a clear removes `implement.stopped` and `implement.failure`.**: The item total is the length of the list and the class total is the count of entries of that class. The list is also the audit trail. Pydantic reads and writes it.
- **Add the settings `roadmap.implement.digest_clears_per_class` (1) and `roadmap.implement.digest_clears_per_item` (3).**: Each retry class gets one automatic clear, and an item spends one on each of the three retry classes at most. A value of 0 turns the digest clear off for that bound.
- **A record that does not parse stops the digest clear for that item and logs a warning.**: The rule fails closed. A person clears the stop with `implement: retry`. The sort of `priority_order` only tests that the record is not empty, so a bad record cannot break a listing.
- **`priority_order` returns `(rank, attempted, number)`.**: Priority stays first, so a retried item of a higher priority goes before a new item of a lower priority, and a new item goes before a retried item inside one priority.
- **Keep the time of the last digest-clear comment in `implement.digest_clear_commented_at`.**: It costs no request and survives a restart. The clear still records its entry when the comment is skipped. The comment of the rule `retry` is not capped, because a person asked for it.
- **Read the clock in `clear_stops` through an argument with a default of the current time.**: A test passes a fixed time.

## Rejected alternatives

- **An allowlist of classes in `stop_clear.py`.**: It copies `ACTION_BY_CLASS` and can drift from it.
- **One limit of 1 for the item.**: It blocks a second retry class that a new image could fix.
- **Two counters in the record.**: They lose the class and the digest of each clear, which the audit needs.
- **Attempt state before priority in the sort.**: A new item of a low priority would go before a retried item of a high priority.
- **Find a comment marker to cap the comments.**: It costs one request for each clear and is fragile.
- **Read the files that an image changed.**: The Service holds only digests and the image has no `image.revision` label, so no map from a digest to commits exists.
