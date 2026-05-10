import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from .factories import UserFactory, DepartmentFactory, EmployeeProfileFactory, LeaveRequestFactory


@pytest.mark.django_db
class TestDepartmentAPI(TestCase):
    """Tests for Department API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.hr_user = UserFactory(is_hr_admin=True)
        self.regular_user = UserFactory()
        self.department = DepartmentFactory()
    
    def test_list_departments(self):
        """Test listing departments"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/api/v1/departments/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_create_department_as_hr_admin(self):
        """Test creating department as HR admin"""
        self.client.force_authenticate(user=self.hr_user)
        data = {
            'name': 'New Department',
            'description': 'Test description',
            'budget': 100000
        }
        response = self.client.post('/api/v1/departments/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_create_department_as_regular_user_fails(self):
        """Test that regular users cannot create departments"""
        self.client.force_authenticate(user=self.regular_user)
        data = {
            'name': 'New Department',
            'description': 'Test description',
            'budget': 100000
        }
        response = self.client.post('/api/v1/departments/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestEmployeeProfileAPI(TestCase):
    """Tests for Employee Profile API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.hr_user = UserFactory(is_hr_admin=True)
        self.employee_user = UserFactory()
        self.employee = EmployeeProfileFactory(user=self.employee_user)
    
    def test_list_employees(self):
        """Test listing employees"""
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.get('/api/v1/employees/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_retrieve_own_employee_profile(self):
        """Test employee can view own profile"""
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.get(f'/api/v1/employees/{self.employee.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_update_own_profile(self):
        """Test employee can update own profile"""
        self.client.force_authenticate(user=self.employee_user)
        data = {'salary': 60000}
        response = self.client.patch(f'/api/v1/employees/{self.employee.id}/', data)
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestLeaveRequestAPI(TestCase):
    """Tests for Leave Request API endpoints with concurrency control"""
    
    def setUp(self):
        self.client = APIClient()
        self.hr_user = UserFactory(is_hr_admin=True)
        self.manager_user = UserFactory(is_manager=True)
        self.employee_user = UserFactory()
        self.employee = EmployeeProfileFactory(user=self.employee_user, manager=self.manager_user)
    
    def test_employee_can_submit_leave_request(self):
        """Test employee can submit a leave request"""
        self.client.force_authenticate(user=self.employee_user)
        start_date = timezone.now().date() + timedelta(days=7)
        end_date = start_date + timedelta(days=5)
        
        data = {
            'start_date': start_date,
            'end_date': end_date,
            'leave_type': 'annual',
            'reason': 'Personal time'
        }
        response = self.client.post('/api/v1/leave-requests/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_manager_can_approve_leave(self):
        """Test manager can approve leave request"""
        leave = LeaveRequestFactory(employee=self.employee, status='pending')
        
        self.client.force_authenticate(user=self.manager_user)
        data = {'approval_notes': 'Approved'}
        response = self.client.post(
            f'/api/v1/leave-requests/{leave.id}/approve_leave/',
            data
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Verify status changed
        leave.refresh_from_db()
        assert leave.status == 'approved'
    
    def test_concurrent_leave_approval_protection(self):
        """Test that concurrent leave approvals are protected"""
        # This would require more complex setup with threading
        # Placeholder for concurrency test
        pass
    
    def test_overlapping_leaves_rejected(self):
        """Test that overlapping leave requests are rejected"""
        start_date = timezone.now().date() + timedelta(days=7)
        end_date = start_date + timedelta(days=5)
        
        # Create first leave request
        LeaveRequestFactory(
            employee=self.employee,
            start_date=start_date,
            end_date=end_date,
            status='approved'
        )
        
        # Try to create overlapping leave
        self.client.force_authenticate(user=self.employee_user)
        overlap_start = start_date + timedelta(days=2)
        overlap_end = overlap_start + timedelta(days=3)
        
        data = {
            'start_date': overlap_start,
            'end_date': overlap_end,
            'leave_type': 'annual',
            'reason': 'Another request'
        }
        response = self.client.post('/api/v1/leave-requests/', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestAuditLogging(TestCase):
    """Tests for audit logging functionality"""
    
    def setUp(self):
        self.client = APIClient()
        self.hr_user = UserFactory(is_hr_admin=True)
        self.department = DepartmentFactory()
    
    def test_audit_log_created_on_department_update(self):
        """Test that audit log is created when department is updated"""
        from employees.models import AuditLog
        
        self.client.force_authenticate(user=self.hr_user)
        data = {'budget': 150000}
        response = self.client.patch(f'/api/v1/departments/{self.department.id}/', data)
        
        assert response.status_code == status.HTTP_200_OK
        
        # Check audit log was created
        audit_logs = AuditLog.objects.filter(object_id=str(self.department.id))
        assert audit_logs.exists()


@pytest.mark.django_db
class TestHealthCheck(TestCase):
    """Tests for health check endpoint"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = self.client.get('/api/v1/health/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == 'healthy'
