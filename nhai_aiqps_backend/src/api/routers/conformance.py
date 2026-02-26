from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends

from src.api.core.security import AuthUser, get_current_user
from src.api.models import ConformanceCheckRequest, ConformanceCheckResponse

router = APIRouter(prefix="/conformance", tags=["conformance"])


@router.post(
    "/run",
    summary="Run conformance check",
    description="Clause-by-clause conformance check (MVP stub). Returns a run id and placeholder results.",
    operation_id="conformance_run",
    response_model=ConformanceCheckResponse,
)
def run_conformance(payload: ConformanceCheckRequest, _: AuthUser = Depends(get_current_user)) -> ConformanceCheckResponse:
    """Run conformance check (stubbed; no external AI calls)."""
    check_id = str(uuid4())
    # In a full implementation, enqueue a job to a self-hosted checker service.
    return ConformanceCheckResponse(
        check_id=check_id,
        tender_id=payload.tender_id,
        status="completed",
        results={
            "baseline_kinds": payload.baseline_kinds,
            "findings": [],
            "note": "MVP stub: implement clause extraction + policy/SBD matching via self-hosted pipeline.",
        },
    )
