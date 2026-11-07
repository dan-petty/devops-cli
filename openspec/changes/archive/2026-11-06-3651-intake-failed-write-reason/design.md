# Design

## Decisions

- **Extend `PlacementFailure.error` with the masked text.**: The final `RoadmapIntakeError` and the logger warning both read this field, so one change gives the same reason to both.
- **Mask with `redact_text` before the bound.**: The cut then never leaves a part of a token in the text.
- **Bound the text to `CONST_MAX_ERROR_DETAIL_LENGTH` characters.**: A GitHub error page can be long, and the failure line must stay readable.
- **Keep the class name in front of the text.**: The class tells the kind of error and the text tells the cause.

## Rejected alternatives

- **Change only the logger warning.**: The console does not show the logger warning, so a person would still not see the reason.
- **Change only the final error.**: The logger warning would still receive the unmasked exception.
- **Show the raw exception text.**: A token in the text would reach the console.
