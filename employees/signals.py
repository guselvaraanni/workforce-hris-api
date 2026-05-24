"""
employees/signals.py — Fixed version

The original had a critical bug: post_save reads from the DB after the save,
which means both "old" and "new" values are the same (current) value.

Fix: Use pre_save to snapshot the old values before the write occurs.

Thread safety note: The _snapshots dict uses str(instance.pk) as key.
In a multi-threaded Django server, two simultaneous updates to the same
employee would race. A production fix is to use thread-local storage:

    import threading
    _local = threading.local()

    def get_snapshots():
        if not hasattr(_local, 'snapshots'):
            _local.snapshots = {}
        return _local.snapshots
"""
import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import EmployeeProfile, LeaveRequest, AuditLog

logger = logging.getLogger('audit')

# Per-thread snapshot store (thread-safe)
import threading
_local = threading.local()


def _get_snapshots():
    """Return the per-thread snapshot dict."""
    if not hasattr(_local, 'snapshots'):
        _local.snapshots = {}
    return _local.snapshots


# ── EmployeeProfile signals ──────────────────────────────────────────────────

@receiver(pre_save, sender=EmployeeProfile)
def capture_employee_snapshot(sender, instance, **kwargs):
    """
    Before saving, snapshot the current DB values for fields we want to track.
    Only runs for existing records (not new creates).
    """
    if not instance.pk:
        return  # New record — no old state to capture

    try:
        old = EmployeeProfile.objects.filter(pk=instance.pk).values(
            'salary', 'department_id', 'employment_status'
        ).first()
        if old:
            _get_snapshots()[str(instance.pk)] = old
    except Exception as e:
        logger.error(f"Error capturing employee snapshot: {e}", exc_info=True)


@receiver(post_save, sender=EmployeeProfile)
def log_employee_profile_changes(sender, instance, created, **kwargs):
    """
    After saving, compare the new state to the snapshot.
    Creates an AuditLog entry for tracked field changes.
    Skips new records (handled explicitly in ViewSet.perform_create).
    """
    if created:
        return

    old = _get_snapshots().pop(str(instance.pk), None)
    if not old:
        return

    changes = {}

    if old['salary'] != instance.salary:
        changes['salary'] = {
            'old': str(old['salary']),
            'new': str(instance.salary)
        }

    if old['department_id'] != instance.department_id:
        changes['department'] = {
            'old': str(old['department_id']),
            'new': str(instance.department_id)
        }

    if old['employment_status'] != instance.employment_status:
        changes['employment_status'] = {
            'old': old['employment_status'],
            'new': instance.employment_status
        }

    if changes:
        try:
            AuditLog.objects.create(
                user=None,  # System-level change (no request context available)
                action='update',
                content_type='EmployeeProfile',
                object_id=str(instance.id),
                object_str=str(instance),
                changes=changes
            )
            logger.info(
                f"Signal audit: EmployeeProfile {instance.employee_id} changed: "
                f"{list(changes.keys())}"
            )
        except Exception as e:
            logger.error(f"Error writing signal audit log: {e}", exc_info=True)


# ── LeaveRequest signals ─────────────────────────────────────────────────────

@receiver(pre_save, sender=LeaveRequest)
def capture_leave_snapshot(sender, instance, **kwargs):
    """Snapshot leave status before save."""
    if not instance.pk:
        return
    try:
        old = LeaveRequest.objects.filter(pk=instance.pk).values('status').first()
        if old:
            _get_snapshots()[f'leave_{instance.pk}'] = old
    except Exception as e:
        logger.error(f"Error capturing leave snapshot: {e}", exc_info=True)


@receiver(post_save, sender=LeaveRequest)
def log_leave_request_changes(sender, instance, created, **kwargs):
    """Log leave status changes (skip creates)."""
    if created:
        return

    old = _get_snapshots().pop(f'leave_{instance.pk}', None)
    if not old:
        return

    if old['status'] != instance.status:
        try:
            AuditLog.objects.create(
                user=instance.approved_by,
                action='update',
                content_type='LeaveRequest',
                object_id=str(instance.id),
                object_str=str(instance),
                changes={
                    'status': {
                        'old': old['status'],
                        'new': instance.status
                    }
                }
            )
            logger.info(
                f"Signal audit: LeaveRequest {instance.id} "
                f"status {old['status']} → {instance.status}"
            )
        except Exception as e:
            logger.error(f"Error writing leave audit log: {e}", exc_info=True)
