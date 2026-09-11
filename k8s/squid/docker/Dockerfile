# syntax=docker/dockerfile:1
FROM ubuntu:24.04

LABEL maintainer="DevOps CLI Team <dan-petty@github.com>"
LABEL description="High-capacity Squid forward caching proxy with SSL-Bump for Ollama 70B models"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        squid-openssl \
        openssl \
        ca-certificates \
        curl \
        tzdata && \
    rm -rf /var/lib/apt/lists/*

# Pre-create cache and SSL certificate database directories
RUN mkdir -p /var/spool/squid/cache /var/spool/squid/ssl_db /var/log/squid && \
    chown -R proxy:proxy /var/spool/squid /var/log/squid

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3128 3401

ENTRYPOINT ["/entrypoint.sh"]
