"""Bounded Web Push transport; never send to a user-selected arbitrary host."""
import base64
import ipaddress
import json
import logging
import hashlib
import re
import socket
from urllib.parse import urlsplit, urlunsplit

import requests
from django.conf import settings
from django.db import transaction, IntegrityError
from rest_framework.exceptions import APIException
from rest_framework import serializers

logger = logging.getLogger(__name__)
PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}


def validate_endpoint(value):
    try:
        parsed = urlsplit(value)
        if (
            len(value) > 500 or parsed.scheme != "https" or parsed.port not in (None, 443)
            or parsed.hostname not in PUSH_HOSTS or parsed.username or parsed.password
            or parsed.fragment or not parsed.path or "\\" in value
            or any(ord(char) < 33 for char in value)
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise serializers.ValidationError("Use an HTTPS endpoint from a supported push provider.")
    return value


def decode_key(value, length):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value):
        raise serializers.ValidationError("Invalid Web Push key.")
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except ValueError:
        raise serializers.ValidationError("Invalid Web Push key.")
    if len(decoded) != length:
        raise serializers.ValidationError("Invalid Web Push key length.")
    return decoded


class PushKeysSerializer(serializers.Serializer):
    auth = serializers.CharField(max_length=100, trim_whitespace=False)
    p256dh = serializers.CharField(max_length=100, trim_whitespace=False)

    def validate(self, attrs):
        decode_key(attrs["auth"], 16)
        point = decode_key(attrs["p256dh"], 65)
        try:
            from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePublicKey, SECP256R1
            EllipticCurvePublicKey.from_encoded_point(SECP256R1(), point)
        except ValueError:
            raise serializers.ValidationError("Invalid Web Push public key.")
        return attrs


class PushSubscriptionSerializer(serializers.Serializer):
    endpoint = serializers.CharField(max_length=500, validators=[validate_endpoint], trim_whitespace=False)
    keys = PushKeysSerializer()


class SubscriptionConflict(APIException):
    status_code = 409
    default_detail = "This subscription cannot be registered. Refresh the browser subscription."


def register_subscription(user, data):
    from accounts.models import User, PushSubscription
    from webpush.models import PushInformation, SubscriptionInfo
    digest = hashlib.sha256(data["endpoint"].encode()).hexdigest()
    try:
        with transaction.atomic():
            User.objects.select_for_update().get(pk=user.pk)
            if PushInformation.objects.filter(subscription__endpoint=data["endpoint"]).exclude(user=user).exists():
                raise SubscriptionConflict
            info = PushInformation.objects.filter(user=user, subscription__endpoint=data["endpoint"]).select_related("subscription").first()
            if info is None:
                if PushInformation.objects.filter(user=user).count() >= 5:
                    raise serializers.ValidationError("At most five push subscriptions are allowed.")
                subscription = SubscriptionInfo.objects.create(browser="web", endpoint=data["endpoint"], **data["keys"])
                info = PushInformation.objects.create(user=user, subscription=subscription)
            else:
                subscription = info.subscription
                subscription.auth = data["keys"]["auth"]
                subscription.p256dh = data["keys"]["p256dh"]
                subscription.save(update_fields=["auth", "p256dh"])
            PushSubscription.objects.update_or_create(push_information=info, defaults={"endpoint_hash": digest})
    except IntegrityError:
        raise SubscriptionConflict
    return digest


def revoke_session_subscription(request):
    from webpush.models import PushInformation
    digest = request.session.pop("push_endpoint_hash", None)
    if digest:
        PushInformation.objects.filter(user=request.user, subscription_meta__endpoint_hash=digest).delete()


class PinnedHTTPSAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, hostname):
        self.hostname = hostname
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **kwargs):
        kwargs.update(assert_hostname=self.hostname, server_hostname=self.hostname)
        return super().init_poolmanager(connections, maxsize, block=block, **kwargs)


class SafePushSession(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False

    def request(self, method, url, **kwargs):
        validate_endpoint(url)
        parsed = urlsplit(url)
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        ips = [ipaddress.ip_address(item[4][0]) for item in addresses]
        if not ips or any(not ip.is_global for ip in ips):
            raise serializers.ValidationError("Push provider did not resolve to a public address.")
        selected = ips[0]
        address = f"[{selected}]" if selected.version == 6 else str(selected)
        # Resolve once and pin the connection, retaining TLS SNI/certificate checks.
        self.mount("https://", PinnedHTTPSAdapter(parsed.hostname))
        pinned_url = urlunsplit(("https", address, parsed.path, parsed.query, ""))
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Host"] = parsed.hostname
        kwargs.update(headers=headers, allow_redirects=False, timeout=(3, 5), stream=True, verify=True)
        response = super().request(method, pinned_url, **kwargs)
        # pywebpush may inspect remote error text. Bound it before returning.
        try:
            body = bytearray()
            for chunk in response.iter_content(1024):
                body.extend(chunk)
                if len(body) >= 8192:
                    break
            response._content = bytes(body[:8192])
        finally:
            response.close()
            response._content_consumed = True
        return response


def send_user_push(*, user, payload, ttl=60):
    from pywebpush import webpush, WebPushException
    from webpush.models import PushInformation

    subscriptions = PushInformation.objects.filter(user=user, subscription_meta__endpoint_hash__isnull=False).select_related("subscription").order_by("pk")[:5]
    for info in subscriptions:
        subscription = info.subscription
        data = {"endpoint": subscription.endpoint, "keys": {"auth": subscription.auth, "p256dh": subscription.p256dh}}
        serializer = PushSubscriptionSerializer(data=data)
        if not serializer.is_valid():
            continue  # Legacy unsafe subscriptions must never reach the transport.
        try:
            with SafePushSession() as session:
                response = webpush(
                    subscription_info=serializer.validated_data, data=json.dumps(payload), ttl=ttl,
                    vapid_private_key=settings.WEBPUSH_SETTINGS["VAPID_PRIVATE_KEY"],
                    vapid_claims={"sub": "mailto:" + settings.WEBPUSH_SETTINGS["VAPID_EMAIL"]},
                    timeout=5, requests_session=session,
                )
                if response.status_code in (404, 410):
                    info.delete()
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                info.delete()
            logger.warning("Push delivery failed for user_id=%s", user.pk)
        except (requests.RequestException, serializers.ValidationError, OSError, ValueError):
            logger.warning("Push delivery failed for user_id=%s", user.pk)
