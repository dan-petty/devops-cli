# Design

## Decisions

- **Return to DeepSeek, not a retry setting.** The failure is the local model's reply format, the same failure that ended the refine trial. A higher retry limit would spend more local time on the same answers.

## Rejected alternatives

- **Keep the trial longer.** 8 of 20 is far under the stop rule of 85%.
