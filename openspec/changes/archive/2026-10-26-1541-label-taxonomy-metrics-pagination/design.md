# Design: Label Taxonomy Metrics Pagination

## Overview

`get_label_taxonomy_metrics` collects taxonomy label counts for open issues.
This change enables pagination on `GhCliClient.api` and filters pull requests from issue listings.

## Architecture & Data Flow

1. `get_label_taxonomy_metrics` queries `repos/{repo}/issues?state=open&per_page=100` with `paginate=True`.
2. `GhCliClient.api` appends `--paginate` to the `gh api` command and applies `DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS`.
3. `parse_paginated_json` uses `json.JSONDecoder().raw_decode` to parse sequential JSON arrays into a list of dictionaries.
4. `get_label_taxonomy_metrics` iterates over the items, skipping any item that contains a `pull_request` key or is not a dictionary.
5. In tests, `GitHubFake` handles `--paginate` by returning all pages concatenated as JSON arrays, and supports `pull_request=True` on `seed_issue`.
