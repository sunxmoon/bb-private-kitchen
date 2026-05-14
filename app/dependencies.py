import os
import uuid
from typing import Optional

import aiofiles
from fastapi import Cookie, Depends, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import crud, models, security
from .csrf import csrf_guard, get_csrf_token
from .database import get_db

templates = Jinja2Templates(directory="templates")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SUPPORTED_MSG = "支持的格式: JPG, JPEG, PNG, GIF, WebP"


async def get_current_user(db: Session = Depends(get_db), user_id: Optional[str] = Cookie(None)):
    if not user_id:
        return None
    try:
        verified = security.verify_cookie_value(user_id)
        if verified is None:
            return None
        user = crud.get_user(db, int(verified))
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
    users = crud.get_users(db)
    return {
        "users": users,
        "current_user": current_user,
        "current_user_id": current_user.id if current_user else None,
        "csrf_token": get_csrf_token(request),
    }


async def save_upload_file(file: UploadFile, destination_dir: str) -> str:
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}. {SUPPORTED_MSG}")
    os.makedirs(destination_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(destination_dir, filename)
    async with aiofiles.open(filepath, "wb") as out_file:
        while content := await file.read(1024 * 1024):
            await out_file.write(content)
    return f"/{filepath}"


def delete_old_image(image_url: Optional[str]):
    if image_url and image_url.startswith("/static/uploads/"):
        relative_path = image_url.lstrip("/")
        if os.path.exists(relative_path):
            try:
                os.remove(relative_path)
            except Exception:
                pass
