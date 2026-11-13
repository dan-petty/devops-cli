## MODIFIED Requirements

### Requirement: The client price of a hosted group is the price in the gateway config
For each hosted group whose gateway config sets an input price, the client cost of a call SHALL be the cost at the input, cached input, cache write and output prices of that group in `k8s/llm/gateway/config.yaml`. A group that sets no cached input price or no cache write price SHALL cost those tokens at its input price.

#### Scenario: A call with cached tokens
- **WHEN** each hosted group that sets its prices prices a call of 10,000 prompt tokens, 6,000 of them cache reads and 2,000 of them cache writes, and 1,000 completion tokens
- **THEN** the client cost of the call equals the cost at the prices of the gateway config, and the groups include `deepseek-v4.1-flash-1017`, `claude-sonnet-5-5` and `claude-haiku-5-5`

## ADDED Requirements

### Requirement: Each spend-ledger row records its cache read and cache write tokens
Each spend-ledger row SHALL store the prompt tokens that the provider read from its cache (`cache_read_tokens`) and the prompt tokens that it wrote to its cache (`cache_write_tokens`). Both SHALL count inside `prompt_tokens`. A ledger that was created before these columns existed SHALL gain both in place and keep its rows, which read 0 for both.

#### Scenario: A row with cache tokens
- **WHEN** the ledger records a call of 1,550 prompt tokens with 300 cache reads and 1,200 cache writes
- **THEN** the row and the record that the ledger gives back hold 300 cache reads and 1,200 cache writes

#### Scenario: A ledger created before the cache columns
- **WHEN** the ledger opens a database whose table `ai_spend_records` has no cache token columns and holds one row
- **THEN** the table has both columns, the old row reads 0 for both, and a new row keeps its counts

### Requirement: Cache write tokens cost the cache write rate
`track_request_spend` SHALL take the cache write tokens of a call and give them, with the cache read tokens, to the genai-prices price, which costs each at the cache rate of the model. A price override or a built-in group price, which names no cache write rate, SHALL cost a cache write token at the prompt rate.

#### Scenario: Sonnet cache prices
- **WHEN** a gateway call of `claude-sonnet-5-5` uses 2,000,000 prompt tokens, of which 1,000,000 are cache reads and 1,000,000 are cache writes
- **THEN** the call costs 2.60 USD with the pricing source `genai_prices:anthropic`, not 4.00 USD at the input price

#### Scenario: Haiku cache prices
- **WHEN** a gateway call of `claude-haiku-5-5` uses 50,000 prompt tokens, of which 20,000 are cache reads and 20,000 are cache writes
- **THEN** the call costs 0.0037 USD

### Requirement: Each caller gives the cache write tokens of its replies
The spend hook of `build_agent` SHALL give the cache write tokens of each reply (`RequestUsage.cache_write_tokens`). `record_run_spend` SHALL give the sum of the cache write tokens of the replies of a run. A chat call of `LLMClient`, blocking or streamed, SHALL give the cache write tokens that its reply names in `usage.prompt_tokens_details.cache_write_tokens`, and 0 when the reply names none.

#### Scenario: A request of an agent on a Claude group
- **WHEN** a request of an agent on `claude-sonnet-5-5` reports 2,000,000 prompt tokens with 1,000,000 cache reads and 1,000,000 cache writes
- **THEN** the record stores both counts and costs 2.60 USD

#### Scenario: A run of two replies
- **WHEN** a run on `claude-sonnet-5-5` gets two replies, each with 1,000,000 prompt tokens, 500,000 cache reads and 500,000 cache writes
- **THEN** the record stores 1,000,000 cache reads and 1,000,000 cache writes and costs 2.60 USD

#### Scenario: A blocking or streamed chat call on a Claude group
- **WHEN** a chat call or a stream on `claude-sonnet-5-5` gets a reply whose usage names 2,000,000 prompt tokens, 1,000,000 `cached_tokens` and 1,000,000 `cache_write_tokens`
- **THEN** the ledger record stores both counts and costs 2.60 USD
