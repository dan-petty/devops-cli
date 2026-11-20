# Design

## Decisions

- **The runner Job reads the keys of a stage Job.** The implement and fix-checks jobs read the App key and the gateway key, as a stage Job does, so the runner template names `CONST_ROADMAP_STAGE_JOB_SECRET_KEYS` and the policy holds one key list for both Jobs. #5498 replaces the list with a row for each job.
- **Both keys are required.** `devops k8s push-secrets` writes both keys in each push (`required` in `cluster_secrets.py`), the live Secret holds both, and the stage template reads them with no `optional`. The keys that `push-secrets` can leave out (the MCP tokens, the Mattermost, Crawl4AI and Firecrawl keys and the webhook secrets) are keys that the runner Job does not read, so no `optional` is needed.
- **The policy keeps `envFrom` of Secret `devops-cli` for a runner Job.** The policy checks an `UPDATE` as a `CREATE`. The Service patches the deadline of a runner Job while it makes progress, up to 14400 s, and resumes a waiting fix-checks Job with a patch. A Job that the Service made before the sync keeps its `envFrom`, so a policy that refuses `envFrom` would refuse those patches, and the Job would end at its old deadline.
- **No sync wave.** In one sync, Argo CD applies the CronJob before the policy. For some seconds, the old policy refuses a Job of the new template. The Service handles a refused create: the implement row takes back the record and the claim, the fix-checks round counts `round_error`, and the next round tries again.

## Rejected alternatives

- **A policy that refuses `envFrom` in each Job of the Service.** It would refuse the deadline patch of each runner Job that runs at the sync (see Decisions). #5498 can refuse it when its table and template test are in place.
- **A sync wave of -1 on the policy.** It removes the seconds of refused creates, but it orders each later sync of the policy before the templates, which is wrong for a change that makes the policy stricter. The Service already retries a refused create.
- **Keep the Valkey password and the Qdrant key for the shell.** The shell of a step gets no key of the pod (`shell_environment`), and the job process uses neither, so the keys give the pod nothing but exposure.
- **Keep `DEVOPS_CLI_MCP_IMPLEMENT_TOKEN` with `optional: true`.** `roadmap.implement.mcp` is off. The stage template set the rule: the change that turns the MCP client on adds the key.
- **A new Secret for the runner.** A person makes Secrets, and #6518 asks for no new Secret and no new key name.
