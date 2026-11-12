# Design

## Decisions

- **The marker tells a job comment from a reply, not the author.** The owner's login posts the intake reason and the retitle comment, so an author check would read them as replies. Each roadmap job marks its comments, and refine already reads replies by these markers (`replies_since_refine`).
- **The pass reads the newest comment of its own job.** `replies_after_marker` gives the comments after the newest comment that holds the marker. When one of them holds no job marker, a person replied and the pass leaves the item. A person reply before a later refine comment is a reply that refine already read, so it does not keep the item.
- **The census texts join the one placeholder rule as whole texts.** "Placeholder not final." is an exact entry, not a lead: a real text can start with the word "Placeholder".

## Rejected alternatives

- **Skip only the alternatives comment.** The census shows intake reason and retitle comments after the refine question too, so one marker is not sufficient.
- **A placeholder set of the repair pass only.** The pull form keeps one rule for a placeholder (#3478). A second set would let refine store a text that repair then reads as a stub.
- **A lead "placeholder" that matches any text that starts with the word.** It would refuse a real problem statement such as "Placeholder text in the template is not found".
