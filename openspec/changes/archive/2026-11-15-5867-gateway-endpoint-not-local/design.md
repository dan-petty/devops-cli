# Design

## Decisions
- Detect gateway proxy endpoints by matching against known gateway service names, the `server` argument, or configured gateway URLs in settings.
- When `served_by` names the gateway proxy rather than a downstream backend, ignore it during route-based local backend evaluation.
- When a gateway request names no downstream backend, use the requested or answered model to determine whether the call is local or hosted.
- Omit the backend label on metrics when no downstream backend served the call, preventing `backend="llm-gateway"` on hosted model tokens.

## Rejected alternatives
- Stripping `m.served_by` in `pydantic_ai_bridge.py`: rejected because `factory.py` and other callers use `m.served_by` to identify gateway-targeted requests.
- Unconditionally setting `served_by=None` in `factory.py`: rejected because tests and mock models rely on passing custom backend endpoints for reporting.
