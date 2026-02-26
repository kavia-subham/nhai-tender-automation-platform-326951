from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, require_roles
from src.api.models import AuditEvent, UpdateWorkflowStateRequest, Workflow

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/workflows",
    summary="List workflows",
    description="List all workflows (admin/reviewer).",
    operation_id="admin_list_workflows",
    response_model=list[Workflow],
)
def list_workflows(_: AuthUser = Depends(require_roles("admin", "reviewer")), db: Db = Depends(get_db)) -> list[Workflow]:
    """List workflows."""
    rows = db.fetch_all(
        """
        SELECT id, entity_type, entity_id, status, created_by, current_version, metadata, created_at, updated_at
        FROM public.workflows
        ORDER BY updated_at DESC
        LIMIT 200
        """
    )
    return [
        Workflow(
            id=str(r["id"]),
            entity_type=r["entity_type"],
            entity_id=str(r["entity_id"]),
            status=str(r["status"]),
            created_by=str(r["created_by"]) if r.get("created_by") else None,
            current_version=int(r.get("current_version") or 1),
            metadata=r.get("metadata") or {},
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]


@router.post(
    "/workflows/{workflow_id}/state",
    summary="Update workflow state",
    description="Update workflow status and write an audit event.",
    operation_id="admin_update_workflow_state",
    response_model=Workflow,
)
def update_workflow_state(
    workflow_id: str,
    payload: UpdateWorkflowStateRequest,
    user: AuthUser = Depends(require_roles("admin", "reviewer")),
    db: Db = Depends(get_db),
) -> Workflow:
    """Update workflow state."""
    wf = db.fetch_one("SELECT id FROM public.workflows WHERE id=%(id)s", {"id": workflow_id})
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")

    row = db.fetch_one(
        """
        UPDATE public.workflows
        SET status=%(status)s::public.workflow_status, updated_at=now()
        WHERE id=%(id)s
        RETURNING id, entity_type, entity_id, status, created_by, current_version, metadata, created_at, updated_at
        """,
        {"id": workflow_id, "status": payload.status},
    )
    db.execute(
        """
        INSERT INTO public.audit_log (actor_user_id, action, entity_type, entity_id, details)
        VALUES (%(uid)s, 'update'::public.audit_action, 'workflow', %(eid)s, %(details)s::jsonb)
        """,
        {"uid": user.id, "eid": workflow_id, "details": {"new_status": payload.status, "comment": payload.comment}},
    )
    return Workflow(
        id=str(row["id"]),
        entity_type=row["entity_type"],
        entity_id=str(row["entity_id"]),
        status=str(row["status"]),
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        current_version=int(row.get("current_version") or 1),
        metadata=row.get("metadata") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get(
    "/audit",
    summary="Get audit log",
    description="List recent audit events (admin/reviewer).",
    operation_id="admin_get_audit",
    response_model=list[AuditEvent],
)
def get_audit(_: AuthUser = Depends(require_roles("admin", "reviewer")), db: Db = Depends(get_db)) -> list[AuditEvent]:
    """Get audit trail."""
    rows = db.fetch_all(
        """
        SELECT id, actor_user_id, action, entity_type, entity_id, details, created_at
        FROM public.audit_log
        ORDER BY created_at DESC
        LIMIT 500
        """
    )
    return [
        AuditEvent(
            id=str(r["id"]),
            actor_user_id=str(r["actor_user_id"]) if r.get("actor_user_id") else None,
            action=str(r["action"]),
            entity_type=r.get("entity_type"),
            entity_id=str(r["entity_id"]) if r.get("entity_id") else None,
            details=r.get("details") or {},
            created_at=r["created_at"],
        )
        for r in rows
    ]
