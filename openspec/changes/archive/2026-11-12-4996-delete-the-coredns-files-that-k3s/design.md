# Design

## Decisions

- Delete the files (option b of #4996). The packaged manifest of k3s is the source of the CoreDNS Deployment, and git describes it in `k8s/README.md` with the live values.
- Keep the test that every pod with an unbound token has an exception. With the files gone, no manifest in the tree is the CoreDNS pod, so the exception has no pod and `test_every_exception_names_a_pod_with_a_token_that_no_role_binds` requires its removal.

## Rejected alternatives

- Option (a): run CoreDNS from its Helm chart with 2 replicas and a larger limit. It needs a change of the k3s server (`--disable=coredns`, or a `.skip` file), which only the owner does. It stays an owner decision on #4989.
- Change the files to the live values (170Mi, 1 replica). Nothing applies them, so they would show a value that git does not control, and drift when k3s changes its manifest.
