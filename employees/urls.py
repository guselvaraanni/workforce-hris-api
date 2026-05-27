from django.urls import path, include
from rest_framework.routers import DefaultRouter

app_name = 'api'
from .views import (
    UserRegistrationView, UserListView, DepartmentViewSet,
    EmployeeProfileViewSet, LeaveRequestViewSet, AuditLogViewSet,
    BulkUploadViewSet, AttendanceViewSet, HealthCheckView
)

# Create router for viewsets
router = DefaultRouter()
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'employees', EmployeeProfileViewSet, basename='employee')
router.register(r'leave-requests', LeaveRequestViewSet, basename='leave-request')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
router.register(r'bulk-uploads', BulkUploadViewSet, basename='bulk-upload')
router.register(r'attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    # Health check
    path('health/', HealthCheckView.as_view(), name='health-check'),
    
    # User management
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/users/', UserListView.as_view(), name='user-list'),
    
    # Router URLs
    path('', include(router.urls)),
]
