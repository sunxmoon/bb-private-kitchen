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

## Completion Promise
The Household Self-Service Ordering Web App is fully implemented, debugged, and optimized.
- Mobile-first web interface using Tailwind CSS and HTMX.
- FastAPI backend with PostgreSQL (SQLAlchemy) and indexing for performance.
- Audit logging for all major actions.
- Image upload support for dishes with automatic storage cleanup.
- Robust user management using cookies and dynamic DB lookups.
- Full User Management CRUD and Password-protected Login system.

## Next Steps for User
1. Ensure PostgreSQL is running and create a database named `ordering_db`.
2. Update `.env` with correct database credentials (DATABASE_URL).
3. Run `python seed_db.py` to initialize data (this will also update passwords to "666").
4. Run `./run.sh` to start the application.
5. Use "666" as the default password for all initial users.

## Mistakes & Learnings
- **Authentication Flow**: Moved from simple cookie-based user switching to a full login/logout flow for better security and audit integrity.
- **User Management**: Added a dedicated management page for household members to manage the user list.
- **Database Schema**: Manually updated models to include passwords. (Note: Existing databases may need manual column addition: `ALTER TABLE users ADD COLUMN password VARCHAR(255) DEFAULT '666' NOT NULL;`)


