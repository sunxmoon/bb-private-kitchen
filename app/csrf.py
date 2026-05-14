import hmac
import os
from secrets import token_urlsafe

from fastapi import HTTPException, Request

CSRF_SECRET = os.getenv("CSRF_SECRET", token_urlsafe(32))
CSRF_COOKIE_NAME = "csrf_token"
CSRF_FORM_NAME = "csrf_token"


def generate_csrf_token() -> str:
    return token_urlsafe(32)


def get_csrf_token(request: Request) -> str:
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = getattr(request.state, CSRF_COOKIE_NAME, None)
    if not token:
        token = generate_csrf_token()
    return token


async def csrf_guard(request: Request):
    if request.method not in ("POST", "PUT", "DELETE"):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token:
        raise HTTPException(status_code=403, detail="CSRF cookie not found")
    content_type = request.headers.get("content-type", "")
    form_token = None
    if "form" in content_type or "multipart" in content_type:
        form = await request.form()
        form_token = form.get(CSRF_FORM_NAME)
    if not form_token:
        form_token = request.headers.get("X-CSRF-Token")
    if not form_token or not hmac.compare_digest(form_token, cookie_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
