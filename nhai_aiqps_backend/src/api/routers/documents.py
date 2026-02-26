from __future__ import annotations

import hashlib
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, get_current_user
from src.api.models import Document, UploadDocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])


def _audit(db: Db, actor_user_id: str | None, action: str, entity_type: str | None, entity_id: str | None, details: dict | None = None):
    db.execute(
        """
        INSERT INTO public.audit_log (actor_user_id, action, entity_type, entity_id, details)
        VALUES (%(uid)s, %(action)s, %(et)s, %(eid)s, %(details)s::jsonb)
        """,
        {"uid": actor_user_id, "action": action, "et": entity_type, "eid": entity_id, "details": (details or {})},
    )


@router.post(
    "/upload",
    summary="Upload a document",
    description="Upload a tender document (pdf/docx/txt/pptx). Stores metadata and creates workflow for approvals/versioning. File bytes are not persisted in MVP; storage_path is a placeholder.",
    operation_id="documents_upload",
    response_model=UploadDocumentResponse,
)
async def upload_document(
    tender_id: str = Form(..., description="Tender ID for the document context."),
    kind: str = Form("other", description="Document kind (rfp/sbd/policy/vendor_upload/etc)."),
    file: UploadFile = File(...),
    user: AuthUser = Depends(get_current_user),
    db: Db = Depends(get_db),
) -> UploadDocumentResponse:
    """Upload a document (metadata persistence for MVP)."""
    data = await file.read()
    sha256 = hashlib.sha256(data).hexdigest()
    storage_path = f"mvp://uploads/{uuid4()}/{file.filename}"

    doc = db.fetch_one(
        """
        INSERT INTO public.documents (tender_id, uploaded_by, kind, status, filename, content_type, storage_path, sha256, metadata)
        VALUES (%(tid)s, %(uid)s, %(kind)s::public.doc_kind, 'uploaded'::public.doc_status,
                %(fn)s, %(ct)s, %(sp)s, %(sha)s, '{}'::jsonb)
        RETURNING id, tender_id, kind, status, filename, content_type, sha256, metadata, current_version
        """,
        {"tid": tender_id, "uid": user.id, "kind": kind, "fn": file.filename, "ct": file.content_type, "sp": storage_path, "sha": sha256},
    )
    if not doc:
        raise HTTPException(status_code=500, detail="Failed to create document")

    wf = db.fetch_one(
        """
        INSERT INTO public.workflows (entity_type, entity_id, status, created_by, current_version, metadata)
        VALUES ('document', %(eid)s, 'draft'::public.workflow_status, %(uid)s, 1, '{}'::jsonb)
        RETURNING id
        """,
        {"eid": str(doc["id"]), "uid": user.id},
    )
    _audit(db, user.id, "upload", "document", str(doc["id"]), {"filename": file.filename, "sha256": sha256})
    model = Document(
        id=str(doc["id"]),
        tender_id=str(doc["tender_id"]) if doc.get("tender_id") else None,
        kind=str(doc["kind"]),
        status=str(doc["status"]),
        filename=doc.get("filename"),
        content_type=doc.get("content_type"),
        sha256=doc.get("sha256"),
        metadata=doc.get("metadata") or {},
        current_version=int(doc.get("current_version") or 1),
    )
    return UploadDocumentResponse(document=model, workflow_id=str(wf["id"]))
