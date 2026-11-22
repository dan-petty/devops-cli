# Proposal: #6757

## Why
Closes #6757. On 2026-11-22 a full `devops ai rag index --include-kb` run stopped with exit 1 after 31 min, at 19456 of 66310 docs chunks, with "Error upserting points into 'devops_docs': Unexpected Response: 502 (Bad Gateway)". The body of the answer was an HTML error page of the proxy in front of Qdrant, and the Qdrant pod had 0 restarts. qdrant-client raises `UnexpectedResponse` for this answer. `_is_transient_qdrant_error` in `src/devops_cli/ai/rag/qdrant.py` does not count it as transient, so `_execute_with_retry` does not send the upsert again, and the first 502 stops the run.

## What Changes
- `_is_transient_qdrant_error` counts an `UnexpectedResponse` as transient when its `status_code` is 429, 502, 503 or 504, and as permanent for each other status. The status alone decides: the words of the answer, such as the reason phrase "Request Timeout" of a 408, do not make an answer transient.
- `_execute_with_retry` does not change. A transient answer gets the same reconnect and backoff as a transport error, and the retry counter `devops_cli_qdrant_retries_total` counts it with the `error_type` `UnexpectedResponse`.
- The loopback server `serving_qdrant` of `tests/support/fakes/qdrant.py` can answer the next requests with a set error status and an HTML body, as a proxy answers them.
- The change alters what a devops command does when a proxy answers 502, so it carries a spec delta.
- The change fits one pull request.

## Capabilities
- `qdrant-request-retry`: new capability, with the ADDED requirements "A gateway or rate-limit answer gets a retry" and "Each other error status ends the operation at once".

## Impact
- Each of the 13 operations of the Qdrant client that go through `_execute_with_retry` (`grep -c "self._execute_with_retry(" src/devops_cli/ai/rag/qdrant.py`) sends a request again after a 429, 502, 503 or 504 answer, up to `DEFAULT_MAX_RETRIES` (3) attempts with waits of 0.5 s and 1.0 s. An index run continues after one bad gateway answer.
- A 408 answer, and an error answer whose text holds a word such as "timeout", now end the operation at once. On the base they got a retry only because of the word in their text.
- `docs/TESTING.md` states that `serving_qdrant` can answer with an error status.

## Feasibility
- Library source: qdrant-client 1.20.0 (`uv pip show qdrant-client`), `ApiClient.send` in `qdrant_client/http/api_client.py` raises `UnexpectedResponse.for_response(response)` for each status other than 200, 201 and 202, and the exception keeps `status_code`. A 429 answer with a `Retry-After` header raises `ResourceExhaustedResponse` instead.
- Base output on origin/main `a3e30286e`: `_is_transient_qdrant_error(UnexpectedResponse(s, reason, b"<html>proxy</html>", Headers()))` gives `False` for 429, 502, 503, 400 and 500, and `True` for 504 and 408, because their reason phrases hold the word "Timeout".
- The premise of the issue holds: the 502 of the run is an `UnexpectedResponse` that the predicate counts as permanent.

## Existing Tool Considered
- httpx 0.28.1: the `retries` of `HTTPTransport` reach httpcore, which retries only `ConnectError` and `ConnectTimeout` while it connects (`httpcore/_sync/connection.py`). It sends no request again after an answer with a status.
- qdrant-client 1.20.0: `upload_points` and `upload_collection` take `max_retries`, but `rest_uploader.upload_batch` retries every exception, a 400 too, and waits with `time.sleep`, past the clock seam. They also replace the `upsert` call of each batch, and the item keeps `_execute_with_retry`. The other calls of the client have no retry of a status.
- `ReadRetryTransport` in `src/devops_cli/http/retry.py` retries the same four statuses, but only for GET, HEAD and OPTIONS. An upsert is a PUT and a search is a POST.
- Build cost: about 10 lines of code and 2 parametrized tests; about 15k tokens and 20 minutes to build, and a low cost to keep, because the rule reads the `status_code` that qdrant-client gives.
- The change deletes no internal code: it adds one branch to `_is_transient_qdrant_error`.
