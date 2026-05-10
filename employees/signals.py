from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import EmployeeProfile, LeaveRequest, AuditLog
import logging

logger = logging.getLogger('audit')


@receiver(post_save, sender=EmployeeProfile)
def log_employee_profile_changes(sender, instance, created, **kwargs):
    """
    Signal handler to log changes to EmployeeProfile.
    Creates an audit log when salary or department is updated.
    """
    if created:
        return  # Skip for new creates as they're handled in views
    
    try:
        # Check if salary or department changed
        old_instance = EmployeeProfile.objects.filter(pk=instance.pk).values(
            'salary', 'department_id'
        ).first()
        
        if old_instance:
            changes = {}
            
            if old_instance['salary'] != instance.salary:
                changes['salary'] = {
                    'old': str(old_instance['salary']),
                    'new': str(instance.salary)
                }
            
            if old_instance['department_id'] != instance.department_id:
                changes['department'] = {
                    'old': str(old_instance['department_id']),
                    'new': str(instance.department_id)
                }
            
            if changes:
                AuditLog.objects.create(
                    user=None,  # System action
                    action='update',
                    content_type='EmployeeProfile',
                    object_id=str(instance.id),
                    object_str=str(instance),
                    changes=changes
                )
                
                logger.info(f"Logged profile update for employee {instance.employee_id}: {changes}")
    
    except Exception as e:
        logger.error(f"Error logging employee profile changes: {str(e)}", exc_info=True)


@receiver(post_save, sender=LeaveRequest)
def log_leave_request_changes(sender, instance, created, **kwargs):
    """
    Signal handler to log changes to LeaveRequest.
    """
    if created:
        return  # Skip for new creates as they're handled in views
    
    try:
        # Log status changes
        old_instance = LeaveRequest.objects.filter(pk=instance.pk).values('status').first()
        
        if old_instance and old_instance['status'] != instance.status:
            AuditLog.objects.create(
                user=instance.approved_by,
                action='update',
                content_type='LeaveRequest',
                object_id=str(instance.id),
                object_str=str(instance),
                changes={'status': {'old': old_instance['status'], 'new': instance.status}}
            )
            
            logger.info(f"Logged leave request update: {instance.id} status changed to {instance.status}")
    
    except Exception as e:
        logger.error(f"Error logging leave request changes: {str(e)}", exc_info=True)
