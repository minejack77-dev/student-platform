"""Allowlisted security metadata only: never serialize requests or exceptions."""
from datetime import datetime, timezone
import json
import logging
from uuid import uuid4

logger = logging.getLogger("security.audit")


class SecurityAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = getattr(getattr(request, "user", None), "pk", None)
        response = self.get_response(request)
        if not request.path.startswith(("/api/", "/admin/")):
            return response
        request_id = uuid4().hex
        response["X-Request-ID"] = request_id
        if request.method in {"GET", "HEAD", "OPTIONS"} and response.status_code < 400:
            return response
        match = getattr(request, "resolver_match", None)
        route = getattr(match, "view_name", None) or "unresolved"
        targets = {key: str(value) for key, value in getattr(match, "kwargs", {}).items()
                   if key in {"pk", "object_id", "image_id"} and str(value).isdigit() and len(str(value)) < 21}
        event = {
            "time": datetime.now(timezone.utc).isoformat(), "request_id": request_id,
            "actor_id": actor or getattr(getattr(request, "user", None), "pk", None), "action": route, "method": request.method,
            "targets": targets, "status": response.status_code,
            "result": "success" if response.status_code < 400 else "denied" if response.status_code < 500 else "error",
        }
        try:
            logger.info(json.dumps(event, ensure_ascii=True, separators=(",", ":")))
        except Exception:
            # Sink outages must not disclose payloads or break authentication.
            pass
        return response
