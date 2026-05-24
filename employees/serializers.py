from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import (
    CustomUser, Department, EmployeeProfile, LeaveRequest, AuditLog, BulkUploadJob
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom token serializer that includes user details in the response.
    """
    def validate(self, attrs):
        data = super().validate(attrs)
        data['user_id'] = str(self.user.id)
        data['email'] = self.user.email
        data['full_name'] = self.user.get_full_name()
        data['is_hr_admin'] = self.user.is_hr_admin
        data['is_manager'] = self.user.is_manager
        return data


class CustomUserSerializer(serializers.ModelSerializer):
    """
    Serializer for CustomUser model.
    """
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'phone_number',
                 'is_hr_admin', 'is_manager', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class CustomUserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new users with password validation.
    """
    password = serializers.CharField(write_only=True, required=True, 
                                    validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = CustomUser
        fields = ['email', 'username', 'first_name', 'last_name', 'password', 'password2',
                 'phone_number', 'is_hr_admin', 'is_manager']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2')
        user = CustomUser.objects.create_user(**validated_data)
        return user


class DepartmentSerializer(serializers.ModelSerializer):
    """
    Serializer for Department model.
    """
    head_name = serializers.CharField(source='head.get_full_name', read_only=True)
    employee_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'head', 'head_name', 'budget', 
                 'is_active', 'employee_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_employee_count(self, obj):
        return getattr(obj, 'active_employee_count', obj.employees.filter(employment_status='active').count())


class EmployeeProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for EmployeeProfile model with nested user data.
    """
    user = CustomUserSerializer(read_only=True)
    email = serializers.EmailField(source='user.email', required=False)
    first_name = serializers.CharField(source='user.first_name', required=False)
    last_name = serializers.CharField(source='user.last_name', required=False)
    phone_number = serializers.CharField(source='user.phone_number', allow_blank=True, required=False)
    department_name = serializers.CharField(source='department.name', read_only=True)
    manager_name = serializers.CharField(source='manager.get_full_name', read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'user', 'email', 'first_name', 'last_name', 'phone_number',
            'employee_id', 'department', 'department_name', 'manager', 
            'manager_name', 'date_of_birth', 'gender', 'address', 'city', 'country',
            'postal_code', 'employment_status', 'employment_type', 'salary', 'bonus',
            'date_of_joining', 'date_of_leaving', 'profile_picture', 'bio', 'skills',
            'full_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'date_of_joining']
    
    def validate_salary(self, value):
        if value < 0:
            raise serializers.ValidationError("Salary cannot be negative.")
        return value

    def update(self, instance, validated_data):
        user_data = validated_data.pop('user', {})
        for attr, value in user_data.items():
            setattr(instance.user, attr, value)
        if user_data:
            instance.user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeProfileCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new employee profiles with user creation.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, validators=[validate_password])
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    profile_picture = serializers.ImageField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = EmployeeProfile
        fields = [
            'email', 'password', 'first_name', 'last_name', 'employee_id', 'department',
            'manager', 'date_of_birth', 'gender', 'address', 'city', 'country',
            'postal_code', 'employment_status', 'employment_type', 'salary', 'bonus',
            'skills', 'profile_picture', 'bio'
        ]
    
    def create(self, validated_data):
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        profile_picture = validated_data.pop('profile_picture', None)
        
        user = CustomUser.objects.create_user(
            email=email,
            username=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        employee = EmployeeProfile.objects.create(user=user, **validated_data)
        if profile_picture is not None:
            employee.profile_picture = profile_picture
            employee.save()
        return employee


class LeaveRequestSerializer(serializers.ModelSerializer):
    """
    Serializer for LeaveRequest model.
    """
    employee = serializers.PrimaryKeyRelatedField(read_only=True)
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', 
                                            read_only=True)
    duration_days = serializers.ReadOnlyField()
    
    class Meta:
        model = LeaveRequest
        fields = [
            'id', 'employee', 'employee_name', 'start_date', 'end_date', 'leave_type',
            'reason', 'status', 'approved_by', 'approved_by_name', 'approval_date',
            'approval_notes', 'duration_days', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'employee', 'created_at', 'updated_at', 'approved_by', 
                           'approved_by_name', 'approval_date']
    
    def validate(self, attrs):
        request = self.context.get('request')
        employee = attrs.get('employee')
        if employee is None and request is not None and hasattr(request.user, 'profile'):
            employee = request.user.profile

        if employee is None:
            raise serializers.ValidationError(
                {'employee': 'Authenticated user must have an employee profile.'}
            )

        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError(
                {'dates': 'Start date must be before end date.'}
            )

        overlapping = LeaveRequest.objects.filter(
            employee=employee,
            start_date__lte=attrs['end_date'],
            end_date__gte=attrs['start_date'],
            status__in=['pending', 'approved']
        )

        if self.instance:
            overlapping = overlapping.exclude(id=self.instance.id)

        if overlapping.exists():
            raise serializers.ValidationError(
                {'dates': 'This leave period overlaps with existing leave request.'}
            )

        return attrs


class LeaveRequestApprovalSerializer(serializers.ModelSerializer):
    """
    Serializer for approving/rejecting leave requests with concurrency control.
    """
    class Meta:
        model = LeaveRequest
        fields = ['status', 'approval_notes']
    
    def validate_status(self, value):
        if value not in ['approved', 'rejected']:
            raise serializers.ValidationError(
                'Status must be either "approved" or "rejected".'
            )
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AuditLog model (read-only).
    """
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'timestamp', 'user', 'user_name', 'action', 'content_type',
            'object_id', 'object_str', 'changes', 'ip_address'
        ]
        # FIX: Explicitly list fields instead of '__all__'
        read_only_fields = [
            'id', 'timestamp', 'user', 'action', 'content_type',
            'object_id', 'object_str', 'changes', 'ip_address'
        ]


class BulkUploadJobSerializer(serializers.ModelSerializer):
    """
    Serializer for BulkUploadJob model.
    """
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', 
                                            read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    
    class Meta:
        model = BulkUploadJob
        fields = [
            'id', 'uploaded_by', 'uploaded_by_name', 'csv_file', 'status',
            'total_records', 'processed_records', 'successful_records', 'failed_records',
            'error_log', 'progress_percentage', 'started_at', 'completed_at', 'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'total_records', 'processed_records', 'successful_records',
            'failed_records', 'error_log', 'started_at', 'completed_at', 'created_at'
        ]


class BulkUploadJobDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for BulkUploadJob with error details.
    """
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name',
                                            read_only=True)
    progress_percentage = serializers.ReadOnlyField()
    processing_time = serializers.SerializerMethodField()
    
    class Meta:
        model = BulkUploadJob
        fields = [
            'id', 'uploaded_by', 'uploaded_by_name', 'csv_file', 'status',
            'total_records', 'processed_records', 'successful_records', 'failed_records',
            'error_log', 'progress_percentage', 'processing_time', 'started_at',
            'completed_at', 'created_at'
        ]
        # FIX: Explicitly list fields instead of '__all__'
        read_only_fields = [
            'id', 'uploaded_by', 'csv_file', 'status', 'total_records', 
            'processed_records', 'successful_records', 'failed_records',
            'error_log', 'started_at', 'completed_at', 'created_at'
        ]
    
    def get_processing_time(self, obj):
        if obj.started_at and obj.completed_at:
            delta = obj.completed_at - obj.started_at
            return str(delta)
        return None