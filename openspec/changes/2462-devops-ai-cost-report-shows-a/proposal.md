# Proposal

## Why

Issue #2462 reports that `devops ai cost report` stops with `ValueError: Invalid IPv6 URL` when the spend ledger holds a served_by value such as `http://[::1`. `_is_single_server_local` in `src/devops_cli/ai/spend/pricing.py` calls `urlsplit(clean)` on the stored value with no guard. `extract_served_by` refuses such a value in a new row, but a ledger row from before that change can hold one. The report must show the row and show its serving backend as `unknown`.

## What Changes

- Guard the `urlsplit(clean).scheme` read in `_is_single_server_local`. A `ValueError` means that the value is no `http+unix` URL. The code after the read already returns false for such a value.
- Add the failing tests first. `test_ai_spend_pricing.py` gets one test of `is_local` over four served_by values. `test_ai_served_by.py` gets two cases in its existing table test of `devops ai cost report --by backend`.
- Add a spec delta. The change is observable, because `devops ai cost report` exits 1 today. `ai-spend-pricing` gets one new requirement for the locality of an unreadable value. `ai-reply-server` gets one new scenario for its existing display requirement.
- The change fits one pull request. It has one task group.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-spend-pricing`: ADDED the requirement "A stored serving backend that no URL reader accepts is hosted".
- `ai-reply-server`: MODIFIED the requirement "A served_by display shows the server without userinfo". The requirement text stays. One scenario is new.

## Impact

- Code: `src/devops_cli/ai/spend/pricing.py` (`_is_single_server_local`).
- Tests: `tests/ai/spend/test_ai_spend_pricing.py`, `tests/ai/client/test_ai_served_by.py`.
- Specs: `openspec/specs/ai-spend-pricing/spec.md`, `openspec/specs/ai-reply-server/spec.md`.
- No command, option, message or document changes. The change regenerates no document.

## Existing code

- `_is_single_server_local`, `_is_local_server` (it splits a comma list and needs every part local) and `is_local` in `pricing.py` keep their shape. Only the scheme read changes.
- `_served_by_label` in `src/devops_cli/commands/ai_cost.py` and `served_by_authority` in `src/devops_cli/ai/client/models.py` already give `unknown` for `http://[::1`. They stay as they are.
- `CONST_AI_BACKEND_HOST_UNKNOWN` stays the label text.
- The tests that must keep passing: `test_a_gateway_call_is_local_by_the_backend_that_served_it` and `test_is_local_configured_cluster_and_gateway` in `tests/ai/spend/test_ai_spend_pricing.py`, and `test_cost_command_names_a_serving_backend_by_its_host_and_port` in `tests/ai/client/test_ai_served_by.py`.

## Acceptance

Each criterion of #2462 maps to the one group of `tasks.md`.

| Criterion of the issue | Delivered by |
| :--- | :--- |
| Report does not crash on unparseable served_by | Group 1: the guard (task 1.2); the cases `unreadable-url` and `unclosed-bracket` (task 1.1) |
| Unparseable backend shows as unknown | Group 1: the case `unreadable-url` of the `--by backend` table test (task 1.1) |
| Valid served_by values still resolve | Group 1: the cases `local-url` of both tests (task 1.1); they pass on the base and pin the behavior |

No criterion waits for a person.

## Feasibility

All commands ran on `origin/main` at `1c20865a`, in the worktree of this change.

- The unguarded call exists. `grep -n urlsplit src/devops_cli/ai/spend/pricing.py` prints line 229 (`_is_local_host`) and line 247 (`_is_single_server_local`, `urlsplit(clean).scheme == "http+unix"`). The issue says line 243; the line moved, the code did not.
- The stdlib raises. `urlsplit("http://[::1")` raises `ValueError: Invalid IPv6 URL`. `http://[`, `http://[::1]x` and `http://a＃b` (a full-width number sign) raise too, so one guard covers all four shapes, and a regex pre-check would not.
- The crash reproduces end to end. A temporary ledger with one `record_request(provider="gateway", server="gateway.example.com", model="m", ..., served_by="http://[::1")` and `CliRunner().invoke(app, ["ai", "cost", "report", "--by", "backend"])` gives exit code 1 with `ValueError('Invalid IPv6 URL')`.
- The path is as the plan says. The traceback ends `ledger.py:341 _tally_and_annotate_servers` -> `pricing.py:291 is_local` -> `pricing.py:264 _is_local_server` -> `pricing.py:247 _is_single_server_local` -> `urlsplit`. `get_lifetime_report` runs this path, so every `devops ai cost report` fails, not only `--by backend`.
- The code after the read is safe. For the four unreadable values, `extract_domain_target(value)` prints `None`, so `_is_single_server_local` returns false after the guard. The other `urlsplit` call (line 229) reads a host that `extract_domain_target` has already checked, so it cannot raise for this input.
- The display needs no change. `served_by_authority("http://[::1")` prints `None`, and `_served_by_label` (`ai_cost.py:212`) turns `None` into `unknown`.
- New rows cannot hold the value. `extract_served_by({"x-litellm-model-api-base": "http://[::1"})` prints `None`, and the same call with `http://localhost:11434` returns the URL. Only old ledger rows are at risk.
- Nothing newer did this. `git log --oneline -3 -- src/devops_cli/ai/spend/pricing.py` ends at `5d86538a` (#2555), and `git log --oneline -3 -- src/devops_cli/commands/ai_cost.py` ends at `0df9777d` (#2884). Neither touches the scheme read. No other active change under `openspec/changes/` names `pricing.py`, `ai-spend-pricing` or `ai-reply-server`. An open-issue search for `urlsplit` finds only #2462 and an unrelated Argo issue.
- Valid values still work. `is_local(server="gateway.example.com", provider="gateway", served_by="http://localhost:11434")` prints `True`, and the same call with `https://api.openai.com` prints `False`.
- The test files are real. `git ls-files tests/ai/spend/test_ai_spend_pricing.py tests/ai/client/test_ai_served_by.py` lists both. The first holds `test_a_gateway_call_is_local_by_the_backend_that_served_it`. The second holds `test_cost_command_names_a_serving_backend_by_its_host_and_port` with the case `no-server`. `tests/test_pricing.py` does not exist.
- The spec base is real. `openspec/specs/ai-reply-server/spec.md` holds the requirement "A served_by display shows the server without userinfo", and its scenario "A stored value that names no server" already shows `unknown`. `openspec/specs/ai-spend-pricing/spec.md` has no requirement on the locality of a stored value.

## Existing Tool Considered

No external tool covers this need. The need is one `try`/`except` around one stdlib call. `read_url_or_authority` in `src/devops_cli/http/urls.py` is the project reader that returns `None` for an unreadable value, but it returns `None` for `http+unix:///run/docker.sock` too (it has no host), so it cannot replace the scheme read. The written cost is about 5 lines of code and 25 lines of test, about 6,000 tokens to write and review, in one session. No dependency is added. The change deletes no internal code.
