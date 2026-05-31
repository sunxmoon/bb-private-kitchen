import threading
import time
from collections import defaultdict

from fastapi import HTTPException, Request

from .config import settings

_WINDOW = 60
_MAX = 5
_lock = threading.Lock()
_attempts: dict[str, list[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, prefering direct connection over proxy headers.

    X-Forwarded-For is only trusted when a single IP is present (indicating
    a known reverse proxy). Multi-value or absent headers fall back to the
    direct TCP connection IP to prevent spoofing.
    """
    forwarded = request.headers.get("X-Forwarded-For", "").strip()
    if forwarded and "," not in forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def login_rate_limit(request: Request):
    if settings.is_testing:
        return
    ip = _get_client_ip(request)
    now = time.time()

    with _lock:
        records = [t for t in _attempts[ip] if now - t < _WINDOW]
        _attempts[ip] = records
        if len(records) >= _MAX:
            wait = int(_WINDOW - (now - records[0]))
            raise HTTPException(status_code=429, detail=f"登录过于频繁，请 {wait} 秒后再试")
        _attempts[ip].append(now)

        if sum(len(v) for v in _attempts.values()) > 1000:
            _purge_stale(now)


def _purge_stale(now: float):
    stale = [
        ip for ip, records in _attempts.items()
        if not [t for t in records if now - t < _WINDOW]
    ]
    for ip in stale:
        del _attempts[ip]
