## ADDED Requirements

### Requirement: A failed model call names its reason
The stage job SHALL name the reason of an item that fails with `AIClientError`: the error code with the HTTP status or the timeout, then the message of the error with each quoted part hidden. It SHALL log one warning line `stage model call failed` with the number of the item, the class of the error, its code, its HTTP status and whether it timed out, and no text of the message. The reason SHALL NOT hold the text that a provider quotes from the model.

#### Scenario: A gateway error
- **WHEN** the model call of item 1 fails with `AIClientError("gateway returned 502", status=502)`
- **THEN** the failure of item 1 has the error `AIClientError`, and its reason holds `HTTP 502` and `gateway returned 502`, and the log holds one line with `item=#1` and `status=502`

#### Scenario: A provider that quotes the model
- **WHEN** the message of the error is `Ollama returned HTTP 500. Response: 'the reply of the model'`
- **THEN** the reason holds `Ollama returned HTTP 500` and does not hold `the reply of the model`
