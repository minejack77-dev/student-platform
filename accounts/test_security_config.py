from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.cache import cache
from rest_framework.test import APIClient
from config.security import security_settings


class DeploymentSecurityTests(SimpleTestCase):
    def production(self):
        return {"DJANGO_ENV": "production", "DJANGO_SECRET_KEY": "synthetic-configuration-test-key-0123456789-ABCDEFGHIJKLMN", "DJANGO_ALLOWED_HOSTS": "school.example.invalid", "DJANGO_CACHE_URL": "redis://127.0.0.1:6379/2"}

    def test_production_refuses_missing_or_known_key_debug_and_wildcard_hosts(self):
        for changes in ({"DJANGO_SECRET_KEY": ""}, {"DJANGO_SECRET_KEY": "django-insecure-" + "x" * 60}, {"DJANGO_SECRET_KEY": "x" * 60}, {"DJANGO_DEBUG": "true"}, {"DJANGO_ALLOWED_HOSTS": "*"}, {"DJANGO_CACHE_URL": ""}):
            with self.subTest(changes=list(changes)), self.assertRaises(ImproperlyConfigured):
                security_settings(self.production() | changes, testing=False)

    def test_production_secure_defaults_and_proxy_trust_are_explicit(self):
        settings = security_settings(self.production(), testing=False)
        self.assertFalse(settings["DEBUG"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])
        self.assertTrue(settings["SECURE_SSL_REDIRECT"])
        self.assertEqual(settings["SECRET_KEY_FALLBACKS"], [])
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", settings)
        self.assertEqual(security_settings(self.production() | {"DJANGO_TRUST_PROXY": "true"}, testing=False)["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_development_key_is_not_a_shared_public_constant(self):
        first = security_settings({"DJANGO_ENV": "development"}, testing=False)
        second = security_settings({"DJANGO_ENV": "development"}, testing=False)
        self.assertNotEqual(first["SECRET_KEY"], second["SECRET_KEY"])
        self.assertTrue(first["DEBUG"])


@override_settings(SECURITY_RATE_LIMITS_ENABLED=True)
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def tearDown(self):
        cache.clear()

    def test_login_pair_limit_has_retry_after_and_does_not_lock_other_sources(self):
        payload = {"username": "nonexistent", "password": "synthetic-wrong"}
        for _ in range(8):
            self.assertEqual(self.client.post("/api/auth/login/", payload, format="json").status_code, 400)
        response = self.client.post("/api/auth/login/", payload, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(self.client.post("/api/auth/login/", payload, format="json", REMOTE_ADDR="192.0.2.2").status_code, 400)

    def test_basic_auth_does_not_offer_an_alternate_login_path(self):
        response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION="Basic dGVzdDp0ZXN0")
        self.assertEqual(response.status_code, 403)
