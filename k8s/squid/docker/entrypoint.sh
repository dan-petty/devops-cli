#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="/var/spool/squid/cache"
SSL_DB_DIR="/var/spool/squid/ssl_db"
SSL_DIR="/var/spool/squid/ssl"
LOG_DIR="/var/log/squid"

mkdir -p "${CACHE_DIR}" "${SSL_DB_DIR}" "${SSL_DIR}" "${LOG_DIR}"

# One-time volume initialization check to avoid slow recursive traversal on restart
if [ ! -f "${CACHE_DIR}/.initialized" ]; then
    echo "First-time volume initialization for ${CACHE_DIR}..."
    chown -R proxy:proxy "/var/spool/squid" "${LOG_DIR}"
    touch "${CACHE_DIR}/.initialized"
    chown proxy:proxy "${CACHE_DIR}/.initialized"
else
    # Non-recursive top-level ownership verification
    chown proxy:proxy /var/spool/squid "${CACHE_DIR}" "${SSL_DB_DIR}" "${SSL_DIR}" "${LOG_DIR}"
fi

# Synchronize Root CA for Squid SSL-Bump
if [ -f "/etc/squid/ssl-ca/ca.key" ] && [ -f "/etc/squid/ssl-ca/ca.pem" ]; then
    echo "Loading pre-provisioned Root CA from /etc/squid/ssl-ca..."
    cp "/etc/squid/ssl-ca/ca.key" "${SSL_DIR}/ca.key"
    cp "/etc/squid/ssl-ca/ca.pem" "${SSL_DIR}/ca.pem"
    chmod 400 "${SSL_DIR}/ca.key"
    chmod 444 "${SSL_DIR}/ca.pem"
    chown -R proxy:proxy "${SSL_DIR}"
elif [ -f "/etc/squid/ssl-ca/tls.key" ] && [ -f "/etc/squid/ssl-ca/tls.crt" ]; then
    echo "Loading pre-provisioned Root CA from /etc/squid/ssl-ca (TLS secret format)..."
    cp "/etc/squid/ssl-ca/tls.key" "${SSL_DIR}/ca.key"
    cp "/etc/squid/ssl-ca/tls.crt" "${SSL_DIR}/ca.pem"
    chmod 400 "${SSL_DIR}/ca.key"
    chmod 444 "${SSL_DIR}/ca.pem"
    chown -R proxy:proxy "${SSL_DIR}"
elif [ -f "${SSL_DIR}/ca.key" ] && [ -f "${SSL_DIR}/ca.pem" ]; then
    echo "Using existing persisted Root CA in ${SSL_DIR}..."
else
    echo "FATAL: Pre-provisioned Root CA missing from /etc/squid/ssl-ca. Ensure Kubernetes Secret 'squid-ca-secret' is provisioned before deploying Squid." >&2
    exit 1
fi

# Initialize SSL cert database if not present
if [ ! -d "${SSL_DB_DIR}/certs" ]; then
    echo "Initializing Squid SSL certificate database in ${SSL_DB_DIR}..."
    rm -rf "${SSL_DB_DIR}"
    /usr/lib/squid/security_file_certgen -c -s "${SSL_DB_DIR}" -M 16MB
    chown -R proxy:proxy "${SSL_DB_DIR}"
fi

# Initialize cache directories if not present
if [ ! -d "${CACHE_DIR}/00" ]; then
    echo "Initializing Squid cache swap directories in ${CACHE_DIR}..."
    squid -z -N -f /etc/squid/squid.conf
fi

# Ensure access log exists and stream to stdout for container log collection
touch "${LOG_DIR}/access.log"
chown proxy:proxy "${LOG_DIR}/access.log"
tail -F -n 0 "${LOG_DIR}/access.log" &

echo "Starting Squid Cache..."
exec squid -N -d 1 -f /etc/squid/squid.conf
