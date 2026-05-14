# Technical Stack: 宝宝的私房菜馆

## 1. Backend
- **Language**: Python 3.10+
- **Framework**: **FastAPI**
    - *Reasoning*: High performance, modern, excellent for rapid API development, built-in validation (Pydantic), and async support.
- **ORM**: **SQLAlchemy 2.0** with **alembic** for migrations.
- **Logging/Audit**: Custom middleware or signals to record changes to the `audit_logs` table.

## 2. Database
- **Primary DB**: **PostgreSQL**
    - *Reasoning*: Robust relational database as requested. Supports JSONB for flexible order details if needed.

## 3. Frontend
- **Architecture**: **HTMX + Tailwind CSS**
    - *Reasoning*: Extremely lightweight. Allows for "Single Page Application" feel without the complexity of a thick JS framework (React/Vue). Perfect for a mobile web app where simplicity is key.
- **Templating**: **Jinja2** (integrated with FastAPI).
- **UI Components**: Simple Tailwind-based mobile layout mirroring `app.jpg`.

## 4. Image Upload & Storage
- **Storage**: Local filesystem storage (e.g., `static/uploads/`).
- **Processing**: `Pillow` for basic image resizing/optimization.
- **Database Reference**: Store relative paths in the PostgreSQL table.

## 5. Security & Authentication
- **Simplicity**: Simple user selection (Family members) or basic password if needed. For a "household" use case, a simple "Who are you?" selector might suffice, backed by a session cookie.

## 6. Project Structure
```text
/
├── app/
│   ├── main.py          # FastAPI app entry
│   ├── models.py        # SQLAlchemy models
│   ├── schemas.py       # Pydantic models
│   ├── crud.py          # Database operations
│   ├── database.py      # DB connection
│   └── routers/         # API routes
├── templates/           # Jinja2 templates
├── static/              # CSS, JS, Uploaded Images
├── alembic/             # Migrations
└── .loki/               # Loki system files
```
