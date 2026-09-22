"""
Safety limits for the on-demand scanner when it runs as a public web app. Every limit is OFF
unless its environment variable is set, so a local run is never throttled or restricted:

  WRITE_LIMIT_PER_MINUTE   max scans per visitor per minute
  DAILY_SCAN_LIMIT         max on-demand scans per day, across all visitors (each one launches
                            a real Chromium browser, which is the expensive part)

Blocking requests to internal/private addresses is always on, in local runs too, because a
scanner that fetches "any URL a visitor supplies" is a classic SSRF target: without this, a
visitor could point it at http://localhost, http://169.254.169.254 (a cloud metadata endpoint),
or another machine on the same private network, and get the scanner to fetch it on their behalf.
"""

import ipaddress
import os
import socket
import time
from collections import defaultdict, deque
from urllib.parse import urlparse


def _int_setting(name: str) -> int:
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0


_recent_requests = defaultdict(deque)


def client_ip(request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.remote_addr or "unknown"


def too_many_requests(ip: str, now: float = None) -> bool:
    limit = _int_setting("WRITE_LIMIT_PER_MINUTE")
    if limit <= 0:
        return False
    now = time.time() if now is None else now
    window = _recent_requests[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        return True
    window.append(now)
    return False


_daily = {"day": None, "count": 0}


def daily_scan_allowed(now: float = None) -> bool:
    limit = _int_setting("DAILY_SCAN_LIMIT")
    if limit <= 0:
        return True
    import datetime

    now = time.time() if now is None else now
    today = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%d")
    if _daily["day"] != today:
        _daily["day"], _daily["count"] = today, 0
    if _daily["count"] >= limit:
        return False
    _daily["count"] += 1
    return True


def is_safe_url(url: str) -> tuple[bool, str]:
    """Rejects anything that is not a plain http(s) URL pointing at a public address, so the
    scanner cannot be used to probe the server's own network. Returns (ok, reason)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False, "Could not parse this URL"

    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://"
    if not parsed.hostname:
        return False, "URL must include a domain name"

    hostname = parsed.hostname.lower()
    if hostname in ("localhost", "metadata.google.internal"):
        return False, "This address is not allowed"

    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, "Could not resolve this domain name"

    for family, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, "This address is not allowed"

    return True, ""


def reset() -> None:
    _recent_requests.clear()
    _daily["day"], _daily["count"] = None, 0
