from __future__ import annotations

import logging
from uuid import uuid4

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.core.db import Db, get_db
from src.api.core.security import (
    AuthUser,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from src.api.models import (
    BeginMfaResponse,
    LoginRequest,
    LoginResponse,
    MfaEnrollResponse,
    RegisterVendorRequest,
    VerifyMfaRequest,
    VerifyMfaResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _audit(db: Db, actor_user_id: str | None, action: str, entity_type: str | None = None, entity_id: str | None = None, details: dict | None = None):
    db.execute(
        """
        INSERT INTO public.audit_log (actor_user_id, action, entity_type, entity_id, details)
        VALUES (%(uid)s, %(action)s, %(et)s, %(eid)s, %(details)s::jsonb)
        """,
        {"uid": actor_user_id, "action": action, "et": entity_type, "eid": entity_id, "details": (details or {})},
    )


@router.post(
    "/register",
    summary="Register vendor",
    description="Register a vendor account. Password is stored as a hash.",
    operation_id="auth_register_vendor",
)
def register_vendor(payload: RegisterVendorRequest, db: Db = Depends(get_db)):
    """Register a vendor account.

    Returns:
        Basic user record.
    """
    existing = db.fetch_one("SELECT id FROM public.users WHERE email=%(email)s", {"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = db.fetch_one(
        """
        INSERT INTO public.users (user_type, email, organization_name, full_name, password_hash)
        VALUES ('vendor', %(email)s, %(org)s, %(name)s, %(ph)s)
        RETURNING id, user_type, email, organization_name, full_name, created_at
        """,
        {"email": payload.email, "org": payload.organization_name, "name": payload.full_name, "ph": hash_password(payload.password)},
    )
    _audit(db, str(user["id"]), "create", "user", str(user["id"]), {"user_type": "vendor"})
    return {"user": user}


@router.post(
    "/login",
    summary="Login",
    description="Email+password login; returns a JWT token. MFA may be required.",
    operation_id="auth_login",
    response_model=LoginResponse,
)
def login(payload: LoginRequest, request: Request, db: Db = Depends(get_db)) -> LoginResponse:
    """Authenticate user credentials and return JWT.

    Notes:
    - If user has any enabled MFA devices, mfa_required=true and token carries mfa=false.
    """
    user = db.fetch_one(
        "SELECT id, user_type, email, password_hash, is_active FROM public.users WHERE email=%(email)s",
        {"email": payload.email},
    )
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.get("password_hash") or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    roles = [r["name"] for r in db.fetch_all(
        """
        SELECT r.name
        FROM public.user_roles ur
        JOIN public.roles r ON r.id = ur.role_id
        WHERE ur.user_id = %(uid)s
        """,
        {"uid": str(user["id"])},
    )]
    mfa = db.fetch_one(
        "SELECT id FROM public.mfa_devices WHERE user_id=%(uid)s AND is_enabled=true LIMIT 1",
        {"uid": str(user["id"])},
    )
    mfa_required = bool(mfa)

    token = create_access_token(
        user_id=str(user["id"]),
        user_type=str(user["user_type"]),
        roles=roles,
        mfa_verified=not mfa_required,
    )
    _audit(db, str(user["id"]), "login", "user", str(user["id"]), {"ip": request.client.host if request.client else None})
    return LoginResponse(
        access_token=token,
        mfa_required=mfa_required,
        user={"id": str(user["id"]), "email": user["email"], "user_type": user["user_type"], "roles": roles},
    )


@router.post(
    "/mfa/enroll/totp",
    summary="Enroll TOTP MFA",
    description="Enroll a TOTP device for the current user. Stores secret_encrypted as plaintext placeholder (replace with app-level encryption).",
    operation_id="auth_mfa_enroll_totp",
    response_model=MfaEnrollResponse,
)
def enroll_totp(user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> MfaEnrollResponse:
    """Enroll TOTP for current user.

    Security note:
    - This stores secret_encrypted in DB. In production, encrypt it using an app-managed key (AES-256 at rest requirement).
    """
    secret = pyotp.random_base32()
    device = db.fetch_one(
        """
        INSERT INTO public.mfa_devices (user_id, method, label, secret_encrypted, is_enabled)
        VALUES (%(uid)s, 'totp', %(label)s, %(secret)s, true)
        RETURNING id, method, label
        """,
        {"uid": user.id, "label": "primary", "secret": secret},
    )
    _audit(db, user.id, "mfa_enable", "mfa_device", str(device["id"]), {"method": "totp"})
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email or user.id, issuer_name="NHAI-AIQPS")
    return MfaEnrollResponse(
        device_id=str(device["id"]),
        method=str(device["method"]),
        label=device.get("label"),
        totp_uri=uri,
        secret_preview=secret[:4] + "..."  # do not expose full secret; preview only
    )


@router.post(
    "/mfa/begin",
    summary="Begin MFA",
    description="Begin an MFA challenge for current user. For TOTP, returns a challenge id.",
    operation_id="auth_mfa_begin",
    response_model=BeginMfaResponse,
)
def begin_mfa(user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> BeginMfaResponse:
    """Begin MFA challenge.

    Currently supports:
    - TOTP (code generated by authenticator)
    """
    device = db.fetch_one(
        """
        SELECT id, method
        FROM public.mfa_devices
        WHERE user_id=%(uid)s AND is_enabled=true
        ORDER BY created_at ASC
        LIMIT 1
        """,
        {"uid": user.id},
    )
    if not device:
        raise HTTPException(status_code=400, detail="No MFA device enrolled")

    challenge_id = str(uuid4())
    # Store challenge in-memory not available; we encode challenge as device_id:nonce for MVP.
    mfa_challenge_id = f"{device['id']}:{challenge_id}"
    return BeginMfaResponse(mfa_challenge_id=mfa_challenge_id, delivery=str(device["method"]), message="Enter your MFA code.")


@router.post(
    "/mfa/verify",
    summary="Verify MFA",
    description="Verify MFA code for a challenge and return a new JWT with mfa=true.",
    operation_id="auth_mfa_verify",
    response_model=VerifyMfaResponse,
)
def verify_mfa(payload: VerifyMfaRequest, user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> VerifyMfaResponse:
    """Verify MFA code."""
    try:
        device_id, _nonce = payload.mfa_challenge_id.split(":", 1)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid challenge id") from e

    device = db.fetch_one(
        "SELECT id, method, secret_encrypted FROM public.mfa_devices WHERE id=%(id)s AND user_id=%(uid)s AND is_enabled=true",
        {"id": device_id, "uid": user.id},
    )
    if not device:
        raise HTTPException(status_code=400, detail="MFA device not found")

    if str(device["method"]) != "totp":
        raise HTTPException(status_code=400, detail="Unsupported MFA method in MVP")

    secret = device.get("secret_encrypted") or ""
    totp = pyotp.TOTP(secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")

    # Update last_used_at
    db.execute("UPDATE public.mfa_devices SET last_used_at=now() WHERE id=%(id)s", {"id": device_id})

    # Re-issue token with mfa verified true
    roles = [r["name"] for r in db.fetch_all(
        """
        SELECT r.name
        FROM public.user_roles ur
        JOIN public.roles r ON r.id = ur.role_id
        WHERE ur.user_id = %(uid)s
        """,
        {"uid": user.id},
    )]
    token = create_access_token(
        user_id=user.id,
        user_type=user.user_type,
        roles=roles,
        mfa_verified=True,
    )
    _audit(db, user.id, "update", "mfa_device", str(device_id), {"verified": True})
    return VerifyMfaResponse(access_token=token)
