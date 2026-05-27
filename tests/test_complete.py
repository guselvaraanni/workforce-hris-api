"""
tests/test_complete.py — Full pytest test suite

Run with: pytest tests/ -v --tb=short
"""
import io
import threading
import pytest
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status as http_status

from employees.models import (
    CustomUser, Department, EmployeeProfile,
    LeaveRequest, AuditLog, BulkUploadJob
)
from employees.utils.csv_processor import process_csv_file
from .factories import UserFactory, DepartmentFactory, EmployeeProfileFactory, LeaveRequestFactory


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_csv_bytes(*rows):
    headers = 'email,first_name,last_name,employee_id,salary,department'
    lines = [headers]
    for r in rows:
        lines.append(
            f"{r.get('email','')},{r.get('first_name','')},{r.get('last_name','')},"
            f"{r.get('employee_id','')},{r.get('salary','')},{r.get('department','')}"
        )
    return io.BytesIO('\n'.join(lines).encode('utf-8'))


def employee_row(n, **overrides):
    d = {
        'email': f'emp{n}@test.com',
        'first_name': f'First{n}',
        'last_name': f'Last{n}',
        'employee_id': f'EMP{n:05d}',
        'salary': '50000',
        'department': 'Engineering',
    }
    d.update(overrides)
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Department API Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDepartmentAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        self.regular = UserFactory()
        self.dept = DepartmentFactory(name='Engineering')

    def test_list_requires_auth(self):
        r = self.client.get('/api/v1/departments/')
        assert r.status_code == 401

    def test_list_authenticated(self):
        self.client.force_authenticate(user=self.regular)
        r = self.client.get('/api/v1/departments/')
        assert r.status_code == 200
        assert 'results' in r.data

    def test_create_as_hr_admin(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.post('/api/v1/departments/', {'name': 'Finance', 'budget': 100000})
        assert r.status_code == 201
        assert Department.objects.filter(name='Finance').exists()

    def test_create_as_regular_forbidden(self):
        self.client.force_authenticate(user=self.regular)
        r = self.client.post('/api/v1/departments/', {'name': 'Finance', 'budget': 100000})
        assert r.status_code == 403

    def test_update_creates_audit_log(self):
        self.client.force_authenticate(user=self.hr)
        self.client.patch(f'/api/v1/departments/{self.dept.id}/', {'budget': 999000})
        assert AuditLog.objects.filter(
            content_type='Department', object_id=str(self.dept.id), action='update'
        ).exists()

    def test_delete_department(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.delete(f'/api/v1/departments/{self.dept.id}/')
        assert r.status_code == 204


# ─────────────────────────────────────────────────────────────────────────────
# Employee Profile API Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEmployeeProfileAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        self.manager = UserFactory(is_manager=True)
        self.emp_user = UserFactory()
        self.dept = DepartmentFactory()
        self.emp = EmployeeProfileFactory(
            user=self.emp_user, department=self.dept, manager=self.manager
        )

    def test_list_as_hr_admin(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/employees/')
        assert r.status_code == 200

    def test_retrieve_own_profile(self):
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.get(f'/api/v1/employees/{self.emp.id}/')
        assert r.status_code == 200
        assert r.data['employee_id'] == self.emp.employee_id

    def test_cannot_retrieve_other_profile(self):
        other_emp = EmployeeProfileFactory()
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.get(f'/api/v1/employees/{other_emp.id}/')
        assert r.status_code in [403, 404]

    def test_update_salary_creates_audit(self):
        self.client.force_authenticate(user=self.hr)
        self.client.patch(f'/api/v1/employees/{self.emp.id}/', {'salary': '75000'})
        assert AuditLog.objects.filter(
            content_type='EmployeeProfile', object_id=str(self.emp.id), action='update'
        ).exists()

    def test_delete_as_manager_forbidden(self):
        self.client.force_authenticate(user=self.manager)
        r = self.client.delete(f'/api/v1/employees/{self.emp.id}/')
        assert r.status_code == 403

    def test_delete_as_hr_admin(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.delete(f'/api/v1/employees/{self.emp.id}/')
        assert r.status_code == 204

    def test_by_department_action(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get(f'/api/v1/employees/by_department/?department_id={self.dept.id}')
        assert r.status_code == 200

    def test_by_department_missing_param(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/employees/by_department/')
        assert r.status_code == 400

    def test_my_team_as_manager(self):
        self.client.force_authenticate(user=self.manager)
        r = self.client.get('/api/v1/employees/my_team/')
        assert r.status_code == 200

    def test_search_by_name(self):
        self.client.force_authenticate(user=self.hr)
        name = self.emp_user.first_name
        r = self.client.get(f'/api/v1/employees/?search={name}')
        assert r.status_code == 200

    def test_filter_by_status(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/employees/?status=active')
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Leave Request Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLeaveRequestAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        self.manager = UserFactory(is_manager=True)
        self.emp_user = UserFactory()
        self.emp = EmployeeProfileFactory(user=self.emp_user, manager=self.manager)
        self.start = timezone.now().date() + timedelta(days=14)
        self.end = self.start + timedelta(days=4)

    def _payload(self, **kw):
        d = {'start_date': self.start, 'end_date': self.end, 'leave_type': 'annual', 'reason': 'Vacation'}
        d.update(kw)
        return d

    def test_submit_leave(self):
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.post('/api/v1/leave-requests/', self._payload())
        assert r.status_code == 201

    def test_submit_leave_creates_missing_profile(self):
        user_without_profile = UserFactory()
        EmployeeProfile.objects.filter(user=user_without_profile).delete()

        self.client.force_authenticate(user=user_without_profile)
        r = self.client.post('/api/v1/leave-requests/', self._payload())

        assert r.status_code == 201
        assert hasattr(user_without_profile, 'profile')
        assert user_without_profile.profile.employee_id == f'EMP-{user_without_profile.id}'

    def test_start_after_end_rejected(self):
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.post('/api/v1/leave-requests/', self._payload(
            start_date=self.end, end_date=self.start
        ))
        assert r.status_code == 400

    def test_overlapping_leave_rejected(self):
        LeaveRequestFactory(employee=self.emp, start_date=self.start, end_date=self.end, status='approved')
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.post('/api/v1/leave-requests/', self._payload(
            start_date=self.start + timedelta(days=1),
            end_date=self.end + timedelta(days=2)
        ))
        assert r.status_code == 400

    def test_approve_leave(self):
        leave = LeaveRequestFactory(employee=self.emp, status='pending')
        self.client.force_authenticate(user=self.manager)
        r = self.client.post(f'/api/v1/leave-requests/{leave.id}/approve_leave/', {'approval_notes': 'OK'})
        assert r.status_code == 200
        leave.refresh_from_db()
        assert leave.status == 'approved'

    def test_reject_leave(self):
        leave = LeaveRequestFactory(employee=self.emp, status='pending')
        self.client.force_authenticate(user=self.manager)
        r = self.client.post(f'/api/v1/leave-requests/{leave.id}/reject_leave/', {'approval_notes': 'Deny'})
        assert r.status_code == 200
        leave.refresh_from_db()
        assert leave.status == 'rejected'

    def test_cannot_approve_already_approved(self):
        leave = LeaveRequestFactory(employee=self.emp, status='approved')
        self.client.force_authenticate(user=self.manager)
        r = self.client.post(f'/api/v1/leave-requests/{leave.id}/approve_leave/', {})
        assert r.status_code == 400

    def test_approval_audit_log(self):
        leave = LeaveRequestFactory(employee=self.emp, status='pending')
        self.client.force_authenticate(user=self.manager)
        self.client.post(f'/api/v1/leave-requests/{leave.id}/approve_leave/', {})
        assert AuditLog.objects.filter(
            content_type='LeaveRequest', object_id=str(leave.id), action='approve'
        ).exists()

    def test_my_requests(self):
        LeaveRequestFactory(employee=self.emp, status='pending')
        self.client.force_authenticate(user=self.emp_user)
        r = self.client.get('/api/v1/leave-requests/my_requests/')
        assert r.status_code == 200

    def test_pending_approvals_as_hr(self):
        LeaveRequestFactory(employee=self.emp, status='pending')
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/leave-requests/pending_approvals/')
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# CSV Ingestion Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestCSVIngestion(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        self.client.force_authenticate(user=self.hr)

    def _upload(self, *rows):
        return self.client.post(
            '/api/v1/bulk-uploads/',
            {'csv_file': make_csv_bytes(*rows)},
            format='multipart'
        )

    def _upload_and_process(self, *rows):
        r = self._upload(*rows)
        assert r.status_code == 201
        process_csv_file(r.data['id'])
        return BulkUploadJob.objects.get(id=r.data['id'])

    def test_upload_creates_job(self):
        r = self._upload(employee_row(1))
        assert r.status_code == 201
        assert BulkUploadJob.objects.filter(id=r.data['id']).exists()

    def test_valid_row_creates_employee(self):
        job = self._upload_and_process(employee_row(901))
        assert job.status == 'completed'
        assert job.successful_records == 1
        assert EmployeeProfile.objects.filter(employee_id='EMP00901').exists()

    def test_user_and_profile_both_created(self):
        self._upload_and_process(employee_row(902))
        assert CustomUser.objects.filter(email='emp902@test.com').exists()
        assert EmployeeProfile.objects.filter(employee_id='EMP00902').exists()

    def test_department_auto_created(self):
        self._upload_and_process(employee_row(903, department='NewDept'))
        assert Department.objects.filter(name='NewDept').exists()

    def test_audit_log_created_per_employee(self):
        self._upload_and_process(employee_row(904))
        profile = EmployeeProfile.objects.get(employee_id='EMP00904')
        assert AuditLog.objects.filter(
            content_type='EmployeeProfile',
            object_id=str(profile.id),
            action='create'
        ).exists()
        log = AuditLog.objects.get(content_type='EmployeeProfile', object_id=str(profile.id))
        assert log.changes.get('source') == 'bulk_csv_upload'

    def test_duplicate_email_in_error_log(self):
        UserFactory(email='dup@test.com')
        job = self._upload_and_process(employee_row(905, email='dup@test.com'))
        assert job.failed_records == 1
        assert any('dup@test.com' in str(e) for e in job.error_log)

    def test_duplicate_employee_id_in_error_log(self):
        existing = EmployeeProfileFactory()
        job = self._upload_and_process(employee_row(906, employee_id=existing.employee_id))
        assert job.failed_records == 1

    def test_invalid_salary_in_error_log(self):
        job = self._upload_and_process(employee_row(907, salary='bad'))
        assert job.failed_records == 1
        assert any('salary' in str(e).lower() for e in job.error_log)

    def test_negative_salary_in_error_log(self):
        job = self._upload_and_process(employee_row(908, salary='-5000'))
        assert job.failed_records == 1

    def test_missing_headers_fails_job(self):
        bad = io.BytesIO(b'email,first_name\njohn@t.com,John\n')
        r = self.client.post('/api/v1/bulk-uploads/', {'csv_file': bad}, format='multipart')
        process_csv_file(r.data['id'])
        job = BulkUploadJob.objects.get(id=r.data['id'])
        assert job.status == 'failed'

    def test_empty_csv_no_crash(self):
        empty = io.BytesIO(b'email,first_name,last_name,employee_id,salary,department\n')
        r = self.client.post('/api/v1/bulk-uploads/', {'csv_file': empty}, format='multipart')
        process_csv_file(r.data['id'])
        job = BulkUploadJob.objects.get(id=r.data['id'])
        assert job.successful_records == 0

    def test_mixed_valid_and_invalid_rows(self):
        job = self._upload_and_process(employee_row(909), employee_row(910, salary='bad'))
        assert job.successful_records == 1
        assert job.failed_records == 1
        assert EmployeeProfile.objects.filter(employee_id='EMP00909').exists()
        assert not EmployeeProfile.objects.filter(employee_id='EMP00910').exists()

    def test_duplicate_email_within_csv(self):
        job = self._upload_and_process(
            employee_row(911),
            employee_row(912, email='emp911@test.com')  # same email as row 1
        )
        assert job.successful_records == 1
        assert job.failed_records == 1

    def test_total_records_set(self):
        rows = [employee_row(i) for i in range(920, 925)]
        job = self._upload_and_process(*rows)
        assert job.total_records == 5

    def test_status_endpoint(self):
        r = self._upload(employee_row(930))
        sr = self.client.get(f'/api/v1/bulk-uploads/{r.data["id"]}/status/')
        assert sr.status_code == 200
        assert 'status' in sr.data

    def test_upload_requires_hr_admin(self):
        regular = UserFactory()
        self.client.force_authenticate(user=regular)
        r = self.client.post(
            '/api/v1/bulk-uploads/',
            {'csv_file': make_csv_bytes(employee_row(999))},
            format='multipart'
        )
        assert r.status_code == 403

    def test_retry_failed_job(self):
        bad = io.BytesIO(b'wrong\nheader\n')
        r = self.client.post('/api/v1/bulk-uploads/', {'csv_file': bad}, format='multipart')
        process_csv_file(r.data['id'])
        job = BulkUploadJob.objects.get(id=r.data['id'])
        assert job.status == 'failed'

        retry = self.client.post(f'/api/v1/bulk-uploads/{job.id}/retry/')
        assert retry.status_code == 200
        job.refresh_from_db()
        assert job.status in ['pending', 'processing', 'failed', 'completed']


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAuditLog(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        self.dept = DepartmentFactory()

    def test_audit_list_requires_hr_admin(self):
        regular = UserFactory()
        self.client.force_authenticate(user=regular)
        r = self.client.get('/api/v1/audit-logs/')
        assert r.status_code == 403

    def test_audit_list_as_hr_admin(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/audit-logs/')
        assert r.status_code == 200

    def test_create_dept_writes_audit(self):
        self.client.force_authenticate(user=self.hr)
        self.client.post('/api/v1/departments/', {'name': 'AuditTestDept', 'budget': 10000})
        assert AuditLog.objects.filter(content_type='Department', action='create').exists()

    def test_audit_log_has_user(self):
        self.client.force_authenticate(user=self.hr)
        self.client.patch(f'/api/v1/departments/{self.dept.id}/', {'budget': 250000})
        log = AuditLog.objects.filter(content_type='Department').latest('timestamp')
        assert log.user == self.hr

    def test_employee_history_endpoint(self):
        emp = EmployeeProfileFactory()
        self.client.force_authenticate(user=self.hr)
        r = self.client.get(f'/api/v1/audit-logs/employee_history/?employee_id={emp.id}')
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# Analytics Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestAnalytics(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hr = UserFactory(is_hr_admin=True)
        dept = DepartmentFactory()
        for i in range(3):
            EmployeeProfileFactory(department=dept, employment_status='active', salary=Decimal('60000'))

    def test_analytics_returns_200(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/analytics/')
        assert r.status_code == 200

    def test_analytics_contains_summary(self):
        self.client.force_authenticate(user=self.hr)
        r = self.client.get('/api/v1/analytics/')
        assert 'summary' in r.data
        assert r.data['summary']['total_active'] >= 3

    def test_analytics_requires_hr_admin(self):
        regular = UserFactory()
        self.client.force_authenticate(user=regular)
        r = self.client.get('/api/v1/analytics/')
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestHealthCheck(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_200_no_auth(self):
        r = self.client.get('/api/v1/health/')
        assert r.status_code == 200
        assert r.data['status'] == 'healthy'


# ─────────────────────────────────────────────────────────────────────────────
# Serializer Unit Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSerializerValidation(TestCase):
    def test_leave_dates_reversed(self):
        from employees.serializers import LeaveRequestSerializer
        emp = EmployeeProfileFactory()
        data = {
            'employee': emp.id, 'start_date': '2025-12-10', 'end_date': '2025-12-05',
            'leave_type': 'annual', 'reason': 'Test'
        }
        s = LeaveRequestSerializer(data=data)
        assert not s.is_valid()

    def test_password_mismatch(self):
        from employees.serializers import CustomUserCreateSerializer
        data = {
            'email': 'x@x.com', 'username': 'x', 'first_name': 'X',
            'last_name': 'Y', 'password': 'pass1', 'password2': 'pass2'
        }
        s = CustomUserCreateSerializer(data=data)
        assert not s.is_valid()


# ─────────────────────────────────────────────────────────────────────────────
# Concurrency — select_for_update (requires TransactionTestCase)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestConcurrencyControl(TransactionTestCase):
    def test_double_approve_prevented(self):
        """
        Two threads simultaneously try to approve the same leave.
        Only one should succeed; leave.status should be 'approved' exactly once.
        """
        manager = UserFactory(is_manager=True)
        hr = UserFactory(is_hr_admin=True)
        emp = EmployeeProfileFactory(manager=manager)
        leave = LeaveRequestFactory(employee=emp, status='pending')

        results = []
        barrier = threading.Barrier(2)

        def approve(approver):
            client = APIClient()
            client.force_authenticate(user=approver)
            barrier.wait()
            r = client.post(
                f'/api/v1/leave-requests/{leave.id}/approve_leave/',
                {'approval_notes': 'Approved'}
            )
            results.append(r.status_code)

        t1 = threading.Thread(target=approve, args=(manager,))
        t2 = threading.Thread(target=approve, args=(hr,))
        t1.start(); t2.start()
        t1.join(timeout=15); t2.join(timeout=15)

        assert http_status.HTTP_200_OK in results
        leave.refresh_from_db()
        assert leave.status == 'approved'
