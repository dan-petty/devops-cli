# Proposal

## Why

The gateway image sits on the v1.103 line after a security bump, and no document says which release comes next, what the upgrade can break, how the image is pinned, how to test the upgrade or how to undo it, so each bump starts its research from nothing. This change writes that plan for #4406 next to the manifests that the bump changes.

## What Changes

- Add `k8s/llm/gateway/UPGRADE.md` with the target release and its release date, one section for each minor release between the pinned image and that target, and the security support statement with the advisories of the later lines.
- Add the update policy of the gateway image: no minimum release age, the newest release that answers the known security and bug issues and that the config and the clients support, and the pin form of the image, the tag `ghcr.io/berriai/litellm:v1.103.11` with no digest, which the Renovate rule for the package writes.
- Add the `litellm-proxy-extras` section: the version that each release pins, each migration directory added between the pinned release and the target, each change to an applied migration, and the start-up migration path that the gateway deployment sets with `ENFORCE_PRISMA_MIGRATION_CHECK` and `LITELLM_MIGRATION_DIR`.
- Add the offline config-load result of the gateway config under `Router` of the target wheel in a new empty directory: the command, the target, 12 model groups, 7 fallback rules, the `/v1/systemone` pass-through and the pass or fail.
- Add the risk list: one entry for each gateway feature that the upgrade can break, with its place in the gateway config and the check that proves it after the bump.
- Link the documented smoke calls at `k8s/README.md:186:#### Smoke check after a gateway upgrade` and the Jev call, and add only the one missing step for `deepseek-v4.1-flash` with `OPENROUTER_API_KEY`, so the page repeats no documented call.
- Add the rollback to `ghcr.io/berriai/litellm:v1.103.11`, the tag that the gateway deployment pins, with the revert of the image line and the `kubectl rollout undo` command.
- Link `k8s/llm/gateway/UPGRADE.md` from `k8s/README.md`, so `tests/invariants/test_agents_md.py:446:def test_every_hand_written_and_generated_document_is_within_two_links_of_agents_md() -> None:` reaches the new page.
- This change has no spec delta: it adds one hand-written document and one link, and changes no behavior that a consumer observes, no command, no manifest and no service.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Documents: `k8s/llm/gateway/UPGRADE.md`, `k8s/README.md`

## Feasibility

- The probe lines of this run say "The path `k8s/llm/gateway/config.yaml` is a file of the staging commit.", "The path `k8s/llm/gateway/deployment.yaml` is a file of the staging commit." and "The path `k8s/llm/gateway/UPGRADE.md` is no file of the staging commit. No commit in the history deleted or renamed it.", so the plan creates the page beside the two manifests that the bump changes.
- `read_file` of `k8s/llm/gateway/deployment.yaml` lines 30-115 showed `k8s/llm/gateway/deployment.yaml:46:image: ghcr.io/berriai/litellm:v1.103.11`, `k8s/llm/gateway/deployment.yaml:35:terminationGracePeriodSeconds: 600` and `k8s/llm/gateway/deployment.yaml:50:readOnlyRootFilesystem: true`, so the gateway runs the 1.103 line on a read-only root file system.
- The staged tree pins v1.103.11 and not the v1.103.10 of the issue body: `k8s/llm/gateway/deployment.yaml:46:image: ghcr.io/berriai/litellm:v1.103.11`, so the page takes v1.103.11 as the running version and as the rollback target.
- The pin form is confirmed by the same read: `k8s/llm/gateway/deployment.yaml:46:image: ghcr.io/berriai/litellm:v1.103.11` holds a tag and no `@sha256` digest, and `k8s/llm/gateway/deployment.yaml:47:imagePullPolicy: IfNotPresent` follows it, so the gateway image is pinned by tag.
- The Renovate rule for that package is confirmed: `read_file` of `.github/renovate.json` lines 240-248 showed `.github/renovate.json:244: "matchPackageNames": ["ghcr.io/berriai/litellm"],` in a rule whose keys are `description`, `matchPackageNames` and `prBodyNotes` and which sets no `pinDigests` and no `minimumReleaseAge`, so the page states the tag as the pin and invents no digest pin.
- Each item of `what_changes` names only a path that a group changes or creates: `k8s/llm/gateway/UPGRADE.md`, which group 1 creates, and `k8s/README.md`, which group 4 changes; `k8s/llm/gateway/deployment.yaml` is a path that groups 1, 2 and 3 read and no group changes.
- The version rule is confirmed: `CONTRIBUTING.md:35:A dependency, an image, a chart or a tool has no minimum release age.` states the owner rule of 2026-11-11, and the same line continues "Pin the newest release that fixes the known security and bug issues and that the surrounding tools support".
- The count of model groups is 12, from a tool of this run: `read_file` of `k8s/llm/gateway/config.yaml` lines 330-410 showed `k8s/llm/gateway/config.yaml:338:id that /v1/models returns, after the 12 model groups, and a caller does not name it (#5302).`
- The count of fallback rules is 7, not the 6 of the issue body: `read_file` of `k8s/llm/gateway/config.yaml` lines 330-410 showed `k8s/llm/gateway/config.yaml:375: fallbacks:` and the rules of lines 376, 377, 384, 390, 397, 401 and 402, among them `k8s/llm/gateway/config.yaml:390: - claude-sonnet-5-5: [deepseek-v4.1-flash-1017]` and `k8s/llm/gateway/config.yaml:397: - deepseek-v4.1-flash-1017: [deepseek-v4.1-flash]`.
- The hosted groups are confirmed: `SECURITY.md:40:13. **Hosted Models**: The LiteLLM gateway serves five groups that call a provider outside the cluster` names them, and `read_file` of `k8s/README.md` lines 180-220 showed `k8s/README.md:186:#### Smoke check after a gateway upgrade` with the key table at `k8s/README.md:196:| Group | Provider key of the gateway pod |`.
- Group 3 links that smoke section instead of copying it: `read_file` of `k8s/README.md` lines 180-220 showed the four group calls at lines 204-207 and the structured call at line 214, so the page links the section and adds only the call for `deepseek-v4.1-flash`, which the section lacks.
- The `litellm-proxy-extras` risk is confirmed from the tree: `read_file` of `openspec/changes/archive/2026-11-10-4370-bump-the-litellm-gateway-to-v1/proposal.md` lines 36-44 showed `openspec/changes/archive/2026-11-10-4370-bump-the-litellm-gateway-to-v1/proposal.md:40:- Database: `litellm-proxy-extras` goes from 0.4.100 to 0.4.100.post1. It adds no migration.`, so group 2 gives the package and its migrations their own section.
- The migration risk of the start-up is confirmed from the tree: `k8s/llm/gateway/deployment.yaml:103: - name: ENFORCE_PRISMA_MIGRATION_CHECK` and `k8s/llm/gateway/deployment.yaml:107: - name: LITELLM_MIGRATION_DIR` sit in the deployment, and the capability `llm-gateway-database` holds the requirements `The gateway migrates on a read-only root file system` and `A failed migration ends the start-up`, so group 3 gives the migration a risk entry with its check.
- The new page needs a route: `src/devops_cli/docs/inventory.py:27: return next(iter(explicit_classes(path)), CONST_DOCS_CLASS_HAND_WRITTEN)` makes a new Markdown file hand-written, `AGENTS.md:39:| change a manifest, the cluster or OpenTofu | [k8s](k8s/README.md), [cluster](docs/CLUSTER.md), [tf](tf/README.md) |` puts `k8s/README.md` one link from the router, and `tests/invariants/test_agents_md.py:446:def test_every_hand_written_and_generated_document_is_within_two_links_of_agents_md() -> None:` is the test that group 4 runs.
- Not checked: this run read no release list and no advisory feed, so the newest stable tag, its release date, the number of minor releases between the pinned image and the target, and the security support of the 1.103 line are `not checked` here. The count of release sections is unverified, and the first step of the `process` of group 1 is the census of that set: it stops when the number of sections it writes differs from the number of releases between v1.103.11 and the target.
- The first checks against the real system are `curl -s https://api.github.com/repos/BerriAI/litellm/releases | jq` and `curl -s https://api.github.com/repos/BerriAI/litellm/security-advisories | jq`, which need a network to `api.github.com`, and then `uv run --with 'litellm[proxy]==<target>' python -I -c` in a new empty directory, which needs a network to PyPI.
- `Router` of the target wheel takes the `model_list` and the `router_settings` that the step reads from `k8s/llm/gateway/config.yaml`; the call needs a network to PyPI for the wheel as its precondition, and no checkout of the repository and no client of a service.
- The commands of groups 1 and 2 are `uv`, `python` with `-I`, `curl` and `jq`, each a tool of the runner image, so none is `NOT_IN_RUNNER`; they need a network to `api.github.com` and `pypi.org`, and the pod has `readOnlyRootFilesystem: true`, so the scratch directory and the uv cache go under the checkout, which the pod writes.
- Group 4 verifies with `uv run devops ci test tests/invariants/test_agents_md.py`: `uv` and `pytest` come from the runner image, the test reaches no network, no cluster and no scanner, and the pod keeps `readOnlyRootFilesystem: true`, `allowPrivilegeEscalation: false`, `capabilities.drop: ALL` and `runAsNonRoot: true`, so the test writes only to the checkout.
- The rollback commands `kubectl -n llm rollout undo deploy/llm-gateway` and `kubectl -n llm rollout status deploy/llm-gateway` are a person's live step on a host that reaches the cluster; `kubectl` is a tool of the runner image, but the pod holds no cluster token, so no group runs them.
- No open item must merge first: `find_issues` for `litellm gateway` listed `#5091 open build(k8s): move the LiteLLM gateway to v1.109`, `#6001 open chore(k8s): Update the LLM gateway to LiteLLM 1.109.1`, `#4885 open test(k8s): run gateway smoke calls after LiteLLM upgrade` and `#4373 open test(k8s): verify the LiteLLM gateway v1.103.10 rollout`, and each takes its target, its risk list or its steps from this plan, so the dependency list stays empty.
- `read_issue` of `#4370` showed `#4370 issue, closed (completed): fix(k8s): bump the LiteLLM gateway to v1.103.10 for advisories` with `Closed by merged pull request #4374.`, and `read_issue` of `#4289` and `#4296` showed both closed, so the related items of the body are no dependency of this plan.

## Existing Tool Considered

Renovate detects each LiteLLM release, opens the bump pull request, writes the image tag and, through `.github/renovate.json`, sends the merger to this plan. It covers no breaking-change analysis, no offline `Router` load of the gateway config and no live hosted-group call, so the plan states those by hand and builds no code.

## Dependencies

None.
