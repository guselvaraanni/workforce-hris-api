"""Global template context for HRIS layout."""
from django.utils import timezone


def hris_layout(request):
    base = {'today_date': timezone.localdate()}
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return base

    user = request.user
    profile = getattr(user, 'profile', None)

    if user.is_hr_admin:
        role_label = 'HR Administrator'
    elif user.is_manager:
        role_label = 'People Manager'
    else:
        role_label = 'Employee'

    initials = ''
    if user.first_name:
        initials += user.first_name[0].upper()
    if user.last_name:
        initials += user.last_name[0].upper()
    if not initials and user.email:
        initials = user.email[0].upper()

    base.update({
        'layout_profile': profile,
        'layout_role_label': role_label,
        'layout_initials': initials,
        'layout_display_name': user.get_full_name() or user.email,
    })
    return base
