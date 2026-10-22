"""Client IP resolution behind Railway's proxy.

X-Forwarded-For is a comma-separated list that each proxy *appends* to. The
left-most entries are whatever the client claimed and can be forged; only the
entries appended by proxies we control are trustworthy. With
TRUSTED_PROXY_COUNT = N, the real client address is the N-th entry from the
right. Railway's edge appends exactly one hop, so production uses N = 1.
With N = 0 (local dev, no proxy) X-Forwarded-For is ignored entirely.
"""
import ipaddress

from django.conf import settings


def _valid(ip):
    try:
        return str(ipaddress.ip_address(ip.strip()))
    except (ValueError, AttributeError):
        return None


def client_ip(request):
    """Best-effort client IP, or None if it cannot be determined."""
    remote = _valid(request.META.get('REMOTE_ADDR', ''))
    count = getattr(settings, 'TRUSTED_PROXY_COUNT', 0)
    if count <= 0:
        return remote
    forwarded = [p for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    if len(forwarded) >= count:
        return _valid(forwarded[-count]) or remote
    return remote


def ratelimit_ip_key(group, request):
    """`key=` callable for django-ratelimit."""
    return client_ip(request) or 'unknown'
