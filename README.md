# Enterprise Workforce HRIS API v2.0

A production-oriented Django REST Framework project for workforce management.

**Stack**: Python 3.11 · Django 4.2 · DRF 3.15 · MySQL 8.0 · pytest · Docker

---

## Quick Start (Docker — recommended)

```bash
# 1. Clone / unzip the project
cd workforce-hris-api

# 2. Start all services (MySQL + Django + Nginx)
docker compose up --build

# 3. In a separate terminal — run migrations and seed data
docker compose exec api python manage.py migrate
docker compose exec api python manage.py seed_data

# 4. Access the application
open http://localhost:8000         # API-driven SPA frontend
open http://localhost:8000/dashboard/   # Server-side template UI
open http://localhost:8000/api/v1/docs/ # Swagger API documentation
open http://localhost:8000/admin/       # Django Admin
```

---

## Local Development (without Docker)

### Prerequisites
- Python 3.11+
- MySQL 8.0 running locally
- `libmysqlclient-dev` (Ubuntu) or `mysql-connector-c` (macOS)

### Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env .env.local
# Edit .env.local — set DB_HOST=localhost, DB_USER, DB_PASSWORD

# 4. Create MySQL database
mysql -u root -p
  CREATE DATABASE employee_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER 'hris_user'@'localhost' IDENTIFIED BY 'hris_password';
  GRANT ALL PRIVILEGES ON employee_management_db.* TO 'hris_user'@'localhost';
  FLUSH PRIVILEGES;

# 5. Run migrations
python manage.py migrate

# 6. Seed sample data
python manage.py seed_data

# 7. Run development server
python manage.py runserver
```

---

## Running Tests

```bash
# Run all tests with coverage report
pytest tests/ -v

# Run specific test class
pytest tests/test_complete.py::TestCSVIngestion -v

# Skip slow/concurrency tests
pytest tests/ -m "not concurrency" -v

# Parallel execution (faster)
pytest tests/ -n auto -v

# Coverage report only
pytest tests/ --cov=employees --cov-report=html
open htmlcov/index.html
```

---

## API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/auth/login/` | Get JWT token | Public |
| POST | `/api/v1/auth/register/` | Create account | Public |
| POST | `/api/v1/auth/refresh/` | Refresh JWT | Public |
| GET/POST | `/api/v1/departments/` | List/create departments | Auth |
| GET/PATCH/DELETE | `/api/v1/departments/{id}/` | Department detail | Auth |
| GET/POST | `/api/v1/employees/` | List/create employees | Auth |
| GET/PATCH/DELETE | `/api/v1/employees/{id}/` | Employee detail | Auth |
| GET | `/api/v1/employees/by_department/` | Employees by dept | HR Admin |
| GET | `/api/v1/employees/my_team/` | Manager's team | Manager |
| GET/POST | `/api/v1/leave-requests/` | List/create leaves | Auth |
| POST | `/api/v1/leave-requests/{id}/approve_leave/` | Approve leave | Manager/HR |
| POST | `/api/v1/leave-requests/{id}/reject_leave/` | Reject leave | Manager/HR |
| GET | `/api/v1/leave-requests/my_requests/` | Own leaves | Auth |
| GET | `/api/v1/leave-requests/pending_approvals/` | Pending for approval | Manager/HR |
| GET | `/api/v1/audit-logs/` | Audit trail | HR Admin |
| GET | `/api/v1/audit-logs/employee_history/` | Per-employee audit | HR Admin |
| GET/POST | `/api/v1/bulk-uploads/` | Upload CSV | HR Admin |
| GET | `/api/v1/bulk-uploads/{id}/status/` | Job status | HR Admin |
| POST | `/api/v1/bulk-uploads/{id}/retry/` | Retry failed job | HR Admin |
| GET | `/api/v1/analytics/` | Workforce stats | HR Admin |
| GET | `/api/v1/health/` | Health check | Public |
| GET | `/api/v1/docs/` | Swagger UI | Public |

### Query Parameters (Employee list)
```
?search=john              # Search name, email, employee_id
?status=active            # employment_status filter
?department=<uuid>        # department filter
?salary_min=50000         # salary >= value
?salary_max=100000        # salary <= value
?joined_after=2024-01-01  # date_of_joining filter
?ordering=-salary         # Sort by field (- for desc)
?page=2                   # Pagination
```

---

## Template UI Pages

| URL | Page | Description |
|-----|------|-------------|
| `/dashboard/` | Dashboard | Stats, dept breakdown, audit feed |
| `/employees/` | Employee List | Searchable/filterable/paginated table |
| `/employees/<id>/` | Employee Detail | Profile, leave history, audit trail |
| `/employees/add/` | Add Employee | Create employee form |
| `/departments/` | Departments | Dept list with headcounts |
| `/leaves/` | Leave Requests | Filterable leave table |
| `/uploads/` | Bulk Uploads | CSV drag-drop + job tracking |
| `/audit/` | Audit Log | Full audit trail with filters |

---

## Architecture

```
config/
  settings.py      — All Django settings (MySQL, JWT, filters, security)
  urls.py          — Root routing (API + template views)
  wsgi.py          — WSGI entry point

employees/
  models.py        — 6 models: CustomUser, Department, EmployeeProfile,
                     LeaveRequest, AuditLog, BulkUploadJob
  views.py         — DRF ViewSets + WorkforceAnalyticsView + HealthCheck
  template_views.py— Django CBVs for server-side rendered pages
  serializers.py   — DRF serializers with validation
  permissions.py   — 7 custom permission classes
  filters.py       — django-filter FilterSets (NEW)
  signals.py       — pre_save/post_save for field-level audit (FIXED)
  urls.py          — DRF router + custom URL patterns
  admin.py         — Django admin registration
  utils/
    audit.py       — log_action() helper
    csv_processor.py — Background CSV ingestion (FIXED + IMPROVED)
  migrations/      — Database schema migrations

templates/
  base.html        — Master layout with sidebar + topbar
  dashboard.html   — Stats and activity feed
  employees.html   — Employee list with filters
  employee_detail.html — Tabbed profile page
  employee_form.html   — Add employee form
  departments.html — Department list
  leaves.html      — Leave requests
  uploads.html     — CSV upload + job tracking
  audit.html       — Audit log

tests/
  factories.py     — factory_boy model factories
  test_complete.py — 35+ tests covering all features

docker/
  mysql/my.cnf     — MySQL charset + InnoDB config
  mysql/init.sql   — Database initialization
  nginx/nginx.conf — Nginx main config
  nginx/default.conf — Virtual host + proxy config
```

---

## Key Design Decisions

### Why `threading.Thread` instead of Celery?
The threading approach is simpler for a self-contained project and works without Redis. In production, replace with Celery: the `process_csv_file` function is already extracted and can be wrapped in a `@shared_task` with one line change.

### Why `select_for_update()` on leave approval?
Pessimistic locking prevents two managers from simultaneously approving the same leave. Without it, both threads could read `status='pending'`, both validate OK, and both write `status='approved'` — a classic lost update problem.

### Why `transaction.on_commit()` for thread start?
Django's `transaction.atomic()` wraps `perform_create()`. If we start the thread inside the transaction, the thread may read the DB before the transaction commits. `on_commit()` delays thread start until after commit, guaranteeing row visibility.

### Why `pre_save` + `post_save` for signals?
`post_save` cannot see what changed — by the time it runs, the DB already has the new values. `pre_save` fires before the write, allowing us to snapshot the current (soon to be "old") values in thread-local storage.

---

## Interview Talking Points

**On the threading model**:
> "I use `threading.Thread` for background CSV processing. The key correctness issue is that the thread must only start after the `BulkUploadJob` row is committed to MySQL. I use `transaction.on_commit()` to guarantee this — without it, the thread could get a 'row not found' error under MySQL's REPEATABLE READ isolation."

**On query optimization**:
> "I apply `select_related('user', 'department', 'manager')` on the EmployeeProfile queryset to prevent N+1 queries on list endpoints. For department headcounts, I use `annotate(count=Count('employees'))` at the DB level rather than calling `.count()` per department in Python. All filtering is done via `django-filter` FilterSets, which push the WHERE clause to the DB."

**On audit trails**:
> "I have two audit layers. First, explicit `log_action()` calls in each ViewSet's `perform_create/update/destroy` methods — these capture the API request user and IP. Second, `pre_save`/`post_save` signals using thread-local snapshots to detect field-level changes that might happen outside the API (e.g., Django admin, management commands). CSV imports write audit entries via `bulk_create` after employee creation."

**On concurrency**:
> "Leave approvals use `select_for_update()` inside `transaction.atomic()`. MySQL acquires a row-level lock, so only one thread can approve a given leave at a time. The second concurrent request reads the now-updated status and returns a 400 error."
