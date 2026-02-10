# Continuity: 宝宝的私房菜馆

## Current Status
- Phase: Discovery
- Objective: Define requirements and technical architecture for the lightweight ordering system.

## Working Memory
- Requirements: Mobile web interface, self-service ordering, dish management (create/edit/save), order summary with specific fields (taste, time, location, ingredients, remarks), audit logging, PostgreSQL backend.
- UI Reference: `app.jpg` exists in the root directory.
- Technology Constraint: Python 3, Lightweight, PostgreSQL.

## Tasks
- [x] Activate Loki Mode
- [x] Create PRD (`.loki/specs/PRD.md`)
- [x] Create Tech Stack (`.loki/specs/TECH_STACK.md`)
- [x] Design Database Schema (`.loki/specs/schema.sql`)
- [x] Initialize Python Environment and Dependencies
- [x] Setup FastAPI scaffolding
- [x] Implement Database connection and models
- [x] Implement CRUD and API endpoints
- [x] Implement Frontend with HTMX/Tailwind
- [x] Seed database and provide run script
- [x] Fix: Dynamic user display in header (replaced hardcoded names with DB fetch + cookies)
- [x] Optimization: Database indexing for foreign keys
- [x] Optimization: Image file cleanup on dish update
- [x] Optimization: Improved redirect workflow (add-item now goes to my-orders)
- [x] Feature: User Management Module (CRUD for users)
- [x] Feature: Authentication system (Login/Logout) with default password "666"
- [x] Feature: Switch User button and refined navigation
- [x] Optimization: Code audit, security hardening, and V2 compatibility
- [x] Testing: Implemented unit tests for Auth and CRUD
- [x] Bug Fix: Fixed logout cookie deletion bug
- [x] Bug Fix: Fixed DB connection error during import/testing

## Feature Implementation Checklist (Phase 2)
- [x] **Task 1: UI 美学升级** - 卡片式布局增强、质感提升、响应式优化
- [x] **Task 2: 常用配置一键填入** - 自动记忆上次点餐偏好，减少重复输入
- [x] **Task 3: “今天吃什么”随机翻牌** - 趣味解决选择困难症

## Feature Implementation Checklist (Phase 3: P2 精致打磨)
- [x] **Task 4: 滚动动态背景** - 背景图随滚动深度动态调整模糊与透明度，增强呼吸感
- [x] **Task 5: 移动端滑动手势** - 订单管理页支持滑动手势删除或完成，提升交互效率
- [x] **Task 6: 实时交互反馈** - 增加简单的通知机制或状态轮询，增强家庭互动感

## Completion Promise
The Household Self-Service Ordering Web App is fully implemented, debugged, and optimized.
- Mobile-first web interface using Tailwind CSS and HTMX.
- FastAPI backend with PostgreSQL (SQLAlchemy) and indexing for performance.
- Audit logging for all major actions.
- Image upload support for dishes with automatic storage cleanup.
- Robust user management using cookies and dynamic DB lookups.
- Full User Management CRUD and Password-protected Login system.
- Secure password hashing using bcrypt.
- Comprehensive test suite ensuring core stability.
- **Enhanced UI/UX**: Card-based library, glassmorphism, and responsive design.
- **Smart Features**: One-click fill from history and random picker for meal planning.

## Next Steps for User
1. Ensure PostgreSQL is running and create a database named `ordering_db`.
2. Update `.env` with correct database credentials (DATABASE_URL).
3. Run `python seed_db.py` to initialize data (this will also update passwords to "666" with secure hashing).
4. Run `./run.sh` to start the application.
5. To run tests: `TESTING=1 PYTHONPATH=. pytest tests/`

## Mistakes & Learnings
- **FastAPI Responses**: Remembered that `RedirectResponse` is a separate object; setting cookies on the background `Response` parameter doesn't affect the returned `RedirectResponse`.
- **Database Initialization**: Moving `metadata.create_all` to a startup event prevents connection errors during testing or imports when the DB is unavailable.
- **Dependency Management**: Standardized on Pydantic V2 and direct `bcrypt` usage for better compatibility with Python 3.12.



