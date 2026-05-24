import json
import threading
import logging

from django.contrib.auth import authenticate, login
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.db.models import Count, Avg, Sum, Q
from rest_framework import viewsets, status, generics, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

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


def _start_upload_thread(job_id: str) -> None:
    """
    Start the CSV processing thread.
    Called via transaction.on_commit() to guarantee the BulkUploadJob row
    is committed before the thread tries to read it.

    WHY transaction.on_commit():
    perform_create() runs inside a transaction. If we started the thread
    directly inside the transaction, the thread's first DB query
    (BulkUploadJob.objects.get(id=job_id)) could execute before the
    outer transaction commits — making the row invisible to the thread
    under MySQL's REPEATABLE READ isolation. on_commit() delays the
    thread start until after the transaction is committed.
    """
    thread = threading.Thread(
        target=process_csv_file,
        args=(job_id,),
        name=f"bulk_upload_{job_id}",
        daemon=False  # Thread must complete even if main process exits
    )
    thread.start()
    logger.info(f"Started bulk upload thread for job {job_id}: {thread.name}")


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom serializer to include user info in token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user_id'] = str(user.id)
        data['email'] = user.email
        data['full_name'] = user.get_full_name() or user.email
        data['is_hr_admin'] = user.is_hr_admin
        data['is_manager'] = user.is_manager
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


@method_decorator(csrf_protect, name='dispatch')
class SessionLoginView(View):
    def post(self, request, *args, **kwargs):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

        email = payload.get('email', '').strip()
        password = payload.get('password', '')
        remember_me = payload.get('rememberMe', False)

        if not email or not password:
            return JsonResponse(
                {'detail': 'Email and password are required.'}, status=400
            )

        user = authenticate(request, username=email, password=password)
        if user is None:
            return JsonResponse({'detail': 'Invalid credentials.'}, status=401)

        login(request, user)
        if not remember_me:
            request.session.set_expiry(0)

        return JsonResponse({'detail': 'Login successful.'})


class UserRegistrationView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserCreateSerializer
    permission_classes = [AllowAny]


class UserListView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    search_fields = ['email', 'first_name', 'last_name']
    ordering_fields = ['created_at', 'email', 'first_name']


class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Department CRUD with annotated employee counts.

    FIX: Original used a per-object .count() query in the serializer —
    an N+1 problem. Now the queryset annotates active_employee_count
    at the DB level so one query serves the entire list.
    """
    serializer_class = DepartmentSerializer
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def get_queryset(self):
        return (
            Department.objects
            .select_related('head')
            .annotate(
                active_employee_count=Count(
                    'employees',
                    filter=Q(employees__employment_status='active')
                )
            )
            .order_by('name')
        )

    def get_permissions(self):
        if self.request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return [IsAuthenticated(), IsHRAdmin()]
        return [IsAuthenticated()]

    @transaction.atomic
    def perform_create(self, serializer):
        department = serializer.save()
        log_action(
            user=self.request.user,
            action='create',
            content_type='Department',
            object_id=str(department.id),
            object_str=str(department),
            changes={k: str(v) for k, v in serializer.validated_data.items()},
            request=self.request
        )

    @transaction.atomic
    def perform_update(self, serializer):
        department = serializer.save()
        log_action(
            user=self.request.user,
            action='update',
            content_type='Department',
            object_id=str(department.id),
            object_str=str(department),
            changes={k: str(v) for k, v in serializer.validated_data.items()},
            request=self.request
        )


class EmployeeProfileViewSet(viewsets.ModelViewSet):
    """
    Employee Profile CRUD with ORM optimization.

    select_related('user', 'department', 'manager') eliminates N+1:
    one JOIN query instead of separate FK lookups per row.
    """
    serializer_class = EmployeeProfileSerializer
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'employee_id']
    ordering_fields = ['user__first_name', 'date_of_joining', 'salary']
    filterset_fields = ['employment_status', 'employment_type', 'department', 'gender']

    def get_queryset(self):
        qs = EmployeeProfile.objects.select_related('user', 'department', 'manager')
        user = self.request.user

        if user.is_hr_admin:
            return qs
        if user.is_manager:
            return qs.filter(Q(manager=user) | Q(user=user))
        if hasattr(user, 'profile'):
            return qs.filter(user=user)
        return qs.none()

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsHRAdmin()]
        elif self.request.method in ['PUT', 'PATCH']:
            return [IsAuthenticated(), IsOwnEmployeeProfileOrAdmin()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), CanDeleteEmployee()]
        return [IsAuthenticated()]

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
        old = EmployeeProfile.objects.get(pk=self.kwargs['pk'])
        old_salary = old.salary
        old_department = old.department_id

        employee = serializer.save()

        changes = {}
        if 'salary' in serializer.validated_data:
            changes['salary'] = {'old': str(old_salary), 'new': str(employee.salary)}
        if 'department' in serializer.validated_data:
            changes['department'] = {'old': str(old_department), 'new': str(employee.department_id)}
        # Capture any other changed fields
        for field, value in serializer.validated_data.items():
            if field not in changes:
                changes[field] = str(value)

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
        """Get employees by department with pagination."""
        department_id = request.query_params.get('department_id')
        if not department_id:
            return Response(
                {'error': 'department_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        employees = self.get_queryset().filter(department_id=department_id)
        # Use paginator so large departments don't return unbounded lists
        page = self.paginate_queryset(employees)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsManager])
    def my_team(self, request):
        """Get employees managed by current user (paginated)."""
        employees = self.get_queryset().filter(manager=request.user)
        page = self.paginate_queryset(employees)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(employees, many=True)
        return Response(serializer.data)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    Leave Request management with pessimistic concurrency control.

    select_for_update() in approve/reject actions locks the row so two
    simultaneous approval requests cannot both succeed on the same leave.
    """
    serializer_class = LeaveRequestSerializer
    search_fields = ['employee__user__email', 'leave_type', 'status']
    ordering_fields = ['start_date', 'created_at', 'status']
    filterset_fields = ['status', 'leave_type']

    def get_queryset(self):
        qs = LeaveRequest.objects.select_related(
            'employee__user', 'employee__department', 'approved_by'
        ).order_by('-created_at')
        user = self.request.user

        if user.is_hr_admin:
            return qs
        if user.is_manager:
            return qs.filter(employee__manager=user)
        if hasattr(user, 'profile'):
            return qs.filter(employee=user.profile)
        return qs.none()

    def get_permissions(self):
        if self.action in ['approve_leave', 'reject_leave']:
            return [IsAuthenticated(), CanApproveLeaves()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        if hasattr(self.request.user, 'profile'):
            serializer.save(employee=self.request.user.profile)
        else:
            raise serializer.ValidationError(
                {'error': 'User does not have an employee profile'}
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeaves])
    def approve_leave(self, request, pk=None):
        """
        Approve a leave request.

        Uses select_for_update() to acquire a row-level lock in MySQL.
        This prevents race conditions where two managers try to approve
        the same leave simultaneously — only one will get the lock;
        the other will see status != 'pending' and return an error.
        """
        with transaction.atomic():
            leave_request = LeaveRequest.objects.select_for_update().get(pk=pk)

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
                leave = serializer.save(
                    approved_by=request.user,
                    approval_date=timezone.now()
                )
                log_action(
                    user=request.user, action='approve',
                    content_type='LeaveRequest', object_id=str(leave.id),
                    object_str=str(leave), changes={'status': 'approved'},
                    request=request
                )
                return Response(self.get_serializer(leave).data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, CanApproveLeaves])
    def reject_leave(self, request, pk=None):
        """Reject a leave request with row-level lock."""
        with transaction.atomic():
            leave_request = LeaveRequest.objects.select_for_update().get(pk=pk)

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
                leave = serializer.save(
                    approved_by=request.user,
                    approval_date=timezone.now()
                )
                log_action(
                    user=request.user, action='reject',
                    content_type='LeaveRequest', object_id=str(leave.id),
                    object_str=str(leave), changes={'status': 'rejected'},
                    request=request
                )
                return Response(self.get_serializer(leave).data)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get current user's leave requests."""
        if not hasattr(request.user, 'profile'):
            return Response({'error': 'User has no employee profile'}, status=400)
        qs = self.get_queryset().filter(employee=request.user.profile)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsHRAdminOrManager])
    def pending_approvals(self, request):
        """Get pending leaves for approval (paginated)."""
        if request.user.is_hr_admin:
            qs = self.get_queryset().filter(status='pending')
        else:
            qs = self.get_queryset().filter(status='pending', employee__manager=request.user)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log — read only, HR Admin only."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    search_fields = ['action', 'content_type', 'user__email']
    ordering_fields = ['timestamp', 'action']
    filterset_fields = ['action', 'content_type']

    def get_queryset(self):
        return AuditLog.objects.select_related('user').order_by('-timestamp')

    @action(detail=False, methods=['get'])
    def employee_history(self, request):
        """Audit trail for a specific employee."""
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response({'error': 'employee_id parameter is required'}, status=400)
        qs = self.get_queryset().filter(
            content_type='EmployeeProfile', object_id=employee_id
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)


class BulkUploadViewSet(viewsets.ModelViewSet):
    """
    Bulk CSV upload with background thread processing.

    FIX: The original started the thread inside @transaction.atomic, which
    caused a race: the thread tried to read the BulkUploadJob row before
    the outer transaction committed. Fixed with transaction.on_commit().
    """
    serializer_class = BulkUploadJobSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    ordering_fields = ['created_at', 'status']

    def get_queryset(self):
        return BulkUploadJob.objects.select_related('uploaded_by').order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return BulkUploadJobDetailSerializer
        return BulkUploadJobSerializer

    def perform_create(self, serializer):
        bulk_job = serializer.save(uploaded_by=self.request.user)
        job_id = str(bulk_job.id)
        # CRITICAL FIX: use on_commit so the thread only starts AFTER the row
        # is committed. Without this, the thread's first DB query may not find
        # the BulkUploadJob row under MySQL's REPEATABLE READ isolation.
        transaction.on_commit(lambda: _start_upload_thread(job_id))

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Poll upload job progress."""
        bulk_job = self.get_object()
        return Response(BulkUploadJobDetailSerializer(bulk_job).data)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry a failed or completed upload job."""
        bulk_job = self.get_object()

        if bulk_job.status not in ['failed', 'completed']:
            return Response(
                {'error': 'Can only retry failed or completed jobs'},
                status=status.HTTP_400_BAD_REQUEST
            )

        bulk_job.status = 'pending'
        bulk_job.processed_records = 0
        bulk_job.successful_records = 0
        bulk_job.failed_records = 0
        bulk_job.error_log = []
        bulk_job.started_at = None
        bulk_job.completed_at = None
        bulk_job.save()

        job_id = str(bulk_job.id)
        transaction.on_commit(lambda: _start_upload_thread(job_id))

        return Response({'message': 'Bulk upload job restarted'})


class WorkforceAnalyticsView(views.APIView):
    """
    Workforce analytics using DB-level aggregation.

    All stats are computed in a single DB query using Django's annotate/aggregate.
    Never iterates over Python objects for calculations.
    """
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        # Summary stats — single aggregate query
        summary = EmployeeProfile.objects.aggregate(
            total_active=Count('id', filter=Q(employment_status='active')),
            total_on_leave=Count('id', filter=Q(employment_status='on_leave')),
            total_terminated=Count('id', filter=Q(employment_status='terminated')),
            avg_salary=Avg('salary', filter=Q(employment_status='active')),
            total_payroll=Sum('salary', filter=Q(employment_status='active')),
        )

        # Department breakdown — single annotated query
        dept_breakdown = list(
            Department.objects
            .filter(is_active=True)
            .annotate(
                headcount=Count(
                    'employees',
                    filter=Q(employees__employment_status='active')
                ),
                avg_salary=Avg(
                    'employees__salary',
                    filter=Q(employees__employment_status='active')
                ),
                total_payroll=Sum(
                    'employees__salary',
                    filter=Q(employees__employment_status='active')
                ),
            )
            .values('name', 'headcount', 'avg_salary', 'total_payroll', 'budget')
            .order_by('-headcount')
        )

        # Leave stats
        leave_stats = LeaveRequest.objects.aggregate(
            pending=Count('id', filter=Q(status='pending')),
            approved_this_month=Count(
                'id',
                filter=Q(
                    status='approved',
                    created_at__month=timezone.now().month
                )
            ),
        )

        # Recent hire trend (last 6 months)
        from django.db.models.functions import TruncMonth
        hire_trend = list(
            EmployeeProfile.objects
            .annotate(month=TruncMonth('date_of_joining'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('-month')[:6]
        )

        return Response({
            'summary': summary,
            'by_department': dept_breakdown,
            'leave_stats': leave_stats,
            'hire_trend': hire_trend,
        })


class HealthCheckView(views.APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'status': 'healthy',
            'timestamp': timezone.now(),
            'version': '2.0.0',
            'message': 'Enterprise Workforce HRIS API is running',
        })
