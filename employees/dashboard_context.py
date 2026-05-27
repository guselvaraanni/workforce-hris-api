"""Dashboard context builders for role-based template views."""
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import (
    AttendanceRecord, AuditLog, BulkUploadJob, Department,
    EmployeeProfile, LeaveRequest,
)
from .utils.attendance_service import (
    build_today_summary,
    get_employee_for_user,
    monthly_attendance_pct,
    team_attendance_today,
    week_summary,
)


def build_dashboard_context(user):
    ctx = {
        'today_date': timezone.localdate(),
        'user_profile': getattr(user, 'profile', None),
    }

    ctx['total_employees'] = EmployeeProfile.objects.filter(
        employment_status='active'
    ).count()
    ctx['total_departments'] = Department.objects.filter(is_active=True).count()
    ctx['pending_leaves'] = LeaveRequest.objects.filter(status='pending').count()
    ctx['recent_uploads'] = BulkUploadJob.objects.filter(
        status__in=['completed', 'processing']
    ).count()

    if user.is_hr_admin:
        ctx['dept_breakdown'] = list(
            Department.objects.filter(is_active=True)
            .annotate(
                headcount=Count(
                    'employees',
                    filter=Q(employees__employment_status='active'),
                ),
                avg_salary=Avg(
                    'employees__salary',
                    filter=Q(employees__employment_status='active'),
                ),
            )
            .values('name', 'headcount', 'avg_salary')
            .order_by('-headcount')[:8]
        )
        ctx['recent_audit'] = list(
            AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
        )

    if user.is_manager:
        ctx['my_team'] = list(
            EmployeeProfile.objects.filter(
                manager=user, employment_status='active',
            ).select_related('user', 'department').order_by('user__first_name')[:12]
        )
        ctx['my_team_count'] = EmployeeProfile.objects.filter(
            manager=user, employment_status='active',
        ).count()
        ctx['my_team_pending_leaves'] = LeaveRequest.objects.filter(
            status='pending', employee__manager=user,
        ).count()
        ctx['pending_leave_requests'] = list(
            LeaveRequest.objects.filter(
                status='pending', employee__manager=user,
            ).select_related('employee__user').order_by('created_at')[:6]
        )
        ctx['team_attendance'] = team_attendance_today(user)
        ctx['team_on_leave_today'] = LeaveRequest.objects.filter(
            status='approved',
            employee__manager=user,
            start_date__lte=timezone.localdate(),
            end_date__gte=timezone.localdate(),
        ).count()

    if hasattr(user, 'profile'):
        employee = user.profile
    elif not user.is_hr_admin:
        employee = get_employee_for_user(user)
    else:
        employee = None

    if employee:
        ctx['user_profile'] = employee
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
        ctx['recent_my_leaves'] = list(
            LeaveRequest.objects.filter(employee=employee).order_by('-created_at')[:5]
        )
        ctx['upcoming_leave'] = (
            LeaveRequest.objects.filter(
                employee=employee,
                start_date__gte=timezone.localdate(),
                status='approved',
            ).order_by('start_date').first()
        )
        ctx['attendance_today'] = build_today_summary(employee)
        ctx['attendance_week'] = week_summary(employee)
        ctx['attendance_month_pct'] = monthly_attendance_pct(employee)
        ctx['attendance_history'] = list(
            AttendanceRecord.objects.filter(employee=employee).order_by('-date')[:7]
        )

    return ctx
