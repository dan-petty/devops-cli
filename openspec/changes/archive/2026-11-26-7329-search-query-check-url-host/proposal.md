# Proposal: #7329

## Why

The check of a web search query reads the host of each word of the query (`_host_of` in `src/devops_cli/ai/web_search.py`). It parses the word with `urlsplit(f"//{word}")`. For a word that is a URL with a scheme, that call gives the scheme as the host (#7329). So the check of a URL word does not read the host that the word names, and its result for the word differs from its result for the bare host.

## What Changes

- The check reads a list of hosts for each word (`_hosts_of`). The list holds the host of the word as a host with no scheme, which is the reading of today, and the host of each URL that the word is or holds. The standard URL parser (`urllib.parse.urlsplit`) reads each URL.
- The check reads these forms of a word and gives the result of the bare host for each: a URL with a scheme (with a port, a path, a query, a fragment, upper-case letters or IPv6 brackets), a scheme-relative URL, a URL inside a longer word (in parentheses, quotes, angle brackets or a Markdown link, and after a prefix such as `url=`), and a URL in the path or the query of another URL, percent-encoded one time or not.
- A dot at the end of a host does not change the result.
- A text that the URL parser refuses raises no error out of the check. The check reads each part of the text between a slash and a bracket as an address or as a host with no scheme.
- `url_candidates` in `src/devops_cli/http/urls.py` holds the rule that finds the URL candidates of a text. `urls_in_order` in `src/devops_cli/roadmap/page_fetch.py` calls it and keeps its result, so the project has one extractor.
- The refusal messages of `_guard` and the order of its checks do not change.
- The behavior of a command changes, so the change has a spec delta.
- The tests give 22 URL forms and 4 forms with no scheme for 5 hosts of the refused kinds and for 1 public host.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-search`: The guard reads the host of a word in each form of the word, A text that the URL parser refuses raises no error out of the guard

## Impact

- Code: `src/devops_cli/ai/web_search.py`, `src/devops_cli/http/urls.py`, `src/devops_cli/roadmap/page_fetch.py`, `src/devops_cli/roadmap/references/queries.py` (docstring)
- Documents: `docs/roadmap/alternatives.md`
- Tests: `tests/ai/test_web_search.py`, `tests/roadmap/references/test_reference_queries.py`
- Callers of the check: `web_search`, the tools `research_lookup` and `research_grep` (`src/devops_cli/roadmap/ask_tools.py`) and the reference step (`src/devops_cli/roadmap/references/queries.py`). Each gets the same messages as before.

## Feasibility

- Python 3.14, `urllib.parse`: `urlsplit("//docs.example.com").hostname` gives `docs.example.com`, and `urlsplit("//https://docs.example.com/page").hostname` gives `https`. `urlsplit("https://docs.example.com/page").hostname` and `urlsplit("//docs.example.com/page").hostname` give `docs.example.com`.
- `urlsplit` raises `ValueError` for two classes of text only (CPython `Lib/urllib/parse.py`, `_check_bracketed_netloc` and `_checknetloc`): a bracket in the host part that holds no IPv6 address, and a character that NFKC changes to a URL delimiter. So the fallback for a refused text has two cases to read.
- `CONST_URL_CANDIDATE_RE` (`src/devops_cli/config/constants.py`) finds each text with a scheme and `://` in a word, and stops a candidate where the next one starts. So it also gives a URL in the path or the query of another URL.
- `uv run devops ci test tests/roadmap/test_roadmap_page_fetch.py` passes with `urls_in_order` on `url_candidates`, so the move keeps the behavior of the page fetch.

## Existing Tool Considered

The standard library covers the need: `urllib.parse.urlsplit` and `urllib.parse.unquote` read a URL, `ipaddress` reads an address, and `unicodedata.normalize` gives the NFKC form that the URL parser itself uses. The project already has the URL locator `CONST_URL_CANDIDATE_RE` and the host classifier `is_local_or_reserved_domain` (tldextract). The change adds no dependency and writes no parser. It deletes the candidate loop of `urls_in_order`, which moves to `url_candidates`.
