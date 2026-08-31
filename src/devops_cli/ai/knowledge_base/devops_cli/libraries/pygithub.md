# Code Library: PyGithub (GitHub REST & GraphQL API Client)

## 1. Project References

| Resource | Endpoint / URL |
| :--- | :--- |
| **Official Documentation** | [pygithub.readthedocs.io](https://pygithub.readthedocs.io/) |
| **Public Git Repository** | [github.com/PyGithub/PyGithub](https://github.com/PyGithub/PyGithub) |
| **Official PyPI Package** | [pypi.org/project/PyGithub](https://pypi.org/project/PyGithub/) (`2.10.0`) |
| **DevOps CLI Integration** | [`src/devops_cli/commands/pr.py`](file:///workspaces/devops-cli/src/devops_cli/commands/pr.py) • [`src/devops_cli/commands/release.py`](file:///workspaces/devops-cli/src/devops_cli/commands/release.py) |

---

## 2. General Information & Architecture

**PyGithub** is a Python library for accessing the GitHub REST API v3 and GitHub GraphQL API. It manages GitHub repositories, Pull Requests, remote CI workflow checks, release assets, and SSH signing keys.

In `devops-cli`:
- **PR Management**: Powers `devops pr list`, `devops pr view`, `devops pr diff`, and `devops pr checks`.
- **Review Comment Posting**: Formats multi-persona review findings into collapsible markdown comments and posts them to target PRs (`devops review pr <num> --post-pr`).
- **Release Automation**: Automates version tag pushes, changelog publication, and GitHub Release asset creation (`devops release prepare`).

---

## 3. Comparable Projects & Tradeoffs

| Library | Strengths | Weaknesses | Why `devops-cli` Chose PyGithub |
| :--- | :--- | :--- | :--- |
| **`PyGithub`** | Complete coverage of GitHub REST API v3, stable object models, automatic pagination, typed exception taxonomy. | Synchronous network I/O. | **Selected**: The most mature, reliable, and widely documented GitHub API client in Python. |
| **`gh` CLI Subprocess** | Uses user's already-authenticated GitHub CLI session. | Brittle JSON parsing across differing `gh` versions, slower execution due to process spawn overhead. | Used as fallback when PAT is absent. |
| **`githubkit`** | Async/sync generated SDK based on OpenAPI specs. | Frequent massive code generation updates, larger package size. | Rejected: PyGithub is more established and stable. |
| **Direct REST Requests (`httpx2`)** | Zero extra dependency. | Requires hundreds of lines of boilerplate for pagination, rate limiting, and error parsing. | Rejected: PyGithub encapsulates all pagination and error handling. |

---

## 4. Key Concepts & Core Patterns

1. **`Github` Instance**: Authenticated via OS Keyring Personal Access Token (`github.token`) or environment variable (`GITHUB_TOKEN`):
   ```python
   from github import Github, Auth

   gh = Github(auth=Auth.Token(token))
   ```
2. **Repository & Pull Request Navigation**:
   ```python
   repo = gh.get_repo("dan-petty/devops-cli")
   pr = repo.get_pull(123)
   ```
3. **Automated Pagination**: PyGithub `PaginatedList` automatically streams next-page API requests transparently when iterating over results.
4. **Rate Limit Inspection**: `gh.get_rate_limit()` checks remaining API calls to prevent 429 rate limit bans.

---

## 5. Common & Advanced Usage Examples

### Fetching PR Details and Posting Review Findings
```python
from github import Github, Auth, GithubException


def post_pr_review_comment(token: str, repo_name: str, pr_number: int, comment_body: str) -> None:
    gh = Github(auth=Auth.Token(token))
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.create_issue_comment(comment_body)
    except GithubException as exc:
        print(f"Failed to post comment to PR #{pr_number}: {exc.data.get('message', exc)}")
```

---

## 6. Best Practices & Security Standards

1. **Zero Token Hardcoding**: Always retrieve GitHub tokens from `devops_cli.config.keyring_vault` or `get_github_token()`.
2. **Rate Limit Defense**: Catch `github.RateLimitExceededException` and display the reset timestamp to the user.
3. **Redact Private Repo Metadata**: Ensure error messages mask internal repository URLs and tokens before emitting to CLI logs.
