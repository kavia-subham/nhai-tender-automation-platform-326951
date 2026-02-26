from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, get_current_user
from src.api.models import BillingSummaryResponse

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/summary",
    summary="Get billing summary",
    description="Return usage/billing summary for current user (or any user if admin).",
    operation_id="billing_summary",
    response_model=BillingSummaryResponse,
)
def billing_summary(user_id: str | None = None, user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> BillingSummaryResponse:
    """Billing summary.

    If user_id is provided, caller must have admin role.
    """
    target_user_id = user_id or user.id
    if user_id and "admin" not in user.roles:
        raise_permission = True
        if raise_permission:
            # keep explicit
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

    inv = db.fetch_all(
        """
        SELECT id, status, period_start, period_end, currency, subtotal, tax, total, issued_at, due_at, paid_at, metadata, created_at
        FROM public.billing_invoices
        WHERE user_id=%(uid)s
        ORDER BY created_at DESC
        LIMIT 24
        """,
        {"uid": target_user_id},
    )

    usage = db.fetch_all(
        """
        SELECT event_type, sum(quantity)::float AS qty
        FROM public.usage_events
        WHERE user_id=%(uid)s
        GROUP BY event_type
        """,
        {"uid": target_user_id},
    )

    return BillingSummaryResponse(
        user_id=target_user_id,
        totals={"usage_by_type": {u["event_type"]: u["qty"] for u in usage}},
        invoices=[
            {
                "id": str(r["id"]),
                "status": str(r["status"]),
                "period_start": r.get("period_start"),
                "period_end": r.get("period_end"),
                "currency": r.get("currency"),
                "subtotal": float(r.get("subtotal") or 0),
                "tax": float(r.get("tax") or 0),
                "total": float(r.get("total") or 0),
                "issued_at": r.get("issued_at"),
                "due_at": r.get("due_at"),
                "paid_at": r.get("paid_at"),
                "metadata": r.get("metadata") or {},
                "created_at": r.get("created_at"),
            }
            for r in inv
        ],
    )
