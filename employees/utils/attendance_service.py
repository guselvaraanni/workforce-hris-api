"""
Attendance business logic — check-in/out, summaries, validation.
Uses Django timezone (settings.TIME_ZONE) for date boundaries.
"""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone

from ..models import AttendanceRecord, EmployeeProfile, LeaveRequest


def _local_today():
    return timezone.localdate()


def _local_now():
    return timezone.now()


def get_employee_for_user(user):
    if hasattr(user, 'profile'):
        return user.profile
    if user.is_authenticated and not user.is_superuser:
        from ..models import generate_employee_id
        profile, _ = EmployeeProfile.objects.get_or_create(
            user=user,
            defaults={
                'employee_id': generate_employee_id(user),
                'salary': 0,
            },
        )
        return profile
    return None


def get_or_create_today_record(employee):
    today = _local_today()
    record, _ = AttendanceRecord.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={'status': 'absent'},
    )
    return record


def check_in(user):
    employee = get_employee_for_user(user)
    if not employee:
        return None, {'error': 'No employee profile linked to this account.'}

    today = _local_today()
    with transaction.atomic():
        record = (
            AttendanceRecord.objects
            .select_for_update()
            .filter(employee=employee, date=today)
            .first()
        )
        if record is None:
            record = AttendanceRecord.objects.create(
                employee=employee,
                date=today,
                status='absent',
            )

        if record.check_in:
            return None, {'error': 'You have already checked in today.'}
        if record.check_out:
            return None, {'error': 'Attendance for today is already completed.'}

        record.check_in = _local_now()
        record.status = 'present'
        record.save(update_fields=['check_in', 'status', 'updated_at'])

    return record, None


def check_out(user):
    employee = get_employee_for_user(user)
    if not employee:
        return None, {'error': 'No employee profile linked to this account.'}

    today = _local_today()
    with transaction.atomic():
        record = (
            AttendanceRecord.objects
            .select_for_update()
            .filter(employee=employee, date=today)
            .first()
        )
        if not record or not record.check_in:
            return None, {'error': 'You must check in before checking out.'}
        if record.check_out:
            return None, {'error': 'You have already checked out today.'}

        now = _local_now()
        if now <= record.check_in:
            return None, {'error': 'Check-out time must be after check-in time.'}

        record.check_out = now
        record.status = 'present'
        record.save(update_fields=['check_out', 'status', 'updated_at'])

    return record, None


def build_today_summary(employee):
    today = _local_today()
    record = AttendanceRecord.objects.filter(employee=employee, date=today).first()

    on_approved_leave = LeaveRequest.objects.filter(
        employee=employee,
        status='approved',
        start_date__lte=today,
        end_date__gte=today,
    ).exists()

    if record is None and on_approved_leave:
        status_label = 'on_leave'
        can_check_in = False
        can_check_out = False
    elif record is None:
        status_label = 'not_started'
        can_check_in = True
        can_check_out = False
    elif record.check_out:
        status_label = 'completed'
        can_check_in = False
        can_check_out = False
    elif record.check_in:
        status_label = 'checked_in'
        can_check_in = False
        can_check_out = True
    else:
        status_label = 'absent'
        can_check_in = True
        can_check_out = False

    duration_seconds = 0
    if record and record.check_in:
        end = record.check_out or _local_now()
        duration_seconds = max(0, int((end - record.check_in).total_seconds()))

    hours = duration_seconds // 3600
    minutes = (duration_seconds % 3600) // 60
    duration_display = f'{hours}h {minutes}m'

    target_seconds = 8 * 3600
    progress_pct = min(100, int((duration_seconds / target_seconds) * 100)) if target_seconds else 0

    return {
        'record': record,
        'status': status_label,
        'can_check_in': can_check_in,
        'can_check_out': can_check_out,
        'check_in_display': record.check_in.strftime('%I:%M %p') if record and record.check_in else '—',
        'check_out_display': record.check_out.strftime('%I:%M %p') if record and record.check_out else '—',
        'duration_display': duration_display,
        'duration_seconds': duration_seconds,
        'progress_pct': progress_pct,
        'on_leave': on_approved_leave,
    }


def week_summary(employee):
    today = _local_today()
    start = today - timedelta(days=6)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start,
            date__lte=today,
        )
    }
    days = []
    present_count = 0
    for i in range(7):
        d = start + timedelta(days=i)
        rec = records.get(d)
        if rec and rec.check_in:
            state = 'present'
            present_count += 1
        elif rec and rec.status == 'on_leave':
            state = 'leave'
        elif d.weekday() >= 5:
            state = 'weekend'
        else:
            state = 'absent'
        days.append({
            'date': d,
            'label': d.strftime('%a'),
            'state': state,
            'is_today': d == today,
        })
    pct = int((present_count / 5) * 100) if present_count else 0
    if today.weekday() < 5:
        pct = min(100, int((present_count / max(1, min(5, (today.weekday() + 1)))) * 100))
    return {'days': days, 'present_count': present_count, 'attendance_pct': pct}


def monthly_attendance_pct(employee, days=30):
    today = _local_today()
    start = today - timedelta(days=days - 1)
    qs = AttendanceRecord.objects.filter(
        employee=employee,
        date__gte=start,
        date__lte=today,
    )
    total_workdays = sum(1 for i in range(days) if (start + timedelta(days=i)).weekday() < 5)
    present = qs.filter(check_in__isnull=False).count()
    if total_workdays == 0:
        return 0
    return int((present / total_workdays) * 100)


def team_attendance_today(manager_user, limit=8):
    team = EmployeeProfile.objects.filter(
        manager=manager_user,
        employment_status='active',
    ).select_related('user', 'department')[:limit]

    today = _local_today()
    result = []
    for emp in team:
        rec = AttendanceRecord.objects.filter(employee=emp, date=today).first()
        if rec and rec.check_in and not rec.check_out:
            st = 'in'
        elif rec and rec.check_out:
            st = 'out'
        elif LeaveRequest.objects.filter(
            employee=emp, status='approved',
            start_date__lte=today, end_date__gte=today,
        ).exists():
            st = 'leave'
        else:
            st = 'away'
        result.append({'employee': emp, 'status': st, 'record': rec})
    return result
