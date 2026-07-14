from django.http import HttpResponseNotFound
from .models import HoneypotHit

PROBE_PATHS = [
    '.env',
    '.env.bak',
    '.git/config',
    'wp-login.php',
    'wp-admin/',
    'config.php.bak',
    'phpinfo.php',
    'xmlrpc.php',
    '.aws/credentials',
    'server-status',
    'debug.log',
]

class HoneypotProbeMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path.lstrip('/')

        if any(path.startswith(probe) for probe in PROBE_PATHS):
            HoneypotHit.objects.create(
                trigger_type='probe_path',
                path=request.path,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                extra_info=f"Method: {request.method}"
            )
            return HttpResponseNotFound()
        
        return self.get_response(request)