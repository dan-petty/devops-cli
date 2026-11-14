# Design

## Decisions

**The Service reads its key from its own Secret.** A virtual key has a budget and a requests-per-minute limit that the master key does not. The Secret `roadmap-service-llm-key` holds only that key, so a rotation changes one Secret.

**The pod template loses `envFrom` and names each other key.** `envFrom` would load the master key into the pod even if `DEVOPS_CLI_AI_API_KEY` came from another Secret: the later source wins, but the pod still holds the master key in its environment. Explicit references remove every key that the Service does not need. The four optional keys stay optional, so a repository without Firecrawl or Valkey starts.

**The person mints the key, and the repository holds only its name.** AGENTS.md gives secret changes to a person. The README gives the `/key/generate` call, the keyring entry, the push and the rotation, and the pull request holds no key value. The `CLUSTER_SECRETS` row `devops/roadmap-service-llm-key` carries the keyring source with `required: false`, so `devops k8s push-secrets` writes the Secret and `deploy-stack` runs before the key exists.

**The other cluster Jobs keep the master key.** #1635 puts their key change out of its scope, and the stage Job admission rule admits the master key only to a stage Job. This change touches the Service Deployment alone.

## Rejected alternatives

- **Keep `envFrom` and override the key.** The pod would still hold the master key in its environment.
- **Change the Jobs too.** #1635 excludes them, and their key is the subject of another issue.
