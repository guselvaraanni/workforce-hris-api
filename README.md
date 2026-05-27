# Enterprise Workforce HRIS API v2.0

A production-oriented **Human Resources Information System (HRIS)** built with Django and Django REST Framework. It combines a secure REST API, server-rendered enterprise UI, role-based dashboards, real-time attendance tracking, leave workflows, audit logging, and CSV bulk import.

**Stack:** Python 3.11 · Django 4.2 · DRF 3.15 · MySQL 8.0 · pytest · Docker

---

## Table of Contents

- [Project Overview](#project-overview)
- [Features](#features)
- [UI Screens](#ui-screens)
- [Architecture & Workflow](#architecture--workflow)
- [Installation & Setup](#installation--setup)
- [API Flow](#api-flow)
- [Background Processing (Bulk CSV)](#background-processing-bulk-csv)
- [Running Tests](#running-tests)
- [Technologies Used](#technologies-used)
- [Key Design Decisions](#key-design-decisions)
- [Future Improvements](#future-improvements)
- [Interview Talking Points](#interview-talking-points)

---

## Project Overview

**Nexus HRMS (Workforce OS)** helps organizations manage employees end to end:

- **HR administrators** onboard staff, run bulk imports, review audit trails, and monitor workforce KPIs.
- **Managers** approve leave, view team attendance, and manage direct reports.
- **Employees** check in/out, request time off, and maintain their profiles.

The system exposes two interfaces that share the same backend:

| Interface | URL examples | Purpose |
|-----------|--------------|---------|
| **HRIS web UI** | `/dashboard/`, `/employees/`, `/profile/` | Day-to-day HR operations (recommended for users) |
| **REST API** | `/api/v1/...` | Integrations, mobile apps, automation (JSON) |
| **API docs** | `/api/v1/docs/` | Swagger/OpenAPI for developers |

> **Note:** Normal navigation always uses the **web UI**. API routes return JSON only (no Django REST Framework browsable pages in the browser by default).

---

## Features

| Area | Capability |
|------|------------|
| **Authentication** | Session login for UI; JWT for API (`/api/v1/auth/login/`) |
| **Role-based access** | HR Admin, Manager, Employee with permission classes |
| **Employee directory** | Search, filter by department/status, pagination |
| **Departments** | Organization structure, headcount, budget |
| **Leave management** | Request, approve/reject, pending queue |
| **Attendance** | Check-in/out, daily hours, weekly strip, 30-day rate |
| **Bulk CSV import** | Background processing with progress and error logs |
| **Audit log** | Field-level change tracking with filters |
| **Dashboards** | Dedicated HR, Manager, and Employee views |
| **Themes** | Light/dark mode with persisted preference |

### Demo credentials (after `seed_data`)

| Role | Email | Password |
|------|-------|----------|
| HR Admin | `hr@example.com` | `Hr@Admin123` |
| Manager | `manager@example.com` | `TestPass123!` |
| Employee | `employee2@example.com` | `TestPass123!` |

---

## UI Screens

Screenshots are stored in [`screenshots/`](screenshots/). Below, each image includes a title, caption, and what it demonstrates.

### Authentication

#### Login — landing page

![Nexus HRMS login page](screenshots/Screenshot%202026-05-27%20221336.png)

*Figure 1 — Enterprise login screen with product branding and feature highlights.*

The login page introduces **Nexus HRMS** and highlights role-based access, audit logging, and leave management. Users sign in with email and password; the session is used for all template routes.

#### Login — credentials entry

![Login with email prefilled](screenshots/Screenshot%202026-05-27%20221348.png)

*Figure 2 — Sign-in form with email/password fields and optional “Developer Sandbox” role shortcuts.*

The form posts to `POST /login/` (session authentication). After success, users are redirected to the role-appropriate dashboard.

---

### HR Admin dashboard

#### HR Operations dashboard

![HR Operations dashboard](screenshots/Screenshot%202026-05-27%20221127.png)

*Figure 3 — HR Admin dashboard: workforce KPIs, department headcount chart, and recent audit activity.*

**What it does:** Summarizes active employees, departments, pending leaves, and bulk-upload jobs. Includes department analytics and a compliance-style audit feed. Primary action: **Add Employee**.

**Route:** `/dashboard/` (when logged in as HR Admin)

---

### Manager dashboard

#### Manager Command Center

![Manager Command Center](screenshots/Screenshot%202026-05-27%20221454.png)

*Figure 4 — Manager dashboard with team KPIs, approval queue, and team attendance panels.*

**What it does:** Shows direct-report count, pending approvals, team on leave today, and org-wide pending leaves. Empty states guide managers when no team is assigned.

**Route:** `/dashboard/` (Manager role)

#### Manager — attendance & direct reports

![Manager attendance widget](screenshots/Screenshot%202026-05-27%20221505.png)

*Figure 5 — Manager view with personal attendance (check-in/out) and direct-reports section.*

**What it does:** Lets managers track their own attendance (check-in time, working duration, weekly calendar) while surfacing team management widgets above.

---

### Employee directory

#### Full directory (all employees)

![Employee directory — 167 members](screenshots/Screenshot%202026-05-27%20221201.png)

*Figure 6 — Searchable employee directory with avatars, department, status, and profile links.*

**What it does:** Lists all active employees with search and filters. HR can open any **View Profile** link (routes to `/employees/<uuid>/`, not the raw API).

**Route:** `/employees/`

#### Directory filtered by department

![Employee directory — HR department filter](screenshots/Screenshot%202026-05-27%20221216.png)

*Figure 7 — Directory filtered to the HR department (25 members) using query parameters.*

**What it does:** Demonstrates server-side filtering (`?department=<uuid>&status=`) without a separate API call from the browser for the table itself.

---

### Employee profile

#### Profile overview

![Employee profile page](screenshots/Screenshot%202026-05-27%20221521.png)

*Figure 8 — Employee profile with attendance summary, leave summary, and tabbed history.*

**What it does:** Displays identity, department, manager, employment type, **today’s attendance** (with check-in/out actions for the profile owner), leave counts, and tabs for leave history, contact info, and audit trail.

**Route:** `/employees/<uuid>/` or **View Profile** → `/profile/` (redirects to your profile)

#### Edit profile

![Edit employee profile form](screenshots/Screenshot%202026-05-27%20221539.png)

*Figure 9 — Edit profile form for personal and employment fields, including photo upload.*

**What it does:** Owners edit personal fields; HR edits full employment data. Form submits via server-side `POST` to `/employees/<uuid>/edit/` (not a raw API form).

**Route:** `/employees/<uuid>/edit/`

---

### Departments

#### Organization structure (HR Admin)

![Departments — HR Admin view](screenshots/Screenshot%202026-05-27%20221226.png)

*Figure 10 — Department list with headcount, budget, and active status (HR Administrator).*

**What it does:** Central view of departments, optional heads, member counts, and budgets. Supports departments created manually or via bulk CSV.

**Route:** `/departments/`

#### Organization structure (Manager)

![Departments — Manager view](screenshots/Screenshot%202026-05-27%20221550.png)

*Figure 11 — Same organization data presented in the manager workspace layout.*

**What it does:** Read-only organizational context for managers planning approvals and team structure.

---

### Leave management

#### Leave approval queue (HR)

![Leave approval queue](screenshots/Screenshot%202026-05-27%20221239.png)

*Figure 12 — HR leave queue with approve/reject actions and status badges.*

**What it does:** HR reviews pending, approved, and rejected requests. Actions call `POST /api/v1/leave-requests/{id}/approve_leave/` or `reject_leave/` via the UI, then refresh the table.

**Route:** `/leaves/`

#### Time off — employee/manager request

![Time off request page](screenshots/Screenshot%202026-05-27%20221601.png)

*Figure 13 — Submit leave requests and filter personal leave history.*

**What it does:** Users submit leave with type, dates, and reason. History table updates from the API; empty state shown when no requests exist.

**Route:** `/leaves/`

---

### Bulk import & job tracking

#### CSV bulk upload

![Bulk CSV upload and job history](screenshots/Screenshot%202026-05-27%20221250.png)

*Figure 14 — Drag-and-drop CSV upload with job history, progress bars, and retry/errors.*

**What it does:** HR uploads a CSV (`email`, `first_name`, `last_name`, `employee_id`, `salary`, `department`). Processing runs in a **background thread**; the UI polls job status via `/api/v1/bulk-uploads/{id}/status/`.

**Route:** `/uploads/`

---

### Audit & compliance

#### System audit log (full)

![System audit log — 118 records](screenshots/Screenshot%202026-05-27%20221302.png)

*Figure 15 — Filterable audit log with action badges, resource types, and JSON change diffs.*

**What it does:** Records create/update/approve events with user, IP, timestamp, and field-level changes. Essential for compliance and debugging data imports.

**Route:** `/audit/`

#### Audit log — filtered by leave requests

![Audit log filtered to LeaveRequest](screenshots/Screenshot%202026-05-27%20221318.png)

*Figure 16 — Audit log filtered to LeaveRequest actions showing approve/update diffs.*

**What it does:** Demonstrates filtering by resource type and viewing structured change payloads (e.g. `status: pending → approved`).

---

### Screenshot index (quick reference)

| File | Section in README | Screen |
|------|-------------------|--------|
| `Screenshot 2026-05-27 221336.png` | [Authentication](#authentication) | Login landing |
| `Screenshot 2026-05-27 221348.png` | [Authentication](#authentication) | Login with credentials |
| `Screenshot 2026-05-27 221127.png` | [HR Admin dashboard](#hr-admin-dashboard) | HR Operations |
| `Screenshot 2026-05-27 221454.png` | [Manager dashboard](#manager-dashboard) | Manager Command Center |
| `Screenshot 2026-05-27 221505.png` | [Manager dashboard](#manager-dashboard) | Manager attendance |
| `Screenshot 2026-05-27 221201.png` | [Employee directory](#employee-directory) | Full directory |
| `Screenshot 2026-05-27 221216.png` | [Employee directory](#employee-directory) | HR dept filter |
| `Screenshot 2026-05-27 221521.png` | [Employee profile](#employee-profile) | Profile overview |
| `Screenshot 2026-05-27 221539.png` | [Employee profile](#employee-profile) | Edit profile |
| `Screenshot 2026-05-27 221226.png` | [Departments](#departments) | Departments (HR) |
| `Screenshot 2026-05-27 221550.png` | [Departments](#departments) | Departments (Manager) |
| `Screenshot 2026-05-27 221239.png` | [Leave management](#leave-management) | Approval queue |
| `Screenshot 2026-05-27 221601.png` | [Leave management](#leave-management) | Time off request |
| `Screenshot 2026-05-27 221250.png` | [Bulk import](#bulk-import--job-tracking) | CSV upload |
| `Screenshot 2026-05-27 221302.png` | [Audit & compliance](#audit--compliance) | Full audit log |
| `Screenshot 2026-05-27 221318.png` | [Audit & compliance](#audit--compliance) | Filtered audit log |

---

## Architecture & Workflow

### High-level request flow

```text
Browser (HRIS UI)  →  Django templates + session auth  →  MySQL
                   ↘  fetch() to /api/v1/... (JSON)     ↗

API clients        →  JWT / session  →  DRF ViewSets  →  MySQL
```

### Application structure

```text
config/
  settings.py       — MySQL, JWT, REST framework, middleware
  urls.py           — UI routes (hris-*) + API namespace (api:*)

employees/
  models.py         — User, Department, EmployeeProfile, LeaveRequest,
                      AttendanceRecord, AuditLog, BulkUploadJob
  views.py          — DRF ViewSets + attendance actions
  template_views.py — Dashboard, directory, profile, audit, uploads
  dashboard_context.py — Role-based dashboard data
  utils/
    attendance_service.py — Check-in/out rules
    csv_processor.py      — Background CSV ingestion

templates/
  base.html + partials/   — Sidebar, topbar, profile menu
  partials/dashboard/     — HR / Manager / Employee dashboards
  employee_detail.html    — Full profile page

static/
  css/hris.css      — Design tokens, light/dark theme
  js/hris.js        — Theme, sidebar, attendance, quick leave
```

### Role-based UI routing

| Role | Dashboard | Primary actions |
|------|-----------|-----------------|
| HR Admin | HR Operations KPIs | Add employee, bulk upload, audit |
| Manager | Command Center | Approve leave, team attendance |
| Employee | Personal overview | Attendance, leave request, profile |

---

## Installation & Setup

### Quick Start (Docker — recommended)

```bash
cd workforce-hris-api

# Start MySQL + Django + Nginx
docker compose up --build

# Migrations and sample data (separate terminal)
docker compose exec api python manage.py migrate
docker compose exec api python manage.py seed_data

# Open in browser
# UI:      http://localhost:8000/dashboard/
# API docs: http://localhost:8000/api/v1/docs/
# Admin:   http://localhost:8000/admin/
```

### Local development (without Docker)

**Prerequisites:** Python 3.11+, MySQL 8.0, `libmysqlclient-dev` (Linux) or MySQL client libraries (Windows/macOS).

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Configure .env (DB_HOST, DB_USER, DB_PASSWORD, etc.)
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

Visit `http://127.0.0.1:8000/` for login, then `http://127.0.0.1:8000/dashboard/`.

---

## API Flow

### UI → API mapping (common actions)

| User action (UI) | HTTP | Endpoint |
|------------------|------|----------|
| Sign in | POST | `/login/` (session) |
| Check in | POST | `/api/v1/attendance/check_in/` |
| Check out | POST | `/api/v1/attendance/check_out/` |
| Submit leave (quick form) | POST | `/api/v1/leave-requests/` |
| Approve leave | POST | `/api/v1/leave-requests/{id}/approve_leave/` |
| Upload CSV | POST | `/api/v1/bulk-uploads/` |
| Poll upload status | GET | `/api/v1/bulk-uploads/{id}/status/` |

Profile and directory pages are rendered server-side; they do **not** open browsable API pages in the browser.

### REST endpoints (summary)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/login/` | JWT token pair | Public |
| POST | `/api/v1/auth/register/` | Register user | Public |
| GET/POST | `/api/v1/employees/` | List/create employees | Auth |
| GET/PATCH/DELETE | `/api/v1/employees/{id}/` | Employee CRUD | Auth |
| GET/POST | `/api/v1/leave-requests/` | Leave CRUD | Auth |
| POST | `/api/v1/leave-requests/{id}/approve_leave/` | Approve | Manager/HR |
| POST | `/api/v1/leave-requests/{id}/reject_leave/` | Reject | Manager/HR |
| POST | `/api/v1/attendance/check_in/` | Check in today | Auth |
| POST | `/api/v1/attendance/check_out/` | Check out today | Auth |
| GET | `/api/v1/attendance/today/` | Today’s summary | Auth |
| GET/POST | `/api/v1/bulk-uploads/` | CSV jobs | HR Admin |
| GET | `/api/v1/audit-logs/` | Audit trail | HR Admin |
| GET | `/api/v1/analytics/` | Workforce stats | HR Admin |
| GET | `/api/v1/health/` | Health check | Public |
| GET | `/api/v1/docs/` | Swagger UI | Public |

Full interactive documentation: **`/api/v1/docs/`**

### Employee list query parameters

```http
GET /api/v1/employees/?search=john&status=active&department=<uuid>&ordering=-salary&page=2
```

### Template UI routes (use these in the browser)

| URL | Page |
|-----|------|
| `/` | Login |
| `/dashboard/` | Role-based dashboard |
| `/profile/` | Redirect to your profile |
| `/employees/` | Employee directory |
| `/employees/<id>/` | Employee profile |
| `/employees/<id>/edit/` | Edit profile |
| `/employees/add/` | Add employee (HR) |
| `/departments/` | Departments |
| `/leaves/` | Leave requests |
| `/uploads/` | Bulk CSV |
| `/audit/` | Audit log (HR) |

---

## Background Processing (Bulk CSV)

This project does **not** use Celery or Redis for CSV import. Instead:

1. HR uploads a file on `/uploads/`.
2. API creates a `BulkUploadJob` row.
3. A **background `threading.Thread`** processes rows after `transaction.on_commit()`.
4. UI polls job status and shows success/failure counts.

```text
Upload → API → DB (job row) → Thread → bulk_create employees → Audit logs
```

For very large deployments, `process_csv_file` in `employees/utils/csv_processor.py` can be wrapped in a Celery task with minimal changes.

---

## Running Tests

```bash
# All tests
pytest tests/ -v --no-cov

# With coverage
pytest tests/ --cov=employees --cov-report=html

# Navigation + attendance suites
pytest tests/test_navigation.py tests/test_attendance.py -v
```

Tests cover attendance check-in/out, URL routing (UI vs API), profile HTML responses, and core HR workflows.

---

## Technologies Used

| Layer | Technology |
|-------|------------|
| Backend | Django 4.2, Django REST Framework 3.15 |
| Auth | Session (UI), SimpleJWT (API) |
| Database | MySQL 8.0 |
| API docs | drf-spectacular (OpenAPI/Swagger) |
| Filtering | django-filter |
| Testing | pytest, factory_boy |
| Frontend (UI) | Django templates, vanilla JS, CSS design tokens |
| DevOps | Docker Compose, Nginx (optional) |
| Background jobs | `threading` (CSV); not Celery |

---

## Key Design Decisions

### Why `threading.Thread` instead of Celery?

Keeps the project self-contained without Redis. `process_csv_file` is already isolated and can become a `@shared_task` later.

### Why `select_for_update()` on leave approval?

Prevents two managers from approving the same pending leave concurrently under MySQL row locking.

### Why `transaction.on_commit()` for CSV threads?

Ensures the upload job row is visible to the worker thread before processing starts.

### Why separate `hris-*` URL names from the API?

Django’s `reverse('employee-detail')` previously resolved to `/api/v1/employees/.../`, which sent users to the DRF browsable API. UI routes now use names like `hris-employee-detail`; API routes use the `api:` namespace.

### Why JSON-only API renderers?

Browsers no longer receive HTML API debug pages during normal use. Set `ENABLE_DRF_BROWSABLE_API=true` only when debugging APIs locally.

---

## Future Improvements

- [ ] Celery + Redis for CSV and scheduled reports
- [ ] Email notifications for leave approvals
- [ ] Holiday calendar and announcements backend
- [ ] Manager assignment UI in admin workflow
- [ ] OpenAPI examples on all ViewSet actions
- [ ] E2E tests (Playwright) for full UI flows
- [ ] Fix known backend items in `PROJECT_ANALYSIS.md` (registration hardening, leave overlap validation)

---

## Interview Talking Points

**On the threading model:**

> “CSV import runs in a background thread started with `transaction.on_commit()` so the job row is committed before the worker reads it—avoiding a classic race under MySQL REPEATABLE READ.”

**On query optimization:**

> “Employee lists use `select_related('user', 'department', 'manager')` and department headcounts use `annotate(Count(...))` at the database layer.”

**On audit trails:**

> “We combine explicit `log_action()` in ViewSets with `pre_save`/`post_save` signals for field-level diffs, including bulk CSV imports.”

**On concurrency:**

> “Leave approvals use `select_for_update()` inside `atomic()` so only one approver wins per request.”

**On UX/API separation:**

> “UI routes are namespaced (`hris-*`) and middleware redirects accidental browser visits to `/api/v1/employees/<id>/` to the profile template—users never land on raw DRF pages.”

---

## Additional documentation

- [`PROJECT_ANALYSIS.md`](PROJECT_ANALYSIS.md) — Architecture audit, API inventory, known issues
- [`notes.txt`](notes.txt) — Maintainer handbook (update with every change)

---

*Built for enterprise workforce management — API-first backend with a polished, role-aware HRIS frontend.*
