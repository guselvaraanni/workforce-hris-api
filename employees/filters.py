"""
employees/filters.py — django-filter FilterSets

Enables proper field-level filtering on API endpoints via query params:
    GET /api/v1/employees/?status=active&salary_min=50000&department=<uuid>
    GET /api/v1/leaves/?status=pending&leave_type=annual&start_after=2025-01-01

Registered in ViewSets via filterset_class = EmployeeFilter.
Requires 'django_filters' in INSTALLED_APPS and DjangoFilterBackend in
DEFAULT_FILTER_BACKENDS (both already set in settings.py).
"""
import django_filters
from django.db.models import Q
from .models import EmployeeProfile, LeaveRequest, AuditLog


class EmployeeFilter(django_filters.FilterSet):
    """
    FilterSet for EmployeeProfile list endpoint.

    Usage:
        ?department=<uuid>         — exact department match
        ?status=active             — employment status
        ?type=full_time            — employment type
        ?salary_min=50000          — salary >= value
        ?salary_max=100000         — salary <= value
        ?joined_after=2024-01-01   — date_of_joining >= date
        ?joined_before=2024-12-31  — date_of_joining <= date
        ?manager=<uuid>            — employees under this manager
    """
    department = django_filters.UUIDFilter(field_name='department__id')
    status = django_filters.CharFilter(field_name='employment_status')
    type = django_filters.CharFilter(field_name='employment_type')
    salary_min = django_filters.NumberFilter(field_name='salary', lookup_expr='gte')
    salary_max = django_filters.NumberFilter(field_name='salary', lookup_expr='lte')
    joined_after = django_filters.DateFilter(field_name='date_of_joining', lookup_expr='gte')
    joined_before = django_filters.DateFilter(field_name='date_of_joining', lookup_expr='lte')
    manager = django_filters.UUIDFilter(field_name='manager__id')
    gender = django_filters.CharFilter(field_name='gender', lookup_expr='iexact')

    class Meta:
        model = EmployeeProfile
        fields = ['department', 'status', 'type', 'salary_min', 'salary_max',
                  'joined_after', 'joined_before', 'manager', 'gender']


class LeaveFilter(django_filters.FilterSet):
    """
    FilterSet for LeaveRequest list endpoint.

    Usage:
        ?status=pending
        ?leave_type=annual
        ?start_after=2025-06-01
        ?start_before=2025-06-30
        ?employee=<uuid>
    """
    status = django_filters.CharFilter(lookup_expr='iexact')
    leave_type = django_filters.CharFilter(lookup_expr='iexact')
    start_after = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_before = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    employee = django_filters.UUIDFilter(field_name='employee__id')

    class Meta:
        model = LeaveRequest
        fields = ['status', 'leave_type', 'start_after', 'start_before', 'employee']


class AuditLogFilter(django_filters.FilterSet):
    """
    FilterSet for AuditLog list endpoint.

    Usage:
        ?action=update
        ?content_type=EmployeeProfile
        ?from=2025-01-01
        ?to=2025-12-31
        ?user_email=admin@example.com
    """
    action = django_filters.CharFilter(lookup_expr='iexact')
    content_type = django_filters.CharFilter(lookup_expr='icontains')
    from_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='date__gte')
    to_date = django_filters.DateFilter(field_name='timestamp', lookup_expr='date__lte')
    user_email = django_filters.CharFilter(field_name='user__email', lookup_expr='icontains')

    class Meta:
        model = AuditLog
        fields = ['action', 'content_type', 'from_date', 'to_date', 'user_email']
