"""
employees/template_views.py — Server-side Django template views

These complement your existing API-driven templates with true server-side
rendered pages. Add these to urls.py alongside your TemplateView entries.

Architecture:
- LoginRequiredMixin enforces authentication
- All querysets use select_related / prefetch_related
- Filtering via GET params, pagination via Django's Paginator
- Forms handle CSRF automatically

To wire these up in config/urls.py:
    from employees.template_views import (
        EmployeeListView, EmployeeDetailView, EmployeeCreateView,
        DashboardView, AuditLogTemplateView, UploadStatusView
    )

    urlpatterns += [
        path('ui/dashboard/', DashboardView.as_view(), name='ui-dashboard'),
        path('ui/employees/', EmployeeListView.as_view(), name='ui-employees'),
        path('ui/employees/<uuid:pk>/', EmployeeDetailView.as_view(), name='ui-employee-detail'),
        path('ui/employees/add/', EmployeeCreateView.as_view(), name='ui-employee-add'),
        path('ui/audit/', AuditLogTemplateView.as_view(), name='ui-audit'),
        path('ui/uploads/', UploadStatusView.as_view(), name='ui-uploads'),
    ]
"""
import re

from django.views.generic import ListView, DetailView, CreateView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone

from .models import (
    EmployeeProfile, Department, LeaveRequest,
    AuditLog, BulkUploadJob, CustomUser
)
from .dashboard_context import build_dashboard_context
from .utils.attendance_service import build_today_summary, monthly_attendance_pct


class HRAdminRequiredMixin(UserPassesTestMixin):
    """Mixin that requires the user to be an HR Admin."""
    def test_func(self):
        return self.request.user.is_hr_admin


class MyProfileRedirectView(LoginRequiredMixin, View):
    """Shortcut: /profile/ → current user's HRIS profile page."""
    login_url = '/'

    def get(self, request, *args, **kwargs):
        profile = getattr(request.user, 'profile', None)
        if profile is None:
            messages.info(
                request,
                'Your employee profile is not set up yet. Contact HR or open the directory.',
            )
            return redirect('hris-dashboard')
        return redirect('hris-employee-detail', pk=profile.pk)


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Main dashboard — aggregates key workforce metrics.

    Uses DB-level aggregation (not Python loops) for all stats.
    Query count: ~5 total, regardless of data size.
    """
    template_name = 'dashboard.html'
    login_url = '/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(build_dashboard_context(self.request.user))
        return ctx


class EmployeeListView(LoginRequiredMixin, ListView):
    """
    Paginated, searchable, filterable employee list.

    ORM optimization:
    - select_related('user', 'department', 'manager') — eliminates N+1
    - All filtering done at DB level (WHERE clause), not in Python
    """
    template_name = 'employees.html'
    context_object_name = 'employees'
    paginate_by = 20
    login_url = '/'

    def get_queryset(self):
        qs = (
            EmployeeProfile.objects
            .select_related('user', 'department', 'manager')
            .order_by('user__first_name', 'user__last_name')
        )

        user = self.request.user
        if user.is_hr_admin:
            pass
        elif user.is_manager:
            qs = qs.filter(Q(manager=user) | Q(user=user))
        elif hasattr(user, 'profile'):
            qs = qs.filter(user=user)
        else:
            qs = qs.none()

        # Text search across name, email, employee_id
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(user__email__icontains=q) |
                Q(employee_id__icontains=q)
            )

        # Filter by department
        dept = self.request.GET.get('department')
        if dept:
            qs = qs.filter(department_id=dept)

        # Filter by status
        emp_status = self.request.GET.get('status')
        if emp_status:
            qs = qs.filter(employment_status=emp_status)

        # Filter by employment type
        emp_type = self.request.GET.get('type')
        if emp_type:
            qs = qs.filter(employment_type=emp_type)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.filter(is_active=True).order_by('name')
        ctx['status_choices'] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        ctx['type_choices'] = EmployeeProfile.EMPLOYMENT_TYPE_CHOICES
        ctx['search_query'] = self.request.GET.get('q', '')
        ctx['selected_dept'] = self.request.GET.get('department', '')
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['total_count'] = self.get_queryset().count()
        return ctx


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    """
    Employee detail page with leave history and audit trail.
    """
    template_name = 'employee_detail.html'
    context_object_name = 'employee'
    login_url = '/'

    def get_queryset(self):
        return EmployeeProfile.objects.select_related('user', 'department', 'manager')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        # Enforce ownership: only own profile, HR admin, or direct manager can view
        if not (
            obj.user == user or
            user.is_hr_admin or
            (user.is_manager and obj.manager == user)
        ):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employee = self.object

        ctx['leave_history'] = (
            LeaveRequest.objects
            .filter(employee=employee)
            .select_related('approved_by')
            .order_by('-created_at')[:10]
        )

        ctx['audit_history'] = (
            AuditLog.objects
            .filter(content_type='EmployeeProfile', object_id=str(employee.id))
            .select_related('user')
            .order_by('-timestamp')[:20]
        )

        if employee.skills:
            ctx['skills_list'] = [
                s.strip()
                for s in re.split(r'[;,]', employee.skills)
                if s.strip()
            ]
        else:
            ctx['skills_list'] = []

        ctx['leave_summary'] = {
            'pending': LeaveRequest.objects.filter(
                employee=employee, status='pending',
            ).count(),
            'approved': LeaveRequest.objects.filter(
                employee=employee, status='approved',
            ).count(),
            'rejected': LeaveRequest.objects.filter(
                employee=employee, status='rejected',
            ).count(),
        }
        ctx['attendance_today'] = build_today_summary(employee)
        ctx['attendance_month_pct'] = monthly_attendance_pct(employee)
        viewer = self.request.user
        ctx['can_edit_profile'] = (
            viewer.is_hr_admin
            or viewer == employee.user
            or (viewer.is_manager and employee.manager == viewer)
        )

        return ctx


class EmployeeCreateView(LoginRequiredMixin, HRAdminRequiredMixin, TemplateView):
    """
    Employee creation form page (HR Admin only).
    The actual creation is handled by the API endpoint;
    this view provides the form shell.
    """
    template_name = 'employee_form.html'
    login_url = '/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['departments'] = Department.objects.filter(is_active=True).order_by('name')
        ctx['managers'] = (
            CustomUser.objects
            .filter(is_manager=True, is_active=True)
            .order_by('first_name')
        )
        ctx['status_choices'] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        ctx['type_choices'] = EmployeeProfile.EMPLOYMENT_TYPE_CHOICES
        return ctx


class EmployeeUpdateView(LoginRequiredMixin, TemplateView):
    """
    Employee profile edit page.
    Owners can edit personal details and profile photo.
    HR Admins can edit the full employee profile.
    """
    template_name = 'employee_edit.html'
    login_url = '/'

    def get_employee(self):
        return EmployeeProfile.objects.select_related('user', 'department', 'manager').get(pk=self.kwargs['pk'])

    def dispatch(self, request, *args, **kwargs):
        self.employee = self.get_employee()
        if not (
            request.user.is_hr_admin or
            request.user == self.employee.user or
            (request.user.is_manager and self.employee.manager == request.user)
        ):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['employee'] = self.employee
        ctx['departments'] = Department.objects.filter(is_active=True).order_by('name')
        ctx['managers'] = (
            CustomUser.objects
            .filter(is_manager=True, is_active=True)
            .order_by('first_name')
        )
        ctx['status_choices'] = EmployeeProfile.EMPLOYMENT_STATUS_CHOICES
        ctx['type_choices'] = EmployeeProfile.EMPLOYMENT_TYPE_CHOICES
        ctx['can_edit_full_profile'] = self.request.user.is_hr_admin
        return ctx

    def post(self, request, *args, **kwargs):
        data = request.POST
        files = request.FILES
        employee = self.employee

        if not request.user.is_hr_admin:
            allowed_profile_fields = {
                'date_of_birth', 'gender', 'address', 'city', 'country',
                'postal_code', 'bio', 'skills'
            }
            allowed_user_fields = {'first_name', 'last_name', 'phone_number'}
        else:
            allowed_profile_fields = {
                'employee_id', 'department', 'manager', 'date_of_birth', 'gender',
                'address', 'city', 'country', 'postal_code', 'employment_status',
                'employment_type', 'salary', 'bonus', 'date_of_leaving', 'bio', 'skills'
            }
            allowed_user_fields = {'first_name', 'last_name', 'email', 'phone_number'}

        with transaction.atomic():
            for field in allowed_user_fields:
                if field in data:
                    value = data.get(field).strip()
                    setattr(employee.user, field, value)
            employee.user.save()

            for field in allowed_profile_fields:
                if field in data:
                    value = data.get(field)
                    if value == '':
                        value = None
                    setattr(employee, field, value)

            if 'profile_picture' in files:
                employee.profile_picture = files['profile_picture']
            employee.save()

        messages.success(request, 'Employee profile updated successfully.')
        return redirect('hris-employee-detail', pk=employee.pk)


class AuditLogTemplateView(LoginRequiredMixin, HRAdminRequiredMixin, ListView):
    """
    Paginated, filterable audit log view (HR Admin only).
    """
    template_name = 'audit.html'
    context_object_name = 'audit_logs'
    paginate_by = 50
    login_url = '/'

    def get_queryset(self):
        qs = AuditLog.objects.select_related('user').order_by('-timestamp')

        action = self.request.GET.get('action')
        if action:
            qs = qs.filter(action=action)

        content_type = self.request.GET.get('content_type')
        if content_type:
            qs = qs.filter(content_type=content_type)

        user_email = self.request.GET.get('user')
        if user_email:
            qs = qs.filter(user__email__icontains=user_email)

        # Date range filtering
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_choices'] = AuditLog.ACTION_CHOICES
        ctx['content_types'] = (
            AuditLog.objects
            .values_list('content_type', flat=True)
            .distinct()
            .order_by('content_type')
        )
        ctx['selected_action'] = self.request.GET.get('action', '')
        ctx['selected_content_type'] = self.request.GET.get('content_type', '')
        ctx['total_count'] = self.get_queryset().count()
        return ctx


class UploadStatusView(LoginRequiredMixin, HRAdminRequiredMixin, ListView):
    """
    Bulk upload job tracking page with live status indicators.
    """
    template_name = 'uploads.html'
    context_object_name = 'jobs'
    paginate_by = 20
    login_url = '/'

    def get_queryset(self):
        return (
            BulkUploadJob.objects
            .select_related('uploaded_by')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['active_jobs'] = BulkUploadJob.objects.filter(
            status='processing'
        ).count()
        ctx['status_choices'] = BulkUploadJob.STATUS_CHOICES
        return ctx


class LeaveListView(LoginRequiredMixin, ListView):
    """Paginated, filterable leave requests view."""
    template_name = 'leaves.html'
    context_object_name = 'leaves'
    paginate_by = 20
    login_url = '/'

    def get_queryset(self):
        user = self.request.user
        qs = LeaveRequest.objects.select_related(
            'employee__user', 'employee__department', 'approved_by'
        ).order_by('-created_at')

        if not user.is_hr_admin:
            if user.is_manager:
                qs = qs.filter(employee__manager=user)
            elif hasattr(user, 'profile'):
                qs = qs.filter(employee=user.profile)
            else:
                qs = qs.none()

        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['status_choices'] = LeaveRequest.STATUS_CHOICES
        ctx['leave_type_choices'] = LeaveRequest.LEAVE_TYPE_CHOICES
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['is_hr_admin'] = user.is_hr_admin
        ctx['can_submit_leave'] = not user.is_hr_admin and hasattr(user, 'profile')
        ctx['can_approve_leaves'] = user.is_hr_admin or user.is_manager
        return ctx


class DepartmentListView(LoginRequiredMixin, ListView):
    """Department list with headcount annotation."""
    template_name = 'departments.html'
    context_object_name = 'departments'
    paginate_by = 20
    login_url = '/'

    def get_queryset(self):
        from django.db.models import Count, Q
        return (
            Department.objects
            .filter(is_active=True)
            .annotate(
                headcount=Count(
                    'employees',
                    filter=Q(employees__employment_status='active')
                )
            )
            .select_related('head')
            .order_by('name')
        )
