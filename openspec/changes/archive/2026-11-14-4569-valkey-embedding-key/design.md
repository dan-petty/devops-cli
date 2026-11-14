# Design

## Context

`_valkey_key` hashes the configured model and the sent text. `_disk_cache_model` hashes the provider and the model name that the request sends, with the gateway and the direct OpenAI forms apart.

## Goals

- One vector identity across the memory, disk and Valkey tiers.
- The direct and gateway requests of one configured model use different keys.

## Decisions

- **The disk identity in the Valkey hash.** The key holds `_disk_cache_model()`, the configured model and the sent text. The identity already answers the provider and request-name question.
- **The old key is a miss.** A vector written by the old form is no hit, so the first run after the change sends the text once.

## Risks

- A change of the identity invalidates the Valkey vectors of the direct providers. One request fills the new key.

## Tests

- A direct OpenAI write is no hit for the gateway, and both requests are sent.
