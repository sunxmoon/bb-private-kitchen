"""
Cleanup orphaned image files in static/uploads/
that are no longer referenced by any dish in the database.

Usage:
    uv run python cleanup_images.py          # dry-run (show what would be deleted)
    uv run python cleanup_images.py --force  # actually delete
"""
import os
import sys

from app import models
from app.database import SessionLocal

UPLOAD_DIRS = ["static/uploads"]


def get_referenced_images(db) -> set:
    refs = set()
    for dish in db.query(models.Dish).all():
        if dish.image_url:
            refs.add(dish.image_url)
    return refs


def main():
    force = "--force" in sys.argv
    db = SessionLocal()
    try:
        referenced = get_referenced_images(db)
    finally:
        db.close()

    total_freed = 0
    for dir_path in UPLOAD_DIRS:
        if not os.path.isdir(dir_path):
            continue
        for fname in os.listdir(dir_path):
            if fname == ".gitkeep":
                continue
            full_path = os.path.join(dir_path, fname)
            if not os.path.isfile(full_path):
                continue
            url = f"/{dir_path}/{fname}"
            if url not in referenced:
                size = os.path.getsize(full_path)
                total_freed += size
                if force:
                    os.remove(full_path)
                    print(f"  deleted  {url}  ({_fmt_size(size)})")
                else:
                    print(f"  would delete  {url}  ({_fmt_size(size)})")

    if total_freed == 0:
        print("No orphaned images found.")
    elif force:
        print(f"\nFreed {_fmt_size(total_freed)} total.")
    else:
        print(f"\nWould free {_fmt_size(total_freed)}. Run with --force to delete.")


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


if __name__ == "__main__":
    main()