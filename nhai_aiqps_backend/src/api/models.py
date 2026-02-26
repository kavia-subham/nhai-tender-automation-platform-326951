from __future__ import annotations

from datetime import datetime, date
from typing import Any, Optional

from pydantic import BaseModel, Field


# --- Auth / MFA ---

class RegisterVendorRequest(BaseModel):
    email: str = Field(..., description="Vendor email address (unique).")
    organization_name: str = Field(..., description="Vendor organization/company name.")
    full_name: Optional[str] = Field(None, description="Full name of the primary contact.")
    password: str = Field(..., min_length=8, description="Plaintext password; will be stored as a hash.")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email.")
    password: str = Field(..., description="User password.")
    user_type: Optional[str] = Field(None, description="Optional hint: vendor/admin.")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token.")
    token_type: str = Field("bearer", description="Token type.")
    mfa_required: bool = Field(..., description="Whether user must complete MFA before privileged actions.")
    user: dict[str, Any] = Field(..., description="User summary.")


class BeginMfaResponse(BaseModel):
    mfa_challenge_id: str = Field(..., description="Challenge identifier to be used for verify.")
    delivery: str = Field(..., description="How code was delivered (totp/email/sms). For TOTP, this is 'totp'.")
    message: str = Field(..., description="Human-readable message.")


class VerifyMfaRequest(BaseModel):
    mfa_challenge_id: str = Field(..., description="Challenge identifier returned by beginMfa.")
    code: str = Field(..., description="One-time code.")


class VerifyMfaResponse(BaseModel):
    access_token: str = Field(..., description="New JWT with mfa_verified=true.")
    token_type: str = Field("bearer", description="Token type.")


class MfaEnrollResponse(BaseModel):
    device_id: str = Field(..., description="MFA device id.")
    method: str = Field(..., description="MFA method (totp).")
    label: Optional[str] = Field(None, description="Device label.")
    totp_uri: Optional[str] = Field(None, description="TOTP provisioning URI (otpauth://).")
    secret_preview: Optional[str] = Field(None, description="Secret preview for demo/dev; avoid in production.")


# --- RBAC ---

class Role(BaseModel):
    id: str
    name: str
    description: Optional[str] = None


class AssignRoleRequest(BaseModel):
    user_id: str = Field(..., description="User ID.")
    role_name: str = Field(..., description="Role name to assign.")


# --- Tenders / Documents ---

class Tender(BaseModel):
    id: str
    nhai_tender_id: Optional[str] = None
    title: str
    published_at: Optional[datetime] = None
    closing_at: Optional[datetime] = None
    source_url: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    id: str
    tender_id: Optional[str] = None
    kind: str
    status: str
    filename: Optional[str] = None
    content_type: Optional[str] = None
    sha256: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    current_version: int


class UploadDocumentResponse(BaseModel):
    document: Document
    workflow_id: str = Field(..., description="Workflow created for approvals/versioning.")


# --- Chat / Orchestration ---

class CreateConversationRequest(BaseModel):
    tender_id: str = Field(..., description="Tender ID context.")
    title: Optional[str] = Field(None, description="Optional conversation title.")


class Conversation(BaseModel):
    id: str
    tender_id: Optional[str] = None
    created_by: Optional[str] = None
    status: str
    title: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User message content.")
    dedupe: bool = Field(True, description="Whether to deduplicate similar questions.")
    categorize: bool = Field(True, description="Whether to categorize the query.")
    insights: bool = Field(True, description="Whether to generate insights.")


class Message(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    token_count: Optional[int] = None
    tool_payload: Optional[dict[str, Any]] = None
    created_at: datetime


class ChatResponse(BaseModel):
    user_message: Message
    assistant_message: Message
    dedupe: Optional[dict[str, Any]] = None
    categorization: Optional[dict[str, Any]] = None
    insights: Optional[dict[str, Any]] = None


class HistoryResponse(BaseModel):
    conversation: Conversation
    messages: list[Message]


class DedupeCategoriesResponse(BaseModel):
    tender_id: str
    duplicates: list[dict[str, Any]] = Field(default_factory=list)
    categories: list[dict[str, Any]] = Field(default_factory=list)


class InsightsResponse(BaseModel):
    tender_id: str
    insights: list[dict[str, Any]] = Field(default_factory=list)


# --- Conformance ---

class ConformanceCheckRequest(BaseModel):
    tender_id: str = Field(..., description="Tender being evaluated.")
    document_id: Optional[str] = Field(None, description="Optional specific document to check (e.g., vendor upload).")
    baseline_kinds: list[str] = Field(default_factory=lambda: ["sbd", "policy"], description="Baseline doc kinds.")


class ConformanceCheckResponse(BaseModel):
    check_id: str = Field(..., description="Conformance check run id.")
    tender_id: str
    status: str = Field(..., description="queued|running|completed|failed (simplified).")
    results: dict[str, Any] = Field(default_factory=dict)


# --- Workflows / Approvals / Audit ---

class Workflow(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    status: str
    created_by: Optional[str] = None
    current_version: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UpdateWorkflowStateRequest(BaseModel):
    status: str = Field(..., description="draft|in_review|approved|rejected|cancelled")
    comment: Optional[str] = Field(None, description="Decision comment.")


class AuditEvent(BaseModel):
    id: str
    actor_user_id: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# --- Analytics / Usage / Billing ---

class AnalyticsResponse(BaseModel):
    metrics: dict[str, Any] = Field(default_factory=dict)


class BillingSummaryResponse(BaseModel):
    user_id: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    totals: dict[str, Any] = Field(default_factory=dict)
    invoices: list[dict[str, Any]] = Field(default_factory=list)
