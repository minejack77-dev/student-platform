"""Fail-closed deployment settings, kept separate for startup regression tests."""
import os
import secrets
import sys
from django.core.exceptions import ImproperlyConfigured


def security_settings(env=None, *, testing=None):
    env = os.environ if env is None else env
    testing = len(sys.argv) > 1 and sys.argv[1] == "test" if testing is None else testing
    mode = env.get("DJANGO_ENV", "test" if testing else "production")
    if mode not in {"production", "development", "test"}:
        raise ImproperlyConfigured("DJANGO_ENV must be production, development or test.")
    production = mode == "production"
    boolean = lambda key, default: env.get(key, str(default)).lower() in {"true", "1", "yes", "on"}
    key = env.get("DJANGO_SECRET_KEY", "")
    debug = boolean("DJANGO_DEBUG", mode == "development")
    hosts = [host.strip() for host in env.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()]
    if production:
        if len(key) < 50 or len(set(key)) < 5 or key.startswith(("django-insecure-", "development-", "replace-")):
            raise ImproperlyConfigured("Production requires a unique DJANGO_SECRET_KEY of at least 50 characters.")
        if debug:
            raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")
        if not hosts or "*" in hosts:
            raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS.")
        if not env.get("DJANGO_CACHE_URL"):
            raise ImproperlyConfigured("Production requires DJANGO_CACHE_URL for shared security rate limits.")
    values = {
        "DJANGO_ENV": mode, "SECRET_KEY": key or secrets.token_urlsafe(48),
        "SECRET_KEY_FALLBACKS": [], "DEBUG": debug,
        "ALLOWED_HOSTS": hosts or ["127.0.0.1", "localhost", "testserver"],
        "SESSION_COOKIE_SECURE": production, "CSRF_COOKIE_SECURE": production,
        "SECURE_SSL_REDIRECT": production,
        "SECURE_HSTS_SECONDS": int(env.get("DJANGO_HSTS_SECONDS", "0")),
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": boolean("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False),
        "SECURE_HSTS_PRELOAD": boolean("DJANGO_HSTS_PRELOAD", False),
        "SESSION_COOKIE_AGE": 28800 if production else 1209600,
        "SECURITY_RATE_LIMITS_ENABLED": mode != "test",
    }
    if boolean("DJANGO_TRUST_PROXY", False):
        values["SECURE_PROXY_SSL_HEADER"] = ("HTTP_X_FORWARDED_PROTO", "https")
    if env.get("DJANGO_CACHE_URL"):
        values["CACHES"] = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env["DJANGO_CACHE_URL"]}}
    return values
