from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.core.settings import get_settings
from src.api.routers import admin, analytics, auth, billing, chat, conformance, documents, rbac, tenders

openapi_tags = [
    {"name": "health", "description": "Health and diagnostics."},
    {"name": "auth", "description": "Authentication, sessions, and MFA."},
    {"name": "rbac", "description": "Role-based access control administration."},
    {"name": "tenders", "description": "Tender discovery and selection."},
    {"name": "documents", "description": "Tender and vendor document ingestion + versioning workflows."},
    {"name": "chat", "description": "Chat orchestration: history, dedupe, categorization, insights."},
    {"name": "conformance", "description": "Clause-by-clause conformance checks."},
    {"name": "admin", "description": "Admin workflows, approvals, audit, and publishing controls."},
    {"name": "analytics", "description": "Analytics dashboard metrics."},
    {"name": "billing", "description": "Usage tracking and billing summary."},
]

settings = get_settings()

app = FastAPI(
    title="NHAI AIQPS Backend API",
    description="REST API for NHAI AIQPS (tender query automation) with self-hosted LLM adapters (no external AI calls).",
    version="0.2.0",
    openapi_tags=openapi_tags,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(rbac.router)
app.include_router(tenders.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(conformance.router)
app.include_router(admin.router)
app.include_router(analytics.router)
app.include_router(billing.router)


@app.get(
    "/",
    tags=["health"],
    summary="Health check",
    description="Basic health check endpoint.",
    operation_id="health_check",
)
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}
