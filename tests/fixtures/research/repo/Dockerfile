# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.14-slim-trixie AS builder
COPY --from=uv /uv /usr/local/bin/
COPY --from=ghcr.io/example-org/tool:1.2.3 /tool /usr/local/bin/tool

FROM builder AS runner
