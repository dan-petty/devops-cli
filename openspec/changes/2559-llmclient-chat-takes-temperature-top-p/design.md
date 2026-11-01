# Design

## Decisions

- **Pass temperature, top_p, and seed through to the payload and cache key**: The review analysis module already passes these values and expects them to reach the model. The provider APIs support per-request sampling. This is the standard pattern for LLM clients.
- **Per-call value overrides config when not None**: This preserves existing behavior for callers that do not pass per-call values, and gives callers that do pass them the expected result.
- **Omit seed for the Claude provider**: The Anthropic API does not accept a seed parameter. Sending it would cause a 400 error.
- **Remove **kwargs so unknown arguments raise TypeError**: Silently ignoring arguments hides bugs. The three recognized parameters are now explicit. Any other keyword is a caller error.

## Rejected alternatives

- **Remove **kwargs without adding explicit parameters**: This would break the review analysis module (src/devops_cli/review/analysis.py _chat_and_judge), which legitimately passes temperature, top_p, and seed and expects them to reach the model.
- **Per-call value replaces config entirely (no fallback)**: This would require callers to pass all sampling parameters or get no sampling at all. It breaks existing callers that rely on config defaults, such as callers that set ai.temperature in settings and pass no per-call value.
