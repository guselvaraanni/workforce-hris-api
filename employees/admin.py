from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    CustomUser, Department, EmployeeProfile, LeaveRequest, AuditLog, BulkUploadJob
)


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """
    Admin interface for CustomUser model.
    """
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('phone_number', 'is_hr_admin', 'is_manager')}),
    )
    list_display = ('email', 'first_name', 'last_name', 'is_hr_admin', 'is_manager', 'is_active')
    list_filter = ('is_hr_admin', 'is_manager', 'is_active', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Admin interface for Department model.
    """
    list_display = ('name', 'head', 'budget', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {'fields': ('id', 'name', 'description')}),
        ('Management', {'fields': ('head', 'budget')}),
        ('Status', {'fields': ('is_active',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for EmployeeProfile model.
    """
    list_display = ('employee_id', 'get_full_name', 'department', 'employment_status', 
                   'salary', 'date_of_joining')
    list_filter = ('employment_status', 'employment_type', 'department', 'date_of_joining')
    search_fields = ('employee_id', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('id', 'user', 'date_of_joining', 'created_at', 'updated_at')
    
    fieldsets = (
        ('User Information', {'fields': ('id', 'user')}),
        ('Employment Details', {
            'fields': ('employee_id', 'department', 'manager', 'employment_status', 'employment_type')
        }),
        ('Personal Information', {
            'fields': ('date_of_birth', 'gender', 'address', 'city', 'country', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Financial', {
            'fields': ('salary', 'bonus')
        }),
        ('Dates', {
            'fields': ('date_of_joining', 'date_of_leaving')
        }),
        ('Profile', {
            'fields': ('profile_picture', 'bio', 'skills'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'Full Name'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    """
    Admin interface for LeaveRequest model.
    """
    list_display = ('id', 'get_employee_name', 'start_date', 'end_date', 'leave_type', 
                   'status', 'approved_by')
    list_filter = ('status', 'leave_type', 'start_date', 'created_at')
    search_fields = ('employee__user__email', 'employee__user__first_name', 'reason')
    readonly_fields = ('id', 'created_at', 'updated_at', 'version')
    
    fieldsets = (
        ('Request Details', {'fields': ('id', 'employee', 'leave_type', 'reason')}),
        ('Dates', {'fields': ('start_date', 'end_date')}),
        ('Approval', {
            'fields': ('status', 'approved_by', 'approval_date', 'approval_notes')
        }),
        ('Concurrency', {'fields': ('version',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def get_employee_name(self, obj):
        return obj.employee.get_full_name()
    get_employee_name.short_description = 'Employee'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin interface for AuditLog model (read-only).
    """
    list_display = ('timestamp', 'get_user', 'action', 'content_type', 'object_str')
    list_filter = ('action', 'timestamp', 'content_type')
    search_fields = ('object_id', 'user__email', 'content_type')
    readonly_fields = ('id', 'timestamp', 'user', 'action', 'content_type', 'object_id',
                      'object_str', 'changes', 'ip_address', 'user_agent')
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_user(self, obj):
        return obj.user.email if obj.user else 'System'
    get_user.short_description = 'User'


@admin.register(BulkUploadJob)
class BulkUploadJobAdmin(admin.ModelAdmin):
    """
    Admin interface for BulkUploadJob model.
    """
    list_display = ('id', 'uploaded_by', 'status', 'progress_percentage', 
                   'successful_records', 'failed_records', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('uploaded_by__email', 'id')
    readonly_fields = ('id', 'created_at', 'started_at', 'completed_at', 'thread_id',
                      'progress_percentage')
    
    fieldsets = (
        ('Upload Information', {'fields': ('id', 'uploaded_by', 'csv_file')}),
        ('Status', {'fields': ('status', 'progress_percentage')}),
        ('Processing Details', {
            'fields': ('total_records', 'processed_records', 'successful_records', 'failed_records')
        }),
        ('Errors', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Thread Info', {
            'fields': ('thread_id',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
