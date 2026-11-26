# Design

## Decisions

- **A word gives a list of hosts, and the reading of today comes first.** `_hosts_of` yields `_host_of(word)` first. So each form that the check reads today (a bare host, a host with a port, a host with a path, a host in brackets) keeps its result and its message. The other readings only add hosts.
- **The URL parser reads the word and each URL candidate in it.** `urlsplit(word).hostname` reads a word that is a URL with a scheme or a scheme-relative URL. `url_candidates(word)` gives each URL inside a longer word and each URL in the path or the query of another one, and `urlsplit` reads each. The parser handles the port, the user info, the brackets and the case of the host.
- **The word is read again with its percent-encoding decoded one time** (`urllib.parse.unquote`). A URL in a query is percent-encoded in most cases.
- **One extractor.** `url_candidates` in `src/devops_cli/http/urls.py` holds the candidate rule of `urls_in_order`: `CONST_URL_CANDIDATE_RE`, the end at a quote, a backtick or an angle bracket, and no prose punctuation at the end. `urls_in_order` keeps the http and https candidates that the parser reads. `src/devops_cli/ai/web_search.py` already imports `devops_cli.http.urls`.
- **A host has no dot at its end.** `ipaddress.ip_address` refuses an address with a dot at its end, and the dot is the root label of a name. `_hosts_of` removes it from each host.
- **A text that the URL parser refuses is read part by part.** `_url_hosts` takes the NFKC form of the text, which is the form that the check of the parser uses, splits it at each slash and bracket, and reads each part as an address and as a host with no scheme. The check reads the text of a query, and a text that no parser accepts can still name a host. A text with no such host, such as `https://[name]:6443/healthz`, keeps its result.
- **The address rule stays strict.** `_is_private_address` reads a full address with `ipaddress.ip_address` only, so a version such as `10.15` is no address in each form of a word.
- **`_guard` does not change.** The messages and the order of the checks stay: an e-mail address first, then for each host an address and then a name.

## Rejected alternatives

- **Replace `_host_of` with `extract_domain_target` of `src/devops_cli/http/urls.py`.** It returns None for a host with an empty port (`_has_empty_port`), so `urlsplit("//host:/path")`, which `_host_of` reads today, would change its result. It also reads no URL inside a longer word.
- **Call `urls_in_order` of `src/devops_cli/roadmap/page_fetch.py` from the check.** It keeps only http and https URLs (`_is_web_url`), and `page_fetch` imports `normalize_url` from `devops_cli.ai.web_search`, so the import would be a cycle.
- **A second pattern for URLs in `src/devops_cli/ai/web_search.py`.** `CONST_URL_CANDIDATE_RE` is the locator of the project (`src/devops_cli/security/sanitizer.py` and `src/devops_cli/roadmap/page_fetch.py` use it), and rule 3 of AGENTS.md asks for the existing tool.
- **Split each word at each URL delimiter and read each piece as a host.** A path segment would be read as a host: `is_local_or_reserved_domain("settings.local")` is True, so `https://example.com/docs/settings.local` would not reach a provider. The test case `url-path-like-a-name` of `tests/ai/test_web_search.py` holds this.
- **Let the error of the parser leave the check.** `rule_queries` of `src/devops_cli/roadmap/references/queries.py` calls the check for each code span of an item, and `docs/roadmap/alternatives.md` says that a text that the URL parser refuses stops no step.
- **Refuse each query that holds a text that the parser refuses.** `https://[name]:6443/healthz` names no host of a refused kind, and the test case `name-in-brackets` of `tests/ai/test_web_search.py` says that such a query reaches the provider.
