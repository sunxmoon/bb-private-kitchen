import os
import uuid
from typing import Optional

import aiofiles
from fastapi import Cookie, Depends, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, security
from .csrf import csrf_guard, get_csrf_token
from .database import get_db

templates = Jinja2Templates(directory="templates")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
SUPPORTED_MSG = "支持的格式: JPG, JPEG, PNG, GIF, WebP"
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


async def get_current_user(db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return None
    try:
        verified = security.verify_cookie_value(user_id)
        if verified is None:
            return None

        if ":" in verified:
            uid_str, token_version_str = verified.split(":", 1)
            uid = int(uid_str)
            token_version = int(token_version_str)
        else:
            uid = int(verified)
            token_version = None

        user = crud.get_user(db, uid)

        if user and token_version is not None:
            if user.token_version != token_version:
                return None

        return user
    except (ValueError, TypeError):
        return None


async def login_required(request: Request, user: Optional[models.User] = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=303, detail="Not logged in", headers={"Location": "/login"})
    await csrf_guard(request)
    return user


async def require_admin(user: models.User = Depends(login_required)):
    if user.role != "admin":
        raise HTTPException(status_code=303, detail="Forbidden", headers={"Location": "/"})
    return user


def get_common_context(request: Request, db: Session, current_user: Optional[models.User] = None):
    from urllib.parse import unquote

    users = crud.get_users(db)
    context = {
        "users": users,
        "current_user": current_user,
        "current_user_id": current_user.id if current_user else None,
        "csrf_token": get_csrf_token(request),
    }

    flash_msg = request.cookies.get("flash_msg")
    if flash_msg:
        context["msg"] = unquote(flash_msg)
    elif "msg" in request.query_params:
        context["msg"] = request.query_params["msg"]

    return context


def redirect_with_flash(url: str, msg: str, status_code: int = 303) -> "RedirectResponse":
    from urllib.parse import quote

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(url=url, status_code=status_code)
    response.set_cookie(key="flash_msg", value=quote(msg), max_age=10, httponly=True, samesite="lax")
    return response


async def save_upload_file(file: UploadFile, destination_dir: str) -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}. {SUPPORTED_MSG}")
    if file.content_type and file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}. {SUPPORTED_MSG}")
    os.makedirs(destination_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(destination_dir, filename)
    total_size = 0
    try:
        async with aiofiles.open(filepath, "wb") as out_file:
            while content := await file.read(1024 * 1024):
                total_size += len(content)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE // 1024 // 1024}MB）")
                await out_file.write(content)
    except HTTPException:
        if os.path.exists(filepath):
            os.remove(filepath)
        raise
    return f"/{filepath}"


def delete_old_image(image_url: Optional[str]):
    if image_url and image_url.startswith("/static/uploads/"):
        relative_path = os.path.normpath(image_url.lstrip("/"))
        # Ensure normalized path is still within uploads directory (prevent path traversal)
        if not relative_path.startswith("static/uploads/"):
            return
        if os.path.exists(relative_path):
            try:
                os.remove(relative_path)
            except Exception:
                pass
