from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from django.views.generic import TemplateView
from django.contrib.auth.views import LogoutView
from employees.views import CustomTokenObtainPairView, SessionLoginView
from employees.template_views import (
    DashboardView, EmployeeListView, EmployeeDetailView,
    EmployeeCreateView, EmployeeUpdateView, AuditLogTemplateView,
    UploadStatusView, LeaveListView, DepartmentListView
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ── API-driven frontend (SPA shell pages) ────────────────────────────
    path('', TemplateView.as_view(template_name='index.html'), name='home'),

    # ── Server-side rendered Django template views ────────────────────────
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('employees/', EmployeeListView.as_view(), name='employees'),
    path('employees/add/', EmployeeCreateView.as_view(), name='employee-add'),
    path('employees/<uuid:pk>/', EmployeeDetailView.as_view(), name='employee-detail'),
    path('employees/<uuid:pk>/edit/', EmployeeUpdateView.as_view(), name='employee-edit'),
    path('departments/', DepartmentListView.as_view(), name='departments'),
    path('leaves/', LeaveListView.as_view(), name='leaves'),
    path('uploads/', UploadStatusView.as_view(), name='uploads'),
    path('audit/', AuditLogTemplateView.as_view(), name='audit'),

    # ── Session login for template UI ─────────────────────────────────────────
    path('login/', SessionLoginView.as_view(), name='session_login'),

    # ── API Auth ──────────────────────────────────────────────────────────
    path('api/v1/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),

    # ── API Schema & Docs ─────────────────────────────────────────────────
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # ── App API URLs ──────────────────────────────────────────────────────
    path('api/v1/', include('employees.urls')),
]

if settings.DEBUG:
    urlpatterns += [path('__debug__/', include('debug_toolbar.urls'))]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
