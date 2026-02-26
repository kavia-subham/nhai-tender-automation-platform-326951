from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, require_roles
from src.api.models import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "",
    summary="Get analytics",
    description="Basic analytics endpoint for dashboards (MVP aggregation).",
    operation_id="analytics_get",
    response_model=AnalyticsResponse,
)
def get_analytics(_: AuthUser = Depends(require_roles("admin", "reviewer")), db: Db = Depends(get_db)) -> AnalyticsResponse:
    """Return simple metrics computed from DB."""
    users = db.fetch_one("SELECT count(*)::int AS c FROM public.users")
    tenders = db.fetch_one("SELECT count(*)::int AS c FROM public.tenders")
    docs = db.fetch_one("SELECT count(*)::int AS c FROM public.documents")
    conv = db.fetch_one("SELECT count(*)::int AS c FROM public.conversations")
    msgs = db.fetch_one("SELECT count(*)::int AS c FROM public.messages")
    workflows = db.fetch_one("SELECT count(*)::int AS c FROM public.workflows")

    return AnalyticsResponse(
        metrics={
            "users": users["c"] if users else 0,
            "tenders": tenders["c"] if tenders else 0,
            "documents": docs["c"] if docs else 0,
            "conversations": conv["c"] if conv else 0,
            "messages": msgs["c"] if msgs else 0,
            "workflows": workflows["c"] if workflows else 0,
        }
    )
