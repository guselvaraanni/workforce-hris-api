"""
Redirect browser HTML navigation away from raw DRF API URLs to HRIS UI pages.
"""
import re

from django.shortcuts import redirect

_EMPLOYEE_API = re.compile(
    r'^/api/v1/employees/(?P<pk>[0-9a-f-]{36})/?$', re.I
)
_EMPLOYEE_EDIT_API = re.compile(
    r'^/api/v1/employees/(?P<pk>[0-9a-f-]{36})/edit/?$', re.I
)
_SKIP_PREFIXES = (
    '/api/v1/docs/',
    '/api/v1/schema/',
    '/api/v1/auth/',
    '/api/v1/health/',
)


class ApiBrowserRedirectMiddleware:
    """
    If a logged-in user opens an API URL in the browser (Accept: text/html),
    send them to the matching server-rendered page instead of DRF browsable API.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.method == 'GET'
            and request.user.is_authenticated
            and request.path.startswith('/api/v1/')
            and not any(request.path.startswith(p) for p in _SKIP_PREFIXES)
            and self._wants_html(request)
        ):
            redirect_to = self._ui_redirect(request.path)
            if redirect_to:
                return redirect(redirect_to)

        return self.get_response(request)

    @staticmethod
    def _wants_html(request):
        accept = request.META.get('HTTP_ACCEPT', '')
        # Browsers send text/html; fetch/XHR from our UI sends application/json
        if 'application/json' in accept and 'text/html' not in accept:
            return False
        return 'text/html' in accept or '*/*' in accept

    @staticmethod
    def _ui_redirect(path):
        m = _EMPLOYEE_API.match(path)
        if m:
            return f'/employees/{m.group("pk")}/'
        if path.rstrip('/') == '/api/v1/employees':
            return '/employees/'
        if path.startswith('/api/v1/leave-requests'):
            return '/leaves/'
        if path.startswith('/api/v1/departments'):
            return '/departments/'
        if path.startswith('/api/v1/audit-logs'):
            return '/audit/'
        if path.startswith('/api/v1/bulk-uploads'):
            return '/uploads/'
        if path.startswith('/api/v1/attendance'):
            return '/dashboard/'
        return None
