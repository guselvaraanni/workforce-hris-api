from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from django.views.generic import TemplateView
from employees.views import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Frontend pages
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
    path('employees/', TemplateView.as_view(template_name='employees.html'), name='employees'),
    path('departments/', TemplateView.as_view(template_name='departments.html'), name='departments'),
    path('leaves/', TemplateView.as_view(template_name='leaves.html'), name='leaves'),
    path('uploads/', TemplateView.as_view(template_name='uploads.html'), name='uploads'),
    path('audit/', TemplateView.as_view(template_name='audit.html'), name='audit'),

    # API Authentication
    path('api/v1/auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/v1/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # API Schema & Documentation
    path('api/v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # App URLs
    path('api/v1/', include('employees.urls')),
]

# Debug toolbar
if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]

# Media and Static Files
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
