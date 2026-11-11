# Design

## Decisions

- Bound the field in `ShadowAnswer`. This is the single point of validation: `observed_issues` already counts a `ValidationError` as unreadable, and `ShadowObservation` validates its answers when intake builds it.
- Keep `ShadowAnswer` a `NamedTuple`. Callers construct and unpack it as a tuple, and only the model that holds it validates it.
- `ShadowIntakeModel.observation` catches `ValidationError`, because the bound can now raise there.

## Rejected alternatives

- A guard or fallback in `_band`: `observed_issues` would not count the mark, and the mark would sit in a band that it does not belong to.
- Make `ShadowAnswer` a `BaseModel`: it changes construction and unpacking for every caller, with no gain.
