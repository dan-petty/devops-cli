# Design

## Context

SearXNG has no limiter and no login in this setup, and it sends the query of the roadmap Service to public search engines. So the NetworkPolicy is the access control, and the engine list is the quality control.

## Decisions

- **The default perimeter skips the pod; the pod has its own policy.** `devops-default-perimeter` selects the pods of the namespace with `matchExpressions NotIn` on `app.kubernetes.io/name`, the shape that Crawl4AI already uses, and the list gains `searxng`. The search pod needs neither the gateway nor the cache Valkey. *Rejected:* an extra deny policy, because policies only add allowances, so the pod would keep the allowances of the default perimeter.
- **Egress is DNS and public TCP 443.** The ranges removed are those of the default perimeter. The engines call HTTPS only (see Feasibility). *Rejected:* port 80 as well, because no engine needs it.
- **Ingress is a pod selector peer alone.** The comment in the default perimeter records that kube-router refused a namespace and pod selector peer paired with `ports`.
- **The client rule is a separate file named `searxng-clients`.** It sits in the `searxng/` folder, so the manifests of the roadmap Service stay as they are.
- **The limiter stays off.** The limiter needs Valkey (a policy change for `valkey-devops`) and its header checks refuse a plain machine client. The perimeter replaces it. *Rejected:* the limiter with Valkey.
- **The settings are a ConfigMap, and the secret is an environment variable.** SearXNG reads `SEARXNG_SECRET` before the file, so the file holds no secret. *Rejected:* a Secret for the whole file, which a keyed engine such as `braveapi` would need.
- **One file is mounted, with `subPath`.** A mount of the whole directory is owned by root, and the entrypoint warns of it. The `subPath` mount leaves `/etc/searxng` as the directory of the image, which user 977 owns. The file does not follow a ConfigMap change, which is right: a change of the settings is a new rollout.
- **An IPv4 bind.** `GRANIAN_HOST=0.0.0.0`. The default `::` takes IPv4 only when the node allows it.
- **Only keyless engines are kept.** The scraping engines of Google, Bing, Brave, Startpage, Mojeek and Qwant were suspended by their upstream sites in October 2026. The keyed Brave engine is not used (owner decision of 2026-11-07). A test holds that none is kept and that every kept name exists in the default settings of the pinned image.
- **The engine names are a committed file.** The test of the kept names cannot reach the network or the image, so `tests/fixtures/searxng/default_engine_names.txt` holds the names of the pinned image. A second test reads the tag in its first line and compares it with the tag of the Deployment, so a bump without a refresh fails. *Rejected:* a test that runs the image (needs a container host that CI jobs and some workstations lack).
- **Startup, readiness and liveness probes on `/healthz`.** The liveness probe waits 10 s and fails three times at 30 s intervals, because a search holds the 4 worker threads for up to the engine timeout.
- **The limits are the measured peak with a margin.** The peak of 20 queries was 117 MiB, so the limit is 384 Mi (about three times) and the request 192 Mi.
- **Renovate gets a rule with a note.** The file sets no minimum release age for other images, and SearXNG publishes many tags a day. The note tells the person to check the 14-day age. *Rejected:* `minimumReleaseAge` for this image, because the issue asks for the note and a person reads each bump.
