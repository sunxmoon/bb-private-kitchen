import os
import time
from collections import defaultdict

from fastapi import HTTPException, Request

_WINDOW = 60
_MAX = 5
_attempts: dict[str, list[float]] = defaultdict(list)


async def login_rate_limit(request: Request):
    if os.getenv("TESTING") == "1":
        return
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not ip:
        ip = request.client.host if request.client else "unknown"
    now = time.time()
    records = [t for t in _attempts[ip] if now - t < _WINDOW]
    _attempts[ip] = records
    if len(records) >= _MAX:
        wait = int(_WINDOW - (now - records[0]))
        raise HTTPException(status_code=429, detail=f"登录过于频繁，请 {wait} 秒后再试")
    _attempts[ip].append(now)
    # Periodic cleanup: remove stale IPs every 100 requests
    if sum(len(v) for v in _attempts.values()) > 1000:
        _purge_stale(now)


def _purge_stale(now: float):
    stale = [ip for ip, records in _attempts.items() if not [t for t in records if now - t < _WINDOW]]
    for ip in stale:
        del _attempts[ip]
