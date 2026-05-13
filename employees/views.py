from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
import threading
import logging

from .models import (
    CustomUser, Department, EmployeeProfile, LeaveRequest, AuditLog, BulkUploadJob
)
from .serializers import (
    CustomUserSerializer, CustomUserCreateSerializer, DepartmentSerializer,
    EmployeeProfileSerializer, EmployeeProfileCreateSerializer,
    LeaveRequestSerializer, LeaveRequestApprovalSerializer, AuditLogSerializer,
    BulkUploadJobSerializer, BulkUploadJobDetailSerializer
)
from .permissions import (
    IsHRAdmin, IsManager, IsHRAdminOrManager, IsEmployee,
    IsOwnEmployeeProfileOrAdmin, CanApproveLeaves, CanDeleteEmployee
)
from .utils.csv_processor import process_csv_file
from .utils.audit import log_action
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

logger = logging.getLogger(__name__)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer to include user info in token response"""

    def validate(self, attrs):
        data = super().validate(attrs)

        # Add user info to response
        user = self.user
        data['user_id'] = user.id
        data['email'] = user.email
        data['full_name'] = user.get_full_name() or user.email
        data['is_hr_admin'] = user.is_hr_admin
        data['is_manager'] = user.is_manager

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view with CORS and user info"""
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class UserRegistrationView(generics.CreateAPIView):
    """
    Endpoint for user registration.
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserCreateSerializer
    permission_classes = [AllowAny]


class UserListView(generics.ListAPIView):
    """
    List all users (HR Admin only).
    """
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['created_at', 'email', 'first_name']


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Department CRUD operations.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    
    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            permission_classes = [IsAuthenticated, IsHRAdmin]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @transaction.atomic
    def perform_create(self, serializer):
        department = serializer.save()
        log_action(
            user=self.request.user,
            action='create',
            content_type='Department',
            object_id=str(department.id),
            object_str=str(department),
            changes=serializer.validated_data,
            request=self.request
        )
    
    @transaction.atomic
    def perform_update(self, serializer):
        old_instance = Department.objects.get(pk=self.kwargs['pk'])
        department = serializer.save()
        changes = serializer.validated_data
        log_action(
            user=self.request.user,
            action='update',
            content_type='Department',
            object_id=str(department.id),
            object_str=str(department),
            changes=changes,
            request=self.request
        )


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Employee Profile CRUD operations.
    Implements ORM optimization with select_related and prefetch_related.
    """
    queryset = EmployeeProfile.objects.select_related('user', 'department', 'manager')
    serializer_class = EmployeeProfileSerializer
    permission_classes = [IsAuthenticated, IsOwnEmployeeProfileOrAdmin]
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'employee_id']
    ordering_fields = ['user__first_name', 'date_of_joining', 'salary']
    
    def get_permissions(self):
        if self.request.method in ['POST']:
            permission_classes = [IsAuthenticated, IsHRAdmin]
        elif self.request.method in ['PUT', 'PATCH']:
            permission_classes = [IsAuthenticated, IsOwnEmployeeProfileOrAdmin]
        elif self.request.method in ['DELETE']:
            permission_classes = [IsAuthenticated, CanDeleteEmployee]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return EmployeeProfileCreateSerializer
        return EmployeeProfileSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        employee = serializer.save()
        log_action(
            user=self.request.user,
            action='create',
            content_type='EmployeeProfile',
            object_id=str(employee.id),
            object_str=str(employee),
            changes={'employee_id': employee.employee_id, 'salary': str(employee.salary)},
            request=self.request
        )
    
    @transaction.atomic
    def perform_update(self, serializer):
        old_instance = EmployeeProfile.objects.get(pk=self.kwargs['pk'])
        old_salary = old_instance.salary
        old_department = old_instance.department_id
        
        employee = serializer.save()
        
        changes = serializer.validated_data.copy()
        if 'salary' in changes:
            changes['salary'] = {'old': str(old_salary), 'new': str(employee.salary)}
        if 'department' in changes:
            changes['department'] = {'old': str(old_department), 'new': str(employee.department_id)}
        
        log_action(
            user=self.request.user,
            action='update',
            content_type='EmployeeProfile',
            object_id=str(employee.id),
            object_str=str(employee),
            changes=changes,
            request=self.request
        )
    
    @transaction.atomic
    def perform_destroy(self, instance):
        log_action(
            user=self.request.user,
            action='delete',
            content_type='EmployeeProfile',
            object_id=str(instance.id),
            object_str=str(instance),
            changes={},
            request=self.request
        )
        instance.delete()
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsHRAdmin])
    def by_department(self, request):
        """Get employees by department"""
        department_id = request.query_params.get('department_id')
        if not department_id:
            return Response(
                {'error': 'department_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        employees = self.queryset.filter(department_id=department_id)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsManager])
    def my_team(self, request):
        """Get employees managed by current user"""
        employees = self.queryset.filter(manager=request.user)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Leave Request management with concurrency control.
    """
    queryset = LeaveRequest.objects.select_related('employee', 'approved_by')
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['employee__user__email', 'leave_type', 'status']
    ordering_fields = ['start_date', 'created_at', 'status']
    
    def get_permissions(self):
        if self.action in ['approve_leave', 'reject_leave']:
            permission_classes = [IsAuthenticated, CanApproveLeaves]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        # Associate the leave request with the current user's employee profile
        if hasattr(self.request.user, 'profile'):
            serializer.save(employee=self.request.user.profile)
        else:
            return Response(
                {'error': 'User does not have an employee profile'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeaves])
    def approve_leave(self, request, pk=None):
        """
        Approve a leave request with database locking to prevent race conditions.
        """
        leave_request = self.get_object()
        
        # Acquire lock to prevent concurrent modifications
        with transaction.atomic():
            leave_request = LeaveRequest.objects.select_for_update().get(pk=leave_request.id)
            
            if leave_request.status != 'pending':
                return Response(
                    {'error': f'Cannot approve a {leave_request.status} leave request'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = LeaveRequestApprovalSerializer(
                leave_request,
                data={'status': 'approved', 'approval_notes': request.data.get('approval_notes', '')},
                partial=True
            )
            
            if serializer.is_valid():
                leave_request = serializer.save(
                    approved_by=request.user,
                    approval_date=timezone.now()
                )
                
                log_action(
                    user=request.user,
                    action='approve',
                    content_type='LeaveRequest',
                    object_id=str(leave_request.id),
                    object_str=str(leave_request),
                    changes={'status': 'approved'},
                    request=request
                )
                
                return Response(
                    self.get_serializer(leave_request).data,
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @transaction.atomic
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeaves])
    def reject_leave(self, request, pk=None):
        """
        Reject a leave request with database locking.
        """
        leave_request = self.get_object()
        
        with transaction.atomic():
            leave_request = LeaveRequest.objects.select_for_update().get(pk=leave_request.id)
            
            if leave_request.status != 'pending':
                return Response(
                    {'error': f'Cannot reject a {leave_request.status} leave request'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            serializer = LeaveRequestApprovalSerializer(
                leave_request,
                data={'status': 'rejected', 'approval_notes': request.data.get('approval_notes', '')},
                partial=True
            )
            
            if serializer.is_valid():
                leave_request = serializer.save(
                    approved_by=request.user,
                    approval_date=timezone.now()
                )
                
                log_action(
                    user=request.user,
                    action='reject',
                    content_type='LeaveRequest',
                    object_id=str(leave_request.id),
                    object_str=str(leave_request),
                    changes={'status': 'rejected'},
                    request=request
                )
                
                return Response(
                    self.get_serializer(leave_request).data,
                    status=status.HTTP_200_OK
                )
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_requests(self, request):
        """Get current user's leave requests"""
        if not hasattr(request.user, 'profile'):
            return Response(
                {'error': 'User does not have an employee profile'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        leave_requests = self.queryset.filter(employee=request.user.profile)
        serializer = self.get_serializer(leave_requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsHRAdminOrManager])
    def pending_approvals(self, request):
        """Get pending leave requests for approval"""
        if request.user.is_hr_admin:
            leave_requests = self.queryset.filter(status='pending')
        else:
            # Manager sees leaves from their subordinates
            leave_requests = self.queryset.filter(
                status='pending',
                employee__manager=request.user
            )
        
        serializer = self.get_serializer(leave_requests, many=True)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing audit logs (read-only).
    """
    queryset = AuditLog.objects.select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    search_fields = ['action', 'content_type', 'user__email']
    ordering_fields = ['timestamp', 'action']
    
    @action(detail=False, methods=['get'])
    def employee_history(self, request):
        """Get audit history for a specific employee"""
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response(
                {'error': 'employee_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logs = self.queryset.filter(
            content_type='EmployeeProfile',
            object_id=employee_id
        )
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)


class BulkUploadViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bulk employee upload with asynchronous processing.
    """
    queryset = BulkUploadJob.objects.all()
    serializer_class = BulkUploadJobSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    ordering_fields = ['created_at', 'status']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BulkUploadJobDetailSerializer
        return BulkUploadJobSerializer
    
    @transaction.atomic
    def perform_create(self, serializer):
        bulk_job = serializer.save(uploaded_by=self.request.user)
        
        # Start async processing in a separate thread
        thread = threading.Thread(
            target=process_csv_file,
            args=(bulk_job.id,),
            name=f"bulk_upload_{bulk_job.id}"
        )
        thread.daemon = False
        thread.start()
        
        logger.info(f"Started bulk upload processing for job {bulk_job.id} in thread {thread.name}")
    
    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get current status and progress of bulk upload job"""
        bulk_job = self.get_object()
        serializer = BulkUploadJobDetailSerializer(bulk_job)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsHRAdmin])
    def retry(self, request, pk=None):
        """Retry a failed bulk upload job"""
        bulk_job = self.get_object()
        
        if bulk_job.status not in ['failed', 'completed']:
            return Response(
                {'error': 'Can only retry failed or completed jobs'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset job status
        bulk_job.status = 'pending'
        bulk_job.processed_records = 0
        bulk_job.successful_records = 0
        bulk_job.failed_records = 0
        bulk_job.error_log = []
        bulk_job.started_at = None
        bulk_job.completed_at = None
        bulk_job.save()
        
        # Restart processing
        thread = threading.Thread(
            target=process_csv_file,
            args=(bulk_job.id,),
            name=f"bulk_upload_retry_{bulk_job.id}"
        )
        thread.daemon = False
        thread.start()
        
        logger.info(f"Restarted bulk upload processing for job {bulk_job.id}")
        
        return Response(
            {'message': 'Bulk upload job restarted'},
            status=status.HTTP_200_OK
        )


class HealthCheckView(views.APIView):
    """
    Simple health check endpoint.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        return Response(
            {
                'status': 'healthy',
                'timestamp': timezone.now(),
                'message': 'Employee Management System API is running'
            },
            status=status.HTTP_200_OK
        )
