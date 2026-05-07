# Employee Management System API

A production-ready Django REST API for comprehensive employee management, featuring MySQL integration, advanced concurrency control, and asynchronous processing capabilities.

## Tech Stack
- Django & Django REST Framework
- MySQL
- JWT Authentication
- Python Threading for Async Tasks

## System Architecture & Features
- **Core Database:** MySQL integration with a custom User Model implementing role-based access control (RBAC).
- **RESTful API:** Complete CRUD operations mapped via ViewSets and Generic Views, secured by JSON Web Tokens (JWT).
- **Concurrency Control:** Database-level pessimistic locking (`select_for_update()`) for leave request management to prevent race conditions during concurrent approval attempts.
- **Asynchronous Processing:** Native Python threading for handling large CSV bulk uploads without blocking the main HTTP thread.
- **Audit Logging:** Observer pattern implementation using Django Signals for automatic, read-only data change tracking.
- **Query Optimization:** Mitigation of the N+1 query problem using `select_related` and `prefetch_related` to minimize database hits.
- **Testing & Documentation:** Comprehensive Pytest suite and auto-generated OpenAPI/Swagger documentation.

## Prerequisites
- Python 3.9+
- MySQL 5.7+ or MariaDB 10.5+

## Local Setup & Installation

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Copy the example environment file and configure your database credentials.

```bash
cp .env.example .env
```

Ensure your `.env` contains the correct database configurations:

```text
DB_ENGINE=django.db.backends.mysql
DB_NAME=employee_management_db
DB_USER=root
DB_PASSWORD=your_password_here
DB_HOST=localhost
DB_PORT=3306
SECRET_KEY=your_secure_secret_key
JWT_SECRET_KEY=your_jwt_secret_key
DEBUG=True
```

### 3. Database Initialization
Create the MySQL database:

```sql
CREATE DATABASE employee_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Apply migrations and seed the initial data:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data --employees 50
```

### 4. Run the Server
```bash
python manage.py runserver
```

The API will be available at: `http://localhost:8000/api/v1/`

## API Documentation
Interactive API documentation is available when the server is running:

- Swagger UI: `http://localhost:8000/api/v1/docs/`
- OpenAPI Schema: `http://localhost:8000/api/v1/schema/`

## Authentication & Authorization
The API uses JWT for authentication.

### Get Token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "hr@example.com", "password": "Hr@Admin123"}'
```

### Role-Based Access Control (RBAC):
- **HR Admin:** Full system access, can manage users, approve all leaves, and view system audit logs.
- **Manager:** Can view team profiles and approve/reject subordinate leave requests.
- **Employee:** Can manage their own personal profile and submit leave requests.

## Testing
The project uses pytest for continuous integration testing.

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=employees tests/
```

