"""Valkey access for devops-cli.

The client lives in `client`, the validated URL of the endpoint it dials in `endpoint`, and the
fail-soft tier of the caches, behind a circuit breaker, in `cache`.
"""
