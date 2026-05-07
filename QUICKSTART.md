# Quick Start Guide - Employee Management System

## 5-Minute Setup

### Step 1: Environment Setup (1 minute)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Database Configuration (2 minutes)

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your MySQL credentials:
# DB_NAME=employee_management_db
# DB_USER=root
# DB_PASSWORD=your_password_here
# DB_HOST=localhost
# DB_PORT=3306
```

Create MySQL database:
```bash
mysql -u root -p
CREATE DATABASE employee_management_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### Step 3: Initialize Database (1 minute)

```bash
# Run migrations
python manage.py migrate

# Seed sample data
python manage.py seed_data --employees 50
```

### Step 4: Start Server (1 minute)

```bash
python manage.py runserver
```

✅ **You're Done!** API is running at `http://localhost:8000/api/v1/`

## 🔑 Default Credentials

After seeding, you can login with:
- **Email**: `hr@example.com`
- **Password**: `Hr@Admin123`

## 🚀 First API Call

### 1. Get Authentication Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "hr@example.com",
    "password": "Hr@Admin123"
  }'
```

Save the `access` token from response.

### 2. List All Employees

```bash
curl http://localhost:8000/api/v1/employees/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 3. View API Documentation

Open browser: `http://localhost:8000/api/v1/docs/`

## 📚 Common Tasks

### Create a New Department

```bash
curl -X POST http://localhost:8000/api/v1/departments/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "DevOps",
    "description": "Infrastructure and DevOps team",
    "budget": 250000,
    "is_active": true
  }'
```

### Create New Employee

```bash
curl -X POST http://localhost:8000/api/v1/employees/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecurePass123!",
    "first_name": "John",
    "last_name": "Doe",
    "employee_id": "EMP999",
    "department": "uuid-of-department",
    "salary": 55000,
    "employment_type": "full_time"
  }'
```

### Submit Leave Request

```bash
curl -X POST http://localhost:8000/api/v1/leave-requests/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-06-01",
    "end_date": "2024-06-05",
    "leave_type": "annual",
    "reason": "Summer vacation"
  }'
```

### Approve Leave Request

```bash
curl -X POST http://localhost:8000/api/v1/leave-requests/{REQUEST_ID}/approve_leave/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "approval_notes": "Approved"
  }'
```

### Upload Bulk Employees

```bash
curl -X POST http://localhost:8000/api/v1/bulk-uploads/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "csv_file=@csv_data/sample_employees.csv"
```

## 🎯 Test the Concurrency Control

The system prevents race conditions in leave approvals:

```python
# In Python shell (python manage.py shell)
from employees.models import LeaveRequest
from django.db import transaction

# Two concurrent approval attempts will be safe
# Only one will succeed, preventing data corruption
```

## 📊 Monitor Performance

Access Django Debug Toolbar at `/admin/` to see:
- SQL queries executed
- Execution time per query
- Total requests/responses

## 🔍 View Audit Logs

```bash
curl http://localhost:8000/api/v1/audit-logs/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 📱 Admin Panel

Navigate to `http://localhost:8000/admin/`
- Login with `hr_admin` / `Hr@Admin123`
- Manage users, departments, employees
- View audit logs
- Monitor bulk uploads

## 🧪 Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=employees

# Run specific test file
pytest tests/test_api.py
```

## 🆘 Common Issues

**Issue**: "Can't connect to MySQL"
```bash
# Check MySQL is running
sudo service mysql start  # Linux
brew services start mysql-community  # macOS
```

**Issue**: "Permission Denied"
- Verify your token is correct
- Check user has required role
- Ensure Authorization header is set

**Issue**: "Database doesn't exist"
```bash
# Create database
mysql -u root -p
CREATE DATABASE employee_management_db CHARACTER SET utf8mb4;
```

## 📖 Next Steps

1. Read the full `README.md` for comprehensive documentation
2. Explore API endpoints at `/api/v1/docs/`
3. Check test suite in `tests/` for usage examples
4. Review `config/settings.py` for configuration options
5. Customize models in `employees/models.py` as needed

## 🎉 You're Ready!

Your production-ready Employee Management System is running. Start building! 🚀

For detailed documentation, see **README.md**
