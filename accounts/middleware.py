from django.utils.cache import patch_cache_control, patch_vary_headers
from django.conf import settings


class PrivateAPIResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            patch_cache_control(response, private=True, no_store=True, no_cache=True, max_age=0)
            patch_vary_headers(response, ("Cookie",))
        if settings.DJANGO_ENV == "production":
            response["Content-Security-Policy-Report-Only"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; media-src 'self'; connect-src 'self'; "
                "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
            )
        return response
