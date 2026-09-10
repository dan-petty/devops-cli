#!/usr/bin/env bash
set -euo pipefail

CACHE_DIR="/var/spool/squid/cache"
SSL_DB_DIR="/var/spool/squid/ssl_db"
SSL_DIR="/var/spool/squid/ssl"
LOG_DIR="/var/log/squid"

mkdir -p "${CACHE_DIR}" "${SSL_DB_DIR}" "${SSL_DIR}" "${LOG_DIR}"
chown -R proxy:proxy "/var/spool/squid" "${LOG_DIR}"

# Generate internal Root CA for SSL-Bump if not present
if [ ! -f "${SSL_DIR}/ca.key" ] || [ ! -f "${SSL_DIR}/ca.pem" ]; then
    echo "Generating dynamic Root CA for Squid SSL-Bump in ${SSL_DIR}..."
    openssl req -new -newkey rsa:2048 -days 3650 -nodes -x509 \
      -subj "/CN=DevOps CLI In-Cluster Squid CA/O=DevOps CLI/OU=Caching Proxy" \
      -keyout "${SSL_DIR}/ca.key" -out "${SSL_DIR}/ca.pem"
    chmod 400 "${SSL_DIR}/ca.key"
    chmod 444 "${SSL_DIR}/ca.pem"
    chown -R proxy:proxy "${SSL_DIR}"
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

echo "Starting Squid Cache..."
exec squid -N -d 1 -f /etc/squid/squid.conf
