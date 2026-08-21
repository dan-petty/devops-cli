1. URL parsing via `urllib.parse.urlparse` checking scheme is strictly 'http' or 'https'.
2. Host resolution to IP addresses with `socket.getaddrinfo` to prevent DNS rebinding.
3. Checking all resolved IPs using `ipaddress.ip_address` to reject private/loopback/link-local ranges (e.g. 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8, 169.254.0.0/16, ::1, fc00::/7).
4. Configurable explicit timeout and redirect disabling or safe redirect validation.
5. Proper exception handling for DNS resolution failures and network timeouts.
