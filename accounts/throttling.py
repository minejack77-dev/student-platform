import hashlib
import time
import unicodedata

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


class SecurityThrottle(BaseThrottle):
    """Atomic fixed-window counters backed by shared Redis in production."""
    retry_after = 60

    def allow_login(self, request, username):
        ip = request.META.get("REMOTE_ADDR", "unknown")
        username = unicodedata.normalize("NFKC", str(username)).strip().casefold()
        return self.check_limits([
            ("login-source", ip, 30, 300),
            ("login-pair", ip + ":" + username, 8, 300),
        ])

    def allow_request(self, request, view):
        if not settings.SECURITY_RATE_LIMITS_ENABLED:
            return True
        ip = request.META.get("REMOTE_ADDR", "unknown")
        name = type(view).__name__
        limits = []
        if name == "LoginView":
            username = request.data.get("username", "") if hasattr(request.data, "get") else ""
            return self.allow_login(request, username)
        else:
            identity = str(request.user.pk) if request.user.is_authenticated else ip
            action = getattr(view, "action", "")
            limits = [("api", identity, 600, 60)]
            if name in {"PushTestView", "PushSubscribeView"} or action == "test_push":
                limits.append(("push", identity, 5, 60))
            if action in {"import_questions", "undo_import"}:
                limits.append(("import", identity, 5, 60))
            if action in {"ranking", "detailed_statistics", "me_assignments", "search_students"}:
                limits.append(("report", identity, 30, 60))
            if action == "create":
                limits.append(("create", identity, 60, 60))
        return self.check_limits(limits)

    def check_limits(self, limits):
        if not settings.SECURITY_RATE_LIMITS_ENABLED:
            return True
        now = int(time.time())
        for scope, identity, limit, window in limits:
            digest = hashlib.sha256(identity.encode()).hexdigest()
            key = f"security:{scope}:{digest}:{now // window}"
            try:
                if cache.add(key, 1, timeout=window + 1):
                    count = 1
                else:
                    count = cache.incr(key)
            except Exception:
                # A failed shared limiter must not silently open expensive APIs.
                self.retry_after = 5
                return False
            if count > limit:
                self.retry_after = window - now % window
                return False
        return True

    def wait(self):
        return self.retry_after


class AdminLoginThrottleMiddleware:
    """Share the API password budget with every mounted Django Admin login."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if request.method != "POST" or not match or match.url_name != "login" or "admin" not in match.app_names:
            return None
        limiter = SecurityThrottle()
        if not limiter.allow_login(request, request.POST.get("username", "")):
            from django.http import HttpResponse
            response = HttpResponse("Too many login attempts. Please try again later.", status=429)
            response["Retry-After"] = str(limiter.wait())
            response["Cache-Control"] = "no-store"
            return response
