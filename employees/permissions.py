from rest_framework import permissions


class IsHRAdmin(permissions.BasePermission):
    """
    Permission to check if user is HR Admin.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_hr_admin


class IsManager(permissions.BasePermission):
    """
    Permission to check if user is Manager.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_manager


class IsHRAdminOrManager(permissions.BasePermission):
    """
    Permission to check if user is HR Admin or Manager.
    """
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated and 
                (request.user.is_hr_admin or request.user.is_manager))


class IsEmployee(permissions.BasePermission):
    """
    Permission to check if user has an employee profile.
    """
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated and 
                hasattr(request.user, 'profile'))


class IsOwnEmployeeProfileOrAdmin(permissions.BasePermission):
    """
    Permission to check if user is viewing/editing their own profile,
    is the employee's direct manager, or is an HR admin.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.is_hr_admin:
            return True
        if obj.user == request.user:
            return True
        if request.user.is_manager and obj.manager == request.user:
            return True
        return False


class CanApproveLeaves(permissions.BasePermission):
    """
    Permission to check if user can approve/reject leave requests.
    Only HR admins or the employee's manager can approve leaves.
    """
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated and 
                (request.user.is_hr_admin or request.user.is_manager))
    
    def has_object_permission(self, request, view, obj):
        # HR Admins can approve any leave
        if request.user.is_hr_admin:
            return True
        
        # Managers can only approve leaves from their subordinates
        if request.user.is_manager:
            return hasattr(request.user, 'subordinates') and \
                   obj.employee.manager == request.user
        
        return False


class IsEmployeeOrReadOnly(permissions.BasePermission):
    """
    Permission to check if user is authenticated to view, HR Admin/Manager to modify.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return request.user and request.user.is_authenticated and \
               (request.user.is_hr_admin or request.user.is_manager)


class CanDeleteEmployee(permissions.BasePermission):
    """
    Permission to check if user can delete employees.
    Only HR Admins can delete employees.
    """
    def has_permission(self, request, view):
        if request.method == 'DELETE':
            return request.user and request.user.is_authenticated and request.user.is_hr_admin
        return True
