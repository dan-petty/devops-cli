# Design

## Decisions

- **Set `roadmap.implement.max_memory_limit: 16Gi` in the example ConfigMap and keep the code default at 8Gi.**: The value belongs to this cluster and the deploy renders the template, so git holds the limit that the runner Jobs use. The code default stays the product default for every cluster, at `src/devops_cli/config/defaults.py:1054:DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT: str = "8Gi"`.
- **Name the smallest node that can run a runner Job as the bound in the description of the setting.**: The parked node is cordoned (#5143) and runs no runner Job, so its 12.8 GiB bounds nothing, and 16Gi is above it. The memory request sets the placement of a Job, so the limit does not place it.
- **List each test module that reads the example ConfigMap in the `changes` of the group that changes the template.**: The implement job edits no test outside the `changes` of its group, and these tests read the template's config, so the new `roadmap.implement` value must not break one of them without the step that caused it.
- **Leave the Deadline line of `docs/CLUSTER.md` and the CronJob template as they are.**: They state the memory limit of the CronJob `k8s/devops/cronjob-runner.yaml`, which a manual run keeps, and not the setting of the Jobs that the Service creates.
- **Keep the other doubled values that the live ConfigMap holds (#5440) out of this change.**: No acceptance criterion of #5484 names them, and each value needs its own proof that the order checks of the settings accept it. The plan records them here so a follow-up takes them with their own criteria.
- **Prove the live ConfigMap after the merge with a person's deploy and read, not with a test.**: The runner pod holds no Kubernetes token and no test of the repository reaches the cluster, so the third acceptance criterion is a person's step after the merge.

## Rejected alternatives

- **Raise `DEFAULT_ROADMAP_IMPLEMENT_MAX_MEMORY_LIMIT` to 16Gi instead of setting the value in the template.**: It pushes a 16Gi limit into every cluster, also one whose nodes cannot allocate it, and the comment above the default at `src/devops_cli/config/defaults.py:1052` keeps 8Gi below the 15 Gi of the smallest node.
- **Patch the live ConfigMap and leave the template as it is.**: `src/devops_cli/k8s/configmap.py:57:def render_devops_configmap_content(` writes the whole template config again, so the next `deploy-stack` removes a hand-set value; that removal is the defect of the issue.
- **Keep the phrase "the smallest node of the cluster" in the description.**: The parked node is cordoned (#5143) and runs no runner Job, so its 12.8 GiB bounds nothing, and the 16Gi that the two kills proved necessary is above it, which the old text would refuse.

## Security

The template `k8s/devops/configmap.example.yaml` holds no credential: the change adds a memory limit and a comment, and no key that reads a secret. What crosses a trust boundary is the memory that a runner Job may burst above its request, which bounds the other pods of the node; a person must confirm that the node which runs runner Jobs can allocate 16Gi, and that the parked node (#5143) runs no runner Job. `tests/k8s/test_k8s_configmap_keys.py` fails when the rendered ConfigMap loses the value, and `tests/config/test_k8s_devops_runtime.py` fails when the template holds a credential.
