"""Short-lived, single-use authorization for confirmed vendor investigations.

The identity resolver issues an opaque authorization only after a vendor reaches
CONFIRMED status. The investigation endpoint consumes that authorization before
creating a job. No authorization token is placed in job state or reports.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_AUTHORIZATION_TTL_SECONDS = 15 * 60
MAX_AUTHORIZATIONS = 500
MIN_CONFIRMED_CONFIDENCE = 0.90
STRONG_IDENTITY_QUALITIES = {
    "OFFICIAL_WEBSITE",
    "AUTHORITATIVE_IDENTITY",
    "COMPANY_OWNED",
}


class InvestigationAuthorizationError(ValueError):
    """Safe API-facing authorization failure."""

    def __init__(
        self,
        detail: str,
        *,
        status_code: int = 401,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class ConfirmedIdentityAuthorization:
    authorization_id: str
    requested_name: str
    canonical_name: str
    website: str | None
    website_domain: str | None
    country: str | None
    city: str | None
    industry: str | None
    identity_confidence: float
    confidence_label: str
    source_quality_labels: tuple[str, ...]
    evidence_urls: tuple[str, ...]
    issued_at: str
    expires_at: str
    consumed_at: str | None = None

    def public_identity(self) -> dict[str, Any]:
        """Return the identity snapshot without the opaque authorization ID."""
        payload = asdict(self)
        payload.pop("authorization_id", None)
        payload["status"] = "CONFIRMED"
        return payload


_AUTHORIZATIONS: dict[str, ConfirmedIdentityAuthorization] = {}
_AUTHORIZATION_LOCK = threading.RLock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _normalize_name(value: Any) -> str:
    return _clean(value).casefold()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _prune(now: datetime) -> None:
    expired = [
        token
        for token, record in _AUTHORIZATIONS.items()
        if record.consumed_at is not None
        or _parse_iso(record.expires_at) <= now
    ]
    for token in expired:
        _AUTHORIZATIONS.pop(token, None)

    if len(_AUTHORIZATIONS) <= MAX_AUTHORIZATIONS:
        return

    oldest = sorted(
        _AUTHORIZATIONS.items(),
        key=lambda item: item[1].issued_at,
    )[: len(_AUTHORIZATIONS) - MAX_AUTHORIZATIONS]
    for token, _ in oldest:
        _AUTHORIZATIONS.pop(token, None)


def issue_investigation_authorization(
    resolution_payload: dict[str, Any],
    *,
    ttl_seconds: int = DEFAULT_AUTHORIZATION_TTL_SECONDS,
) -> dict[str, Any]:
    """Issue an opaque authorization for a strongly confirmed identity."""
    if not isinstance(resolution_payload, dict):
        raise InvestigationAuthorizationError(
            "A confirmed identity result is required.",
            status_code=400,
        )

    if _clean(resolution_payload.get("resolution_status")).upper() != "CONFIRMED":
        raise InvestigationAuthorizationError(
            "Investigation authorization requires CONFIRMED identity status.",
            status_code=409,
        )

    selected = resolution_payload.get("selected_candidate")
    if not isinstance(selected, dict):
        raise InvestigationAuthorizationError(
            "Confirmed identity is missing the selected candidate.",
            status_code=409,
        )

    requested_name = _clean(resolution_payload.get("requested_name"))
    canonical_name = _clean(selected.get("legal_name"))
    confidence = selected.get("identity_confidence")
    labels = tuple(
        sorted(
            {
                _clean(item).upper()
                for item in (selected.get("source_quality_labels") or ())
                if _clean(item)
            }
        )
    )

    if not requested_name or not canonical_name:
        raise InvestigationAuthorizationError(
            "Confirmed identity is missing a company name.",
            status_code=409,
        )

    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or float(confidence) < MIN_CONFIRMED_CONFIDENCE
    ):
        raise InvestigationAuthorizationError(
            "Confirmed identity confidence is below the investigation threshold.",
            status_code=409,
        )

    if not (set(labels) & STRONG_IDENTITY_QUALITIES):
        raise InvestigationAuthorizationError(
            "Confirmed identity lacks an authenticated identity source.",
            status_code=409,
        )

    if ttl_seconds < 30 or ttl_seconds > 3600:
        raise InvestigationAuthorizationError(
            "Authorization lifetime must be between 30 and 3600 seconds.",
            status_code=400,
        )

    now = _utc_now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    authorization_id = secrets.token_urlsafe(32)

    record = ConfirmedIdentityAuthorization(
        authorization_id=authorization_id,
        requested_name=requested_name,
        canonical_name=canonical_name,
        website=_clean(selected.get("website")) or None,
        website_domain=_clean(selected.get("website_domain")) or None,
        country=_clean(selected.get("country")) or None,
        city=_clean(selected.get("city")) or None,
        industry=_clean(selected.get("industry")) or None,
        identity_confidence=round(float(confidence), 2),
        confidence_label=_clean(selected.get("confidence_label")) or "HIGH",
        source_quality_labels=labels,
        evidence_urls=tuple(
            _clean(url)
            for url in (selected.get("evidence_urls") or ())
            if _clean(url)
        ),
        issued_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
    )

    with _AUTHORIZATION_LOCK:
        _prune(now)
        _AUTHORIZATIONS[authorization_id] = record

    return {
        "authorization_id": authorization_id,
        "expires_at": record.expires_at,
        "single_use": True,
        "required_for": "/api/investigate",
    }


def consume_investigation_authorization(
    authorization_id: str,
    *,
    requested_vendor_name: str | None = None,
) -> dict[str, Any]:
    """Consume one valid authorization and return its safe identity snapshot."""
    token = _clean(authorization_id)
    if not token:
        raise InvestigationAuthorizationError(
            "identity_authorization_id is required.",
            status_code=401,
        )

    now = _utc_now()

    with _AUTHORIZATION_LOCK:
        record = _AUTHORIZATIONS.get(token)
        if record is None:
            raise InvestigationAuthorizationError(
                "Identity authorization is invalid, expired, or already used.",
                status_code=401,
            )

        if record.consumed_at is not None or _parse_iso(record.expires_at) <= now:
            _AUTHORIZATIONS.pop(token, None)
            raise InvestigationAuthorizationError(
                "Identity authorization is invalid, expired, or already used.",
                status_code=401,
            )

        supplied_name = _clean(requested_vendor_name)
        if supplied_name and _normalize_name(supplied_name) not in {
            _normalize_name(record.requested_name),
            _normalize_name(record.canonical_name),
        }:
            raise InvestigationAuthorizationError(
                "Requested vendor does not match the confirmed identity.",
                status_code=409,
            )

        consumed = ConfirmedIdentityAuthorization(
            **{
                **asdict(record),
                "consumed_at": now.isoformat(),
            }
        )
        _AUTHORIZATIONS[token] = consumed

    return consumed.public_identity()


def clear_investigation_authorizations_for_testing() -> None:
    """Clear process-local authorization state for deterministic tests."""
    with _AUTHORIZATION_LOCK:
        _AUTHORIZATIONS.clear()
