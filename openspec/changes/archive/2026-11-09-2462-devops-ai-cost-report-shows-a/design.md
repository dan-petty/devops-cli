# Design

## Decisions

- A `ValueError` from `urlsplit(clean).scheme` means that the value is no `http+unix` URL. The guard catches only that one call. The code after it already returns false for an unreadable value, because `extract_domain_target` gives `None` for it. So a call with an unreadable served_by counts as hosted, and the report shows its backend as `unknown`.
- The unit test lists four values, including a comma list, because `_is_local_server` splits a list and needs every part local.

## Rejected alternatives

- Raise a domain error. The report would still stop, and the issue asks that it show the row.
- Check the string with a regex before `urlsplit`. `urlsplit` rejects at least four shapes (`http://[::1`, `http://[`, `http://[::1]x` and a full-width number sign in the host). A regex is a second parser to keep, and it would miss shapes.
- Replace the scheme read with `read_url_or_authority`. That reader returns `None` for `http+unix:///run/docker.sock`, which has no host, so the `http+unix` case would stop working.
