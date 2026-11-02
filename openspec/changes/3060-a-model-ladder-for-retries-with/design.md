# Design

## Decisions

- **Store the ladder as a map from step class to an ordered tier list in the existing settings.**: The issue asks for a tier per attempt and per step class, and the settings already hold the model overrides of a task.
- **Advance the tier on a provider error and leave the repair round counter unchanged.**: The issue says a provider error moves down the ladder without spending a repair round.
- **Read gateway tier health before each tier choice and skip a tier that it reports unhealthy.**: The issue requires the gateway tier health to be read before a choice.
- **Record the token cost per tier in the record of the implement run, beside the step record.**: The repository has no trace module, and the run record already holds what each step of an item did.
- **Default the ladder to local tiers only.**: The issue requires no hosted-provider call unless the setting names one.

## Rejected alternatives

- **A single global tier list.**: The issue requires a ladder per step class, so plan and repair can use different tiers.
- **Treat a provider error as a normal failure and spend a repair round.**: The issue says a provider error moves down the ladder without spending a repair round.
- **Cache gateway health for a TTL.**: The issue requires gateway tier health to be read before a choice, and a cache returns stale health.
- **Record only an aggregate token total.**: The issue requires the token cost per tier, not only the total.
