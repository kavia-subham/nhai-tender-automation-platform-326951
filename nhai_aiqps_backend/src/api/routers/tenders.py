from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, get_current_user
from src.api.models import Tender

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get(
    "",
    summary="List tenders",
    description="List NHAI-published tenders available to vendors/admins.",
    operation_id="tenders_list",
    response_model=list[Tender],
)
def list_tenders(_: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> list[Tender]:
    """List tenders."""
    rows = db.fetch_all(
        """
        SELECT id, nhai_tender_id, title, published_at, closing_at, source_url, metadata
        FROM public.tenders
        ORDER BY created_at DESC
        LIMIT 200
        """
    )
    return [
        Tender(
            id=str(r["id"]),
            nhai_tender_id=r.get("nhai_tender_id"),
            title=r["title"],
            published_at=r.get("published_at"),
            closing_at=r.get("closing_at"),
            source_url=r.get("source_url"),
            metadata=r.get("metadata") or {},
        )
        for r in rows
    ]
