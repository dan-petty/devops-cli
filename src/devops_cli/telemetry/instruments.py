"""The counters and histograms devops-cli sends over OTLP (#564).

Every command runs as its own short-lived process, so a counter or histogram cannot keep a
running total. Each observation is sent as a delta, and the collector's `deltatocumulative`
processor adds a series' deltas up across processes before Prometheus stores them. A histogram
is exponential, so Prometheus stores it as a native histogram under the instrument's own name,
with no `_bucket`, `_sum` or `_count` series (#792); a dashboard reads it with
`histogram_quantile`, `histogram_avg` and `histogram_count`. Dashboards query only the metrics
defined here; `tests/test_telemetry_instruments.py` checks each query.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from devops_cli.config.constants import CONST_METRIC_LABEL_MAX_LENGTH, CONST_METRIC_LABEL_UNSAFE_RE


class InstrumentKind(StrEnum):
    """How a metric accumulates."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class Instrument:
    """A metric devops-cli sends, named as Prometheus stores it."""

    name: str
    kind: InstrumentKind
    unit: str
    description: str


COMMAND_TOTAL = Instrument(
    "devops_cli_command_total", InstrumentKind.COUNTER, "1", "Commands run, by command and status"
)
COMMAND_DURATION = Instrument(
    "devops_cli_command_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Command wall time, by command",
)
USAGE_ERROR_TOTAL = Instrument(
    "devops_cli_usage_error_total",
    InstrumentKind.COUNTER,
    "1",
    "Usage errors of the CLI, by kind (such as unknown_command or unknown_option), command path below devops and caller: person, agent, ci or mcp",
)
SUBCOMMAND_DURATION = Instrument(
    "devops_cli_subcommand_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Sub-command wall time, by command group, sub-command (the command path below devops, such as pr threads reply) and status: ok or error",
)
SUBPROCESS_DURATION = Instrument(
    "devops_cli_subprocess_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Wall time of a program that devops-cli ran, by program and status: ok or error",
)
TELEMETRY_TESTS_TOTAL = Instrument(
    "devops_cli_telemetry_tests_total",
    InstrumentKind.COUNTER,
    "1",
    "Test points that devops telemetry test sent, to show that metrics reach the collector",
)
CI_CHECKS_TOTAL = Instrument(
    "devops_cli_ci_checks_total",
    InstrumentKind.COUNTER,
    "1",
    "Checks that devops ci ran, by step and outcome: pass or fail",
)
CI_GATE_SLOT_WAIT = Instrument(
    "devops_cli_ci_gate_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a devops ci run waited for a free gate slot before its checks started",
)
REVIEW_DURATION = Instrument(
    "devops_cli_review_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Review wall time, by target type",
)
FINDINGS_TOTAL = Instrument(
    "devops_cli_findings_total",
    InstrumentKind.COUNTER,
    "1",
    "Review findings, by producer, severity and status",
)
AI_REQUESTS_TOTAL = Instrument(
    "devops_cli_ai_requests_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM calls and embedding requests, by operation (chat or embeddings), provider, model, server, "
    "serving backend, whether the cache answered and row: the job row that sent the request",
)
AI_TOKENS_TOTAL = Instrument(
    "devops_cli_ai_tokens_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM and embedding tokens, by operation (chat or embeddings), type (prompt or completion), "
    "provider, model, server, backend, row and local: true when a local model ran them. The AI "
    "spend dashboard prices local tokens as savings at the reference price that its constant "
    "reference_price_usd_per_token holds for their operation and type",
)
AI_SPEND_USD_TOTAL = Instrument(
    "devops_cli_ai_spend_usd_total",
    InstrumentKind.COUNTER,
    "USD",
    "Approximate LLM and embedding spend, by operation, provider, model, server, backend and row. "
    "Each request that a model answers adds to it, and a local request adds 0. A hosted gateway "
    "call is priced at the deployment model that the gateway names, and its model label is the "
    "model that the client asked for, such as the route name. A prompt token that the provider "
    "read from its cache costs the cached input rate of the model",
)
AI_MODEL_ANSWERS_TOTAL = Instrument(
    "devops_cli_ai_model_answers_total",
    InstrumentKind.COUNTER,
    "1",
    "Model replies of an agent run, one for each model request, by the model that the client asked "
    "for (asked), the model that the reply names (answered), whether they differ (fallback: true "
    "when a gateway fallback answered) and the job row that sent the request (row). A slot that "
    "reads one model while another answers shows as fallback true",
)
AI_JSON_REPAIRS_TOTAL = Instrument(
    "devops_cli_ai_json_repairs_total",
    InstrumentKind.COUNTER,
    "1",
    "LLM JSON replies repaired after strict parsing failed, by entry point source",
)
AI_GATEWAY_SLOT_WAIT = Instrument(
    "devops_cli_ai_gateway_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a chat call to the LLM gateway waited in this process for one of the gateway's backend "
    "slots, by outcome: ok once it held one, or timeout",
)
AI_OLLAMA_SLOT_WAIT = Instrument(
    "devops_cli_ai_ollama_slot_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a call to Ollama waited in this process for a slot on one of its nodes, by priority "
    "(high, normal or as_available) and outcome: ok once it held one, or timeout",
)
AI_CHAT_DURATION = Instrument(
    "devops_cli_ai_chat_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "LLM chat call wall time, by provider and model, from the request to the reply. A gateway "
    "call's time includes its wait for a backend slot",
)
AI_STRUCTURED_ATTEMPTS_TOTAL = Instrument(
    "devops_cli_ai_structured_attempts_total",
    InstrumentKind.COUNTER,
    "1",
    "Structured-output attempts, by model and outcome: valid when the reply matched its schema, "
    "else invalid. Each invalid attempt but the last is retried",
)
AI_PREWARMS_TOTAL = Instrument(
    "devops_cli_ai_prewarms_total",
    InstrumentKind.COUNTER,
    "1",
    "devops ai prewarm runs, by model, evict (true when the run unloaded the model) and outcome: "
    "ok or failed",
)
AI_GATEWAY_PROBE_DURATION = Instrument(
    "devops_cli_ai_gateway_probe_duration_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time a health probe of the LLM gateway took",
)
AI_GATEWAY_HEALTHY = Instrument(
    "devops_cli_ai_gateway_healthy",
    InstrumentKind.GAUGE,
    "1",
    "Whether the last health probe of the LLM gateway passed: 1, or 0",
)
AI_GATEWAY_FAILOVERS_TOTAL = Instrument(
    "devops_cli_ai_gateway_failovers_total",
    InstrumentKind.COUNTER,
    "1",
    "Failovers of a gateway model alias to its fallback, by virtual model and simulate: true "
    "for a simulated failover",
)
AI_CAPABILITY_GATE_TOTAL = Instrument(
    "devops_cli_ai_capability_gate_total",
    InstrumentKind.COUNTER,
    "1",
    "Failovers to a model below the capability tier of their role, by role, model and decision: "
    "rejection when the gate refused it, or override when --force let it through",
)
RAG_QUERY_DURATION = Instrument(
    "devops_cli_rag_query_duration_ms",
    InstrumentKind.HISTOGRAM,
    "ms",
    "RAG retrieval time, by stage: embedding, search, ranking, or total for the whole query",
)
QDRANT_RETRIES_TOTAL = Instrument(
    "devops_cli_qdrant_retries_total",
    InstrumentKind.COUNTER,
    "1",
    "Qdrant requests retried after a transient error, by operation and error type",
)
RAG_POINTS = Instrument(
    "devops_cli_rag_points",
    InstrumentKind.GAUGE,
    "1",
    "Points stored in RAG vector collections, by collection",
)
GITHUB_REQUESTS_TOTAL = Instrument(
    "devops_cli_github_requests_total",
    InstrumentKind.COUNTER,
    "1",
    "GitHub requests the rate limiter paced, each attempt and retry once, by resource, method, "
    "status, repo and row. The resource is the rate limit resource the request spends, such as "
    "core, graphql or search. The method is the HTTP method; a GraphQL request is a POST, and a gh "
    "command other than gh api is a POST when it writes and a GET when it reads. The status is the "
    "HTTP status of the answer, such as 200 or 304. It is none for a gh command or for an attempt "
    "that got no answer. The repo is the repository of the roadmap Service worker that sent the "
    "request, one of service.repos, and "
    "the row is the job row that sent it, such as metrics, intake, refine or alternatives; each is "
    "other outside a worker or a row. A gh command and a request of the GitHub session both count. "
    "A gh command counts once, also when gh reads many pages for it; devops gh api --paginate "
    "reads a REST GET through the GitHub session, so each page counts. "
    "The counter holds every attempt. The request budget of the Service leaves out the attempts "
    "with status 304, as GitHub does not count them against its rate limit",
)
GITHUB_THROTTLE_WAIT = Instrument(
    "devops_cli_github_throttle_wait_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Time devops-cli waited before it sent a refused GitHub request again, by resource: one "
    "observation for each throttle. GitHub refused the request with a rate limit, or the GitHub "
    "session got a 5xx for a read",
)
GITHUB_GRAPHQL_POINTS_TOTAL = Instrument(
    "devops_cli_github_graphql_points_total",
    InstrumentKind.COUNTER,
    "1",
    "GraphQL points that GitHub reported each answer cost in its rateLimit field",
)
WEB_SEARCHES_TOTAL = Instrument(
    "devops_cli_web_searches_total",
    InstrumentKind.COUNTER,
    "1",
    "Web search attempts, by the provider that ran (the backend, or none) and the result: ok for a "
    "provider that returned hits, empty for one that returned none, the HTTP status of a provider "
    "that refused the search, such as 402 when the account has no credits or 429 at its rate "
    "limit, degraded for a reply that the provider could not read, error for a provider that "
    "did not answer, refused for a query that the guard stopped or an address that the egress check refused, and exhausted for a search that "
    "no provider answered. The backend of the last two is none",
)
CRAWL4AI_FETCHES_TOTAL = Instrument(
    "devops_cli_crawl4ai_fetches_total",
    InstrumentKind.COUNTER,
    "1",
    "Page text fetches through the Crawl4AI service, by result: ok, the HTTP status of a fetch that "
    "the service refused, such as 401 for a wrong token, 429 at its rate limit or 504 when the page "
    "took too long, or error for a fetch that got no answer or a reply that is not page text. A page "
    "URL that the client refuses before it sends a request does not count",
)
ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL = Instrument(
    "devops_cli_roadmap_refine_comments_capped_total",
    InstrumentKind.COUNTER,
    "1",
    "Refine comments that the cap on refine's comments on one item in 24 hours stopped: one "
    "count for each newest comment on an item that the cap left with no answer. The item waits "
    "on a person and takes no place under the round's limit. A later round that finds no newer "
    "comment on the item does not count it again",
)
ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL = Instrument(
    "devops_cli_roadmap_comment_repeats_refused_total",
    InstrumentKind.COUNTER,
    "1",
    "Comments of a roadmap job that the store did not post, by row: the same text, with its "
    "commits, digests and run IDs left out, is in the job's trailing run of comments on the item "
    "and is less than 7 days old. The label row names the job: retitle, refine, alternatives, "
    "intake, stage or implement, so the counter has at most 6 series",
)
ROADMAP_ALTERNATIVES_TOTAL = Instrument(
    "devops_cli_roadmap_alternatives_total",
    InstrumentKind.COUNTER,
    "1",
    "Checks of open items for an open tool that covers them, by verdict: covers, partly, none, "
    "not-applicable, rejected or in-use. One count for each check that the alternatives job writes "
    "to an item. A check that fails, or that the job skips because a person changed the item, "
    "counts nothing",
)
ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS = Instrument(
    "devops_cli_roadmap_alternatives_unchecked_items",
    InstrumentKind.GAUGE,
    "1",
    "Open items that the alternatives check can take and has not checked, by repo. An item in "
    "the retry delay after a failed check counts. An item in progress or from an author with no "
    "write access does not. The Service sends it at the start of each round of the check",
)
ROADMAP_ALTERNATIVES_OLDEST_CHECK_AGE = Instrument(
    "devops_cli_roadmap_alternatives_oldest_check_age_seconds",
    InstrumentKind.GAUGE,
    "s",
    "Age of the oldest alternatives check among the items that the check can take, by repo. The "
    "age is the time since the check was written. Not sent while no such item has a check",
)
ROADMAP_CONFLICTED_PULLS = Instrument(
    "devops_cli_roadmap_conflicted_pulls",
    InstrumentKind.GAUGE,
    "1",
    "Open ready delivery pull requests that GitHub reports with merge conflicts against the "
    "default branch, by repo. The Service sends it at the end of each round of the row "
    "pr_conflicts. A pull request whose mergeable state GitHub has not computed does not count",
)
ROADMAP_ALTERNATIVES_SEARCHES = Instrument(
    "devops_cli_roadmap_alternatives_searches",
    InstrumentKind.HISTOGRAM,
    "1",
    "Web searches that a provider answered for one alternatives check, by verdict. One observation "
    "for each check that the alternatives job writes. A search that no provider answered does not "
    "count. A check that the job skips for its item class runs no search and observes 0",
)
ROADMAP_PAGE_FETCHES_TOTAL = Instrument(
    "devops_cli_roadmap_page_fetches_total",
    InstrumentKind.COUNTER,
    "1",
    "Calls of the tool fetch_page in refine's investigation and in the alternatives check, by "
    "toolset (refine or alternatives) and result: ok for a page whose text the tool returned, "
    "refused for a URL that the tool refused before any request (not https, not named by a search "
    "result or by the item text, or not on a public host), limit for a call over the limit of "
    "fetches for one item, and error for a fetch that failed. The fetches that reach the Crawl4AI "
    "service also count in devops_cli_crawl4ai_fetches_total",
)
ROADMAP_STAGE_TOTAL = Instrument(
    "devops_cli_roadmap_stage_total",
    InstrumentKind.COUNTER,
    "1",
    "Items that a stage round handled, one count for each item, by repository and result: staged for an item "
    "written as a branch and a draft pull request, needs_split for an item stopped on a task "
    "group over the budget, failed for an item that failed in the plan or in the writes, "
    "degenerate for an item whose plan reply was a placeholder in every text (the job sent no "
    "second request), and skipped for an item the job left out with a reason. The label reason "
    "names the rule of a skipped item, such as title_type, held, failed_lately, queue_full, "
    "returned or rejected, and is none for the other results. A plan with no write counts nothing",
)
ROADMAP_STAGE_PLAN_RECORD_TOTAL = Instrument(
    "devops_cli_roadmap_stage_plan_record_total",
    InstrumentKind.COUNTER,
    "1",
    "Uses of the plan file of the stage job, by result: hit for a plan that the job read from the "
    "file and so sent the planner no request, miss for an item with no file of its key, and "
    "written for a plan that the job wrote to the file. A miss that plans adds one to miss and one "
    "to written. The hit rate is hit divided by the sum of hit and miss",
)
DECISION_POINT_TOTAL = Instrument(
    "devops_cli_decision_point_total",
    InstrumentKind.COUNTER,
    "1",
    "Decisions of a registered decision point (ADR 0020), by point, resolver (rule, model or "
    "fallback), band (continue, review or flag, or none for a fallback) and mode (shadow or on). "
    "A point in the mode off, and a point with no rule while ai.decision_model is empty, count "
    "nothing. A point writes only the resolvers that it has: one resolver besides the fallback "
    "gives 8 series, and a rule and a model give 14. The registry refuses a catalogue of more "
    "than 60 series. The registry holds stage.verify_screen, a model and no rule: 8 series. The "
    "decision record and the outcome record of each decision are log lines that share an "
    "identifier, and their join gives the false-clear rate of a point",
)
ROADMAP_TOOL_CALLS_TOTAL = Instrument(
    "devops_cli_roadmap_tool_calls_total",
    InstrumentKind.COUNTER,
    "1",
    "Tool calls of the roadmap planner and verifier, by tool, row, toolset and outcome. The outcome ok is a "
    "call that gave its result. The outcome empty is a call that ran and found nothing, such as "
    "a search with no match. The outcome error is a call that could not run or got no answer. "
    "The row is the job row of the run: stage for the planner, stage_verify for the verifier. "
    "Each run adds 0 for every tool of its toolset before its first model request. So a tool "
    "that no run calls keeps a series",
)
ROADMAP_TOOL_ANSWER_CHARS = Instrument(
    "devops_cli_roadmap_tool_answer_chars",
    InstrumentKind.HISTOGRAM,
    "{char}",
    "Characters in the answer of each tool call of the roadmap planner and verifier, after the "
    "cut of the tool, by tool, row and toolset. The text of a refusal counts. A call that got no answer "
    "adds no observation",
)
ROADMAP_TOOL_CALLS_PER_RUN = Instrument(
    "devops_cli_roadmap_tool_calls_per_run",
    InstrumentKind.HISTOGRAM,
    "{call}",
    "Tool calls of each run of the roadmap planner and verifier, by row and toolset. A run that "
    "raised "
    "because a model call failed adds no observation",
)
ROADMAP_TOOL_LIMIT_HITS_TOTAL = Instrument(
    "devops_cli_roadmap_tool_limit_hits_total",
    InstrumentKind.COUNTER,
    "1",
    "Runs of the roadmap planner and verifier whose tools ended on a limit, by row, toolset and "
    "limit. "
    "The limit calls means fewer tool calls were left than a turn needs. The limit requests "
    "means one model request was left. The limit window means the messages filled the context "
    "window. One count for each run",
)
ROADMAP_AGE_LABELS = ("repo", "state", "plan")
"""The labels of `ROADMAP_ITEM_AGE` and `ROADMAP_OLDEST_ITEM`, in the order the dashboard names them."""
ROADMAP_ITEM_AGE = Instrument(
    "devops_cli_roadmap_item_age_seconds",
    InstrumentKind.GAUGE,
    "s",
    "Age of the oldest open roadmap item in each status, by repo, state and plan. The state is "
    "the status. Plan is true when the item holds a stage pull request. That pull request waits "
    "for a person. The age is the time since the status label was set. Zero when no item is in "
    "the pair",
)
ROADMAP_OLDEST_ITEM = Instrument(
    "devops_cli_roadmap_oldest_item_number",
    InstrumentKind.GAUGE,
    "1",
    "Issue number of the oldest open roadmap item in each pair of repo, state and plan. The pair "
    "is the one that devops_cli_roadmap_item_age_seconds reports. Zero when no item is in the "
    "pair",
)
ROADMAP_CLAIM_AGE = Instrument(
    "devops_cli_roadmap_claim_age_seconds",
    InstrumentKind.GAUGE,
    "s",
    "Age of the oldest claim on an open roadmap item, by repo. The age is the time since the "
    "owner label was set. Zero when no open item holds a claim",
)
ROADMAP_ROW_SECONDS = Instrument(
    "devops_cli_roadmap_row_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Seconds that a roadmap row took to run, one sample for each run, by repo, row and result: "
    "success, error or stopped. A row that is not due, that the failure ledger suspends, or "
    "that a clone failure keeps from running adds no sample. One repository adds at most 36 "
    "series: 12 rows and 3 results",
)
ROADMAP_STEP_SECONDS = Instrument(
    "devops_cli_roadmap_step_seconds",
    InstrumentKind.HISTOGRAM,
    "s",
    "Seconds that one step of a roadmap job took, one sample for each call of the step, by repo, "
    "row, step and result: ok or error. The labels are those of devops_cli_roadmap_row_seconds "
    "with a step. The stage row sends select, plan, gate, review and apply. The implement row "
    "sends checks, publish and watch with the same labels (#4067): checks is one call of the "
    "scoped checks with its fix rounds, publish is the push of the branch with the scoped checks "
    "left out, and watch is one watch of the checks of the pull request, with the result error "
    "when a check failed. The push of a stop is not timed. A refused reply adds a second plan "
    "sample and a second gate sample, so a sample is one call and not one item. A gate that "
    "finds a problem has the result ok. A job with no review model adds no review sample. One "
    "repository adds at most 10 series for the stage row (5 steps and 2 results) and 6 series "
    "for the implement row (3 steps and 2 results): 16 series. The histogram buckets add none",
)
ROADMAP_INTAKE_CANDIDATES_TOTAL = Instrument(
    "devops_cli_roadmap_intake_candidates_total",
    InstrumentKind.COUNTER,
    "1",
    "Candidates that an intake round decided, one count for each candidate, by repo and result: "
    "placed, duplicate, skipped or failed. A candidate that is placed and that the model flags as "
    "a possible duplicate counts as duplicate and not as placed: intake still places it. A "
    "candidate whose item a person changed since the plan counts as skipped, and the next plan "
    "decides it again. A candidate whose write failed counts as failed. A rate limit or an "
    "authentication error ends the round, and the candidates after it count nothing. The round "
    "sends 0 for the four results before its first candidate. One repository adds 4 series",
)
ROADMAP_JEV_COMPLETENESS_TOTAL = Instrument(
    "devops_cli_roadmap_jev_completeness_total",
    InstrumentKind.COUNTER,
    "1",
    "Decisions of the Jev completeness check of a draft pull request, one count for each check, "
    "by outcome: passed (Jev found each acceptance criterion delivered), held (Jev doubts a "
    "criterion or the tests, so the draft stays a draft), error (Jev gave no answer, so the "
    "draft stays a draft) or skipped (the issue lists no criterion or too many, or the diff is "
    "too large). A check adds 1 to its outcome and 0 to the other three, so the four series "
    "exist from the first check. The check runs only when the setting "
    "roadmap.stage.jev_completeness is true. Series: 4 for each scraped pod",
)
ROADMAP_INTAKE_JEV_FIELDS_TOTAL = Instrument(
    "devops_cli_roadmap_intake_jev_fields_total",
    InstrumentKind.COUNTER,
    "1",
    "Proposal fields that intake asked Jev for (#4298, #4395), one count for each field of each "
    "candidate, by field and outcome. The field is type, priority, value, effort or duplicate. "
    "Each mode of roadmap.intake.jev has its own outcomes. With on: jev when the field comes "
    "from the answer of Jev, or fallback when a Jev error, a timeout or a low confidence left the "
    "proposal to the triage model; a proposal falls back as a whole, so its fields all count "
    "fallback. With shadow, the triage model gives every label and Jev decides nothing: agree "
    "when the Jev answer equals the triage answer, differ when it does not, or jev_error when a "
    "Jev error or a timeout left the field with no answer. The type counts only for a candidate "
    "whose title gives no type, and the duplicate counts only for a candidate with a nearest "
    "item. Nothing counts while the setting is off. The metric adds at most 25 series: 5 fields "
    "and 5 outcomes. One mode writes 10 (on) or 15 (shadow) of them",
)
ROADMAP_IMPLEMENT_EXTENSION_TOTAL = Instrument(
    "devops_cli_roadmap_implement_extension_total",
    InstrumentKind.COUNTER,
    "1",
    "Decisions of the rule implement.extension (#4394), one count for each time an implement step "
    "reaches its token budget, by decision: extended (the step got its one extension) or halted "
    "(the step stopped with the class limit_reached). A step that reaches the end of its "
    "extension counts halted, so one step counts at most two decisions. A decision adds 1 to its "
    "series and 0 to the other, so both series exist from the first decision. The metric adds 2 "
    "series",
)
ROADMAP_STAGE_GATE_REFUSALS_TOTAL = Instrument(
    "devops_cli_roadmap_stage_gate_refusals_total",
    InstrumentKind.COUNTER,
    "1",
    "Replies of the stage model that a gate found a problem in, one count for each gate that "
    "found at least one problem in a reply, by repo and gate. A reply that two gates refuse adds "
    "1 to each. The gates run again on the reply that answers a problem, so the count is of "
    "refused replies and not of refused items. One repository adds 16 series, one for each gate",
)
ROADMAP_STAGE_GATE_PROBLEMS = Instrument(
    "devops_cli_roadmap_stage_gate_problems",
    InstrumentKind.HISTOGRAM,
    "1",
    "Findings of the stage checks in one reply of a plan, one observation for each reply that the "
    "checks judged, by repo and reply: 0 for the first reply of a plan run and 1 more for each "
    "return, so at most roadmap.stage.gate_returns plus 1. A reply that passes the checks "
    "observes 0. One repository adds at most 4 series",
)
EMBEDDING_CACHE_LOOKUPS_TOTAL = Instrument(
    "devops_cli_embedding_cache_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Embedding cache lookups, one for each text that an embedding request gets, by result: hit "
    "or miss. A hit names its tier: memory for the cache of the process, valkey, or disk for "
    "the cache file that keeps the vectors of intake between runs",
)
EMBEDDING_CACHE_SIZE = Instrument(
    "devops_cli_embedding_cache_size",
    InstrumentKind.GAUGE,
    "1",
    "Embeddings that the memory cache of the process held after its last embedding request",
)
RAG_EMBEDDING_BATCH_SIZE = Instrument(
    "devops_cli_rag_embedding_batch_size",
    InstrumentKind.GAUGE,
    "1",
    "Texts in each embedding request after the last change of the adaptive batch size",
)
RAG_EMBEDDING_BATCH_RESIZES_TOTAL = Instrument(
    "devops_cli_rag_embedding_batch_resizes_total",
    InstrumentKind.COUNTER,
    "1",
    "Changes of the adaptive embedding batch size, by action: additive_increase after enough "
    "fast batches, or multiplicative_decrease after a slow or failed batch",
)
RAG_DRIFT_SCORE = Instrument(
    "devops_cli_rag_drift_score",
    InstrumentKind.GAUGE,
    "1",
    "Share of a project's files that changed, were added or were deleted since its last index, "
    "from its last drift check, by project. A drifted knowledge base scores 1",
)
RAG_DRIFT_DETECTED = Instrument(
    "devops_cli_rag_drift_detected",
    InstrumentKind.GAUGE,
    "1",
    "Whether the last drift check of a project found drift in its files, its git head or its "
    "knowledge base: 1, or 0, by project",
)
RAG_INVESTIGATIONS_TOTAL = Instrument(
    "devops_cli_rag_investigations_total",
    InstrumentKind.COUNTER,
    "1",
    "RAG context retrievals that finished, by outcome: found when they returned context, or empty",
)
RAG_STOPS_TOTAL = Instrument(
    "devops_cli_rag_stops_total",
    InstrumentKind.COUNTER,
    "1",
    "Processes that turned RAG off for the rest of their run after an embedding failure",
)
RAG_INGEST_RUNS_TOTAL = Instrument(
    "devops_cli_rag_ingest_runs_total",
    InstrumentKind.COUNTER,
    "1",
    "RAG repository ingestion runs, by repo and result: success or error",
)
RAG_INGEST_LAST_SUCCESS_TIMESTAMP = Instrument(
    "devops_cli_rag_ingest_last_success_timestamp_seconds",
    InstrumentKind.GAUGE,
    "s",
    "Timestamp of the last successful RAG repository ingestion run, by repo",
)
VULNERABILITY_LOOKUPS_TOTAL = Instrument(
    "devops_cli_vulnerability_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Packages looked up in a vulnerability database, by source, status and batch: true when one "
    "batch request looked them up",
)
THREAT_INTEL_LOOKUPS_TOTAL = Instrument(
    "devops_cli_threat_intel_lookups_total",
    InstrumentKind.COUNTER,
    "1",
    "Domains that a threat-intelligence source was asked about, by source and status: ok, "
    "unavailable or failed. A domain that the cache answered is not counted",
)

PROJECT_RELEASES = Instrument(
    "devops_cli_project_releases",
    InstrumentKind.GAUGE,
    "1",
    "Total project releases tracked, by repo",
)
PROJECT_COMMITS = Instrument(
    "devops_cli_project_commits",
    InstrumentKind.GAUGE,
    "1",
    "Project commits count by repo and release",
)
PROJECT_PRS = Instrument(
    "devops_cli_project_prs",
    InstrumentKind.GAUGE,
    "1",
    "Project pull requests merged by repo and release",
)
PROJECT_CI_RUNS = Instrument(
    "devops_cli_project_ci_runs",
    InstrumentKind.GAUGE,
    "1",
    "CI workflow runs by repo, workflow, status and conclusion",
)
PROJECT_ITEMS = Instrument(
    "devops_cli_project_items",
    InstrumentKind.GAUGE,
    "1",
    "Roadmap items, the issues with a priority label, by repo, release, state, type and "
    "priority. "
    "The repo is the casefolded owner/name of the repository. "
    "The release is the first v* tag whose commits close the item. "
    "A label is empty when the item has no value for it",
)
PROJECT_ITEM_LABELS = ("release", "state", "type", "priority")
"""The labels of `PROJECT_ITEMS`, in the order the dashboard names them."""
PROJECT_RELEASE_INTERVAL_DAYS = Instrument(
    "devops_cli_project_release_interval_days",
    InstrumentKind.HISTOGRAM,
    "d",
    "Days elapsed between consecutive project releases, by repo and release",
)
PROJECT_TRAFFIC_VIEWS = Instrument(
    "devops_cli_project_traffic_views",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total page views count, by repo",
)
PROJECT_TRAFFIC_VIEWS_UNIQUES = Instrument(
    "devops_cli_project_traffic_views_uniques",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique visitors count, by repo",
)
PROJECT_TRAFFIC_CLONES = Instrument(
    "devops_cli_project_traffic_clones",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository total git clones count, by repo",
)
PROJECT_TRAFFIC_CLONES_UNIQUES = Instrument(
    "devops_cli_project_traffic_clones_uniques",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository unique cloners count, by repo",
)
PROJECT_TRAFFIC_REFERRERS = Instrument(
    "devops_cli_project_traffic_referrers",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic referrals count by repo and referrer source",
)
PROJECT_TRAFFIC_PATHS = Instrument(
    "devops_cli_project_traffic_paths",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository traffic page views by repo and content path",
)
PROJECT_STARS = Instrument(
    "devops_cli_project_stars",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository stargazers count, by repo",
)
PROJECT_FORKS = Instrument(
    "devops_cli_project_forks",
    InstrumentKind.GAUGE,
    "1",
    "GitHub repository forks count, by repo",
)
UPSTREAM_SERVICE_STATUS = Instrument(
    "devops_cli_upstream_service_status",
    InstrumentKind.GAUGE,
    "1",
    "Upstream cloud service operational status severity code (0=none/operational, 1=minor, 2=major, 3=critical) by service",
)
UPSTREAM_COMPONENT_STATUS = Instrument(
    "devops_cli_upstream_component_status",
    InstrumentKind.GAUGE,
    "1",
    "Upstream cloud service component status code (0=operational, 1=degraded, 2=partial_outage, 3=major_outage) by service and component",
)
RESEARCH_OPEN_FINDINGS = Instrument(
    "devops_cli_research_open_findings",
    InstrumentKind.GAUGE,
    "1",
    "Open research findings, by severity: the advisories that affect a pin of the project. `devops research sweep` sets one value for each severity of the scale, with zero for a severity that has no finding. It sets none when a lookup got no answer",
)

INSTRUMENTS: tuple[Instrument, ...] = (
    COMMAND_TOTAL,
    COMMAND_DURATION,
    USAGE_ERROR_TOTAL,
    SUBCOMMAND_DURATION,
    SUBPROCESS_DURATION,
    TELEMETRY_TESTS_TOTAL,
    CI_CHECKS_TOTAL,
    CI_GATE_SLOT_WAIT,
    REVIEW_DURATION,
    FINDINGS_TOTAL,
    AI_REQUESTS_TOTAL,
    AI_TOKENS_TOTAL,
    AI_SPEND_USD_TOTAL,
    AI_MODEL_ANSWERS_TOTAL,
    AI_JSON_REPAIRS_TOTAL,
    AI_GATEWAY_SLOT_WAIT,
    AI_OLLAMA_SLOT_WAIT,
    AI_CHAT_DURATION,
    AI_STRUCTURED_ATTEMPTS_TOTAL,
    AI_PREWARMS_TOTAL,
    AI_GATEWAY_PROBE_DURATION,
    AI_GATEWAY_HEALTHY,
    AI_GATEWAY_FAILOVERS_TOTAL,
    AI_CAPABILITY_GATE_TOTAL,
    RAG_QUERY_DURATION,
    QDRANT_RETRIES_TOTAL,
    RAG_POINTS,
    GITHUB_REQUESTS_TOTAL,
    GITHUB_THROTTLE_WAIT,
    GITHUB_GRAPHQL_POINTS_TOTAL,
    WEB_SEARCHES_TOTAL,
    CRAWL4AI_FETCHES_TOTAL,
    ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL,
    ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL,
    ROADMAP_ALTERNATIVES_TOTAL,
    ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS,
    ROADMAP_ALTERNATIVES_OLDEST_CHECK_AGE,
    ROADMAP_ALTERNATIVES_SEARCHES,
    ROADMAP_CONFLICTED_PULLS,
    ROADMAP_PAGE_FETCHES_TOTAL,
    ROADMAP_STAGE_PLAN_RECORD_TOTAL,
    DECISION_POINT_TOTAL,
    ROADMAP_STAGE_TOTAL,
    ROADMAP_TOOL_CALLS_TOTAL,
    ROADMAP_TOOL_ANSWER_CHARS,
    ROADMAP_TOOL_CALLS_PER_RUN,
    ROADMAP_TOOL_LIMIT_HITS_TOTAL,
    ROADMAP_ITEM_AGE,
    ROADMAP_OLDEST_ITEM,
    ROADMAP_CLAIM_AGE,
    ROADMAP_ROW_SECONDS,
    ROADMAP_STEP_SECONDS,
    ROADMAP_INTAKE_CANDIDATES_TOTAL,
    ROADMAP_JEV_COMPLETENESS_TOTAL,
    ROADMAP_INTAKE_JEV_FIELDS_TOTAL,
    ROADMAP_IMPLEMENT_EXTENSION_TOTAL,
    ROADMAP_STAGE_GATE_PROBLEMS,
    ROADMAP_STAGE_GATE_REFUSALS_TOTAL,
    EMBEDDING_CACHE_LOOKUPS_TOTAL,
    EMBEDDING_CACHE_SIZE,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_EMBEDDING_BATCH_RESIZES_TOTAL,
    RAG_DRIFT_SCORE,
    RAG_DRIFT_DETECTED,
    RAG_INVESTIGATIONS_TOTAL,
    RAG_STOPS_TOTAL,
    RAG_INGEST_RUNS_TOTAL,
    RAG_INGEST_LAST_SUCCESS_TIMESTAMP,
    VULNERABILITY_LOOKUPS_TOTAL,
    THREAT_INTEL_LOOKUPS_TOTAL,
    PROJECT_RELEASES,
    PROJECT_COMMITS,
    PROJECT_PRS,
    PROJECT_CI_RUNS,
    PROJECT_ITEMS,
    PROJECT_RELEASE_INTERVAL_DAYS,
    PROJECT_TRAFFIC_VIEWS,
    PROJECT_TRAFFIC_VIEWS_UNIQUES,
    PROJECT_TRAFFIC_CLONES,
    PROJECT_TRAFFIC_CLONES_UNIQUES,
    PROJECT_TRAFFIC_REFERRERS,
    PROJECT_TRAFFIC_PATHS,
    PROJECT_STARS,
    PROJECT_FORKS,
    UPSTREAM_SERVICE_STATUS,
    UPSTREAM_COMPONENT_STATUS,
    RESEARCH_OPEN_FINDINGS,
)


def emit(instrument: Instrument, value: float, attributes: dict[str, Any] | None = None) -> None:
    """Add to a counter, record a gauge, or observe a histogram value."""
    from devops_cli.telemetry.tracer import get_tracer

    tracer = get_tracer()
    if instrument.kind is InstrumentKind.COUNTER:
        tracer.increment_counter(
            instrument.name, value, unit=instrument.unit, attributes=attributes
        )
    elif instrument.kind is InstrumentKind.GAUGE:
        tracer.record_gauge(instrument.name, value, unit=instrument.unit, attributes=attributes)
    else:
        tracer.record_histogram(
            instrument.name,
            value,
            unit=instrument.unit,
            attributes=attributes,
        )


def bounded_label(value: str) -> str:
    """A label value that a caller set, cut to a safe length and set of characters.

    Each character outside `CONST_METRIC_LABEL_UNSAFE_RE`'s allowed set becomes `_`, and the
    text keeps at most `CONST_METRIC_LABEL_MAX_LENGTH` characters.
    """
    return CONST_METRIC_LABEL_UNSAFE_RE.sub("_", value)[:CONST_METRIC_LABEL_MAX_LENGTH]


def backend_name(served_by: str | None) -> str:
    """A serving backend's short name: its host's first label, e.g. `ollama-16gib` or `ollama-0`."""
    if not served_by:
        return ""
    from devops_cli.http.urls import extract_domain_target

    host = extract_domain_target(served_by) or served_by
    return host.split(".", 1)[0]


__all__ = [
    "AI_CAPABILITY_GATE_TOTAL",
    "AI_CHAT_DURATION",
    "AI_GATEWAY_FAILOVERS_TOTAL",
    "AI_GATEWAY_HEALTHY",
    "AI_GATEWAY_PROBE_DURATION",
    "AI_GATEWAY_SLOT_WAIT",
    "AI_JSON_REPAIRS_TOTAL",
    "AI_MODEL_ANSWERS_TOTAL",
    "AI_OLLAMA_SLOT_WAIT",
    "AI_PREWARMS_TOTAL",
    "AI_REQUESTS_TOTAL",
    "AI_SPEND_USD_TOTAL",
    "AI_STRUCTURED_ATTEMPTS_TOTAL",
    "AI_TOKENS_TOTAL",
    "CI_CHECKS_TOTAL",
    "CI_GATE_SLOT_WAIT",
    "COMMAND_DURATION",
    "COMMAND_TOTAL",
    "CRAWL4AI_FETCHES_TOTAL",
    "DECISION_POINT_TOTAL",
    "EMBEDDING_CACHE_LOOKUPS_TOTAL",
    "EMBEDDING_CACHE_SIZE",
    "FINDINGS_TOTAL",
    "GITHUB_GRAPHQL_POINTS_TOTAL",
    "GITHUB_REQUESTS_TOTAL",
    "GITHUB_THROTTLE_WAIT",
    "INSTRUMENTS",
    "PROJECT_CI_RUNS",
    "PROJECT_COMMITS",
    "PROJECT_FORKS",
    "PROJECT_ITEMS",
    "PROJECT_ITEM_LABELS",
    "PROJECT_PRS",
    "PROJECT_RELEASES",
    "PROJECT_RELEASE_INTERVAL_DAYS",
    "PROJECT_STARS",
    "PROJECT_TRAFFIC_CLONES",
    "PROJECT_TRAFFIC_CLONES_UNIQUES",
    "PROJECT_TRAFFIC_PATHS",
    "PROJECT_TRAFFIC_REFERRERS",
    "PROJECT_TRAFFIC_VIEWS",
    "PROJECT_TRAFFIC_VIEWS_UNIQUES",
    "QDRANT_RETRIES_TOTAL",
    "RAG_DRIFT_DETECTED",
    "RAG_DRIFT_SCORE",
    "RAG_EMBEDDING_BATCH_RESIZES_TOTAL",
    "RAG_EMBEDDING_BATCH_SIZE",
    "RAG_INGEST_LAST_SUCCESS_TIMESTAMP",
    "RAG_INGEST_RUNS_TOTAL",
    "RAG_INVESTIGATIONS_TOTAL",
    "RAG_POINTS",
    "RAG_QUERY_DURATION",
    "RAG_STOPS_TOTAL",
    "RESEARCH_OPEN_FINDINGS",
    "REVIEW_DURATION",
    "ROADMAP_AGE_LABELS",
    "ROADMAP_ALTERNATIVES_OLDEST_CHECK_AGE",
    "ROADMAP_ALTERNATIVES_SEARCHES",
    "ROADMAP_ALTERNATIVES_TOTAL",
    "ROADMAP_ALTERNATIVES_UNCHECKED_ITEMS",
    "ROADMAP_CLAIM_AGE",
    "ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL",
    "ROADMAP_CONFLICTED_PULLS",
    "ROADMAP_INTAKE_CANDIDATES_TOTAL",
    "ROADMAP_ITEM_AGE",
    "ROADMAP_JEV_COMPLETENESS_TOTAL",
    "ROADMAP_OLDEST_ITEM",
    "ROADMAP_PAGE_FETCHES_TOTAL",
    "ROADMAP_REFINE_COMMENTS_CAPPED_TOTAL",
    "ROADMAP_ROW_SECONDS",
    "ROADMAP_STAGE_GATE_PROBLEMS",
    "ROADMAP_STAGE_GATE_REFUSALS_TOTAL",
    "ROADMAP_STAGE_PLAN_RECORD_TOTAL",
    "ROADMAP_STAGE_TOTAL",
    "ROADMAP_STEP_SECONDS",
    "ROADMAP_TOOL_ANSWER_CHARS",
    "ROADMAP_TOOL_CALLS_PER_RUN",
    "ROADMAP_TOOL_CALLS_TOTAL",
    "ROADMAP_TOOL_LIMIT_HITS_TOTAL",
    "SUBCOMMAND_DURATION",
    "SUBPROCESS_DURATION",
    "TELEMETRY_TESTS_TOTAL",
    "THREAT_INTEL_LOOKUPS_TOTAL",
    "UPSTREAM_COMPONENT_STATUS",
    "UPSTREAM_SERVICE_STATUS",
    "USAGE_ERROR_TOTAL",
    "VULNERABILITY_LOOKUPS_TOTAL",
    "WEB_SEARCHES_TOTAL",
    "Instrument",
    "InstrumentKind",
    "backend_name",
    "bounded_label",
    "emit",
]
