import logging
import json
from django.core.serializers.json import DjangoJSONEncoder
from ..models import AuditLog

logger = logging.getLogger('audit')


def get_client_ip(request):
    """
    Extract client IP address from request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_action(user, action, content_type, object_id, object_str, changes, request):
    """
    Create an audit log entry for a specific action.
    
    Args:
        user: User performing the action
        action: Action type (create, update, delete, approve, reject)
        content_type: Model name being audited
        object_id: ID of the object
        object_str: String representation of the object
        changes: Dictionary of changes made
        request: HTTP request object
    """
    try:
        audit_log = AuditLog.objects.create(
            user=user,
            action=action,
            content_type=content_type,
            object_id=str(object_id),
            object_str=object_str,
            changes=changes,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        
        logger.info(
            f"[{action.upper()}] {content_type}({object_id}) by {user.email} "
            f"from {get_client_ip(request)}"
        )
        
        return audit_log
    
    except Exception as e:
        logger.error(f"Error creating audit log: {str(e)}", exc_info=True)
        return None
