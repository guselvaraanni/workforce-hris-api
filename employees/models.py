from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, EmailValidator
from django.utils import timezone
import uuid
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUser(AbstractUser):
    """
    Custom User Model extending Django's AbstractUser.
    Provides foundation for authentication across the system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, validators=[EmailValidator()])
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    is_hr_admin = models.BooleanField(default=False)
    is_manager = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'Custom User'
        verbose_name_plural = 'Custom Users'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['is_hr_admin']),
            models.Index(fields=['is_manager']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def has_profile(self):
        return hasattr(self, 'profile')


class Department(models.Model):
    """
    Department model for organizing employees.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    head = models.OneToOneField(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                               related_name='managed_department')
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0, 
                                validators=[MinValueValidator(0)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return self.name


def generate_employee_id(user):
    """Generate a safe employee_id that fits the 20-character field."""
    return f"EMP-{user.id.hex[:12]}"


class EmployeeProfile(models.Model):
    """
    Employee Profile model with complete employee information.
    Uses OneToOneField relationship with CustomUser.
    """
    EMPLOYMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('terminated', 'Terminated'),
    ]
    
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('intern', 'Intern'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='employees')
    manager = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='subordinates')
    
    # Personal Information
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
                             blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    
    # Employment Information
    employee_id = models.CharField(max_length=20, unique=True)
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, 
                                        default='active')
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, 
                                      default='full_time')
    
    # Financial Information
    salary = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0, 
                               validators=[MinValueValidator(0)])
    
    # Dates
    date_of_joining = models.DateField(auto_now_add=True)
    date_of_leaving = models.DateField(null=True, blank=True)
    
    # Profile
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    bio = models.TextField(blank=True)
    skills = models.CharField(max_length=500, blank=True, help_text='Comma-separated skills')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Employee Profile'
        verbose_name_plural = 'Employee Profiles'
        ordering = ['user__first_name', 'user__last_name']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['employment_status']),
            models.Index(fields=['department']),
            models.Index(fields=['manager']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"
    
    def get_full_name(self):
        return self.user.get_full_name()
    
    @receiver(post_save, sender=CustomUser)
    def create_employee_profile(sender, instance, created, **kwargs):
        if created and not instance.is_superuser:
            # Automatically create profile for new users
            EmployeeProfile.objects.create(
                user=instance,
                employee_id=generate_employee_id(instance),
                salary=0
            )


class LeaveRequest(models.Model):
    """
    Leave Request model for managing employee time off.
    Implements concurrency control with database locking.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    
    LEAVE_TYPE_CHOICES = [
        ('annual', 'Annual'),
        ('sick', 'Sick'),
        ('personal', 'Personal'),
        ('maternity', 'Maternity'),
        ('paternity', 'Paternity'),
        ('unpaid', 'Unpaid'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name='leave_requests')
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE_CHOICES, default='annual')
    reason = models.TextField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_leave_requests')
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Concurrency Control
    version = models.IntegerField(default=0, help_text='Version number for optimistic locking')
    
    class Meta:
        verbose_name = 'Leave Request'
        verbose_name_plural = 'Leave Requests'
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.start_date} to {self.end_date}"
    
    @property
    def duration_days(self):
        """Calculate number of days for this leave request"""
        return (self.end_date - self.start_date).days + 1
    
    def is_overlapping(self, other_request):
        """Check if this request overlaps with another"""
        return (self.start_date <= other_request.end_date and 
                self.end_date >= other_request.start_date)


class AuditLog(models.Model):
    """
    Audit Log model for tracking all changes to employee data.
    Implements the Observer pattern via Django Signals.
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    # Object Information
    content_type = models.CharField(max_length=100, help_text='Model name being audited')
    object_id = models.CharField(max_length=100, db_index=True)
    object_str = models.CharField(max_length=255)
    
    # Change Details
    changes = models.JSONField(default=dict, help_text='Dictionary of field changes')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['object_id']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.action.upper()} - {self.content_type} ({self.object_id}) at {self.timestamp}"


class BulkUploadJob(models.Model):
    """
    Bulk Upload Job model for tracking CSV file processing.
    Supports asynchronous processing with threading.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True,
                                   related_name='bulk_upload_jobs')
    csv_file = models.FileField(upload_to='bulk_uploads/')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_records = models.IntegerField(default=0)
    processed_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    
    error_log = models.JSONField(default=list, help_text='List of errors encountered')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    thread_id = models.CharField(max_length=100, blank=True, help_text='ID of processing thread')

    @property
    def progress_percentage(self):
        if not self.total_records:
            return 0
        return int((self.processed_records / self.total_records) * 100)
    
    class Meta:
        verbose_name = 'Bulk Upload Job'
        verbose_name_plural = 'Bulk Upload Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['uploaded_by']),
        ]
    
    def __str__(self):
        return f"Bulk Upload - {self.id} ({self.status})"
    
    @property
    def progress_percentage(self):
        """Calculate upload progress percentage"""
        if self.total_records == 0:
            return 0
        return (self.processed_records / self.total_records) * 100
