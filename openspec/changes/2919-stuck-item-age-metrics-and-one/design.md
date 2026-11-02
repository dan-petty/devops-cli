# Design

## Decisions

- **Compute the age from the timestamp of the label event that set the state label, through an injectable clock.**: The label event marks the moment the item entered the state, and ADR 0016 keeps the history of each label change in the issue events.
- **Read the alert threshold from the Service configuration with a default.**: The issue says a set time, so the owner can adjust it without a code change.
- **Add the age panel to the existing project-metrics dashboard.**: The dashboard already reads the roadmap gauges, and the panel can sit beside the inbox panel when it arrives.

## Rejected alternatives

- **Compute the age from the issue created_at or updated_at.**: updated_at changes on any edit, and created_at is the issue age, not the state age.
- **Hardcode the alert threshold in the rule.**: The issue says a set time, and a hardcoded value needs a code change and a redeploy to adjust.
- **Wait for the inbox panel before adding the age panel.**: The issue says the age panel does not wait for the inbox panel.
