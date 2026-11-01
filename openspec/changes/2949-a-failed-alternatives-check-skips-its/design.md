# Design

## Decisions

- **The retry interval is 3 days, configurable via roadmap.alternatives.retry_days.**: The issue says 'not in the next round.' One day is the round interval, so it does not meet the requirement. Three days is more than one round and less than the 30-day recheck interval. It gives the upstream service time to recover.
- **The failure record holds the item number, the error class, and the time of the failure.**: These three fields are sufficient to identify the failure, diagnose it, and schedule the retry. They match the pattern of other job records in the project.
- **The row fails and counts toward the 3-round suspension only when zero items were checked in the round.**: The issue states the row fails 'only when no item could be checked in the round (for example no search key or no model).' A partial failure is a normal condition and should not suspend the row.
- **The stop reason uses bounded_text from the #2875 pattern and the readable provider text from #2922.**: The issue explicitly references these two changes for the stop reason format. The bounded_text helper masks secrets and cuts the text to a fixed length.

## Rejected alternatives

- **Retry after 1 day (the next round).**: The issue body says 'not in the next round.' One day is the round interval, so this does not meet the requirement.
- **Retry after 7 days.**: Too long. The item waits a full week before retry, which delays the owner's request to confirm all issues are vetted (issue body, 2026-10-31).
- **Keep the current behavior: fail the round on any item error.**: This is the behavior that caused the suspension on 2026-10-30 (issue body, Evidence section). One bad item blocked the entire repository's alternatives row.
