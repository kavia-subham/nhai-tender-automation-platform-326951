from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.core.db import Db, get_db
from src.api.core.security import AuthUser, get_current_user
from src.api.models import (
    ChatResponse,
    CreateConversationRequest,
    Conversation,
    HistoryResponse,
    Message,
    SendMessageRequest,
)
from src.api.services.chat_service import ChatOrchestrateRequest, ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/conversations",
    summary="Create conversation",
    description="Create a new conversation for a tender context.",
    operation_id="chat_create_conversation",
    response_model=Conversation,
)
def create_conversation(payload: CreateConversationRequest, user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> Conversation:
    """Create a conversation."""
    row = db.fetch_one(
        """
        INSERT INTO public.conversations (tender_id, created_by, status, title, metadata)
        VALUES (%(tid)s, %(uid)s, 'active'::public.conversation_status, %(title)s, '{}'::jsonb)
        RETURNING id, tender_id, created_by, status, title, metadata, created_at, updated_at
        """,
        {"tid": payload.tender_id, "uid": user.id, "title": payload.title},
    )
    return Conversation(
        id=str(row["id"]),
        tender_id=str(row["tender_id"]) if row.get("tender_id") else None,
        created_by=str(row["created_by"]) if row.get("created_by") else None,
        status=str(row["status"]),
        title=row.get("title"),
        metadata=row.get("metadata") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="Send message",
    description="Send a message and get assistant response with optional dedupe/categorization/insights (self-hosted LLM stub).",
    operation_id="chat_send_message",
    response_model=ChatResponse,
)
def send_message(conversation_id: str, payload: SendMessageRequest, user: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> ChatResponse:
    """Send message with orchestration."""
    conv = db.fetch_one(
        "SELECT id, tender_id FROM public.conversations WHERE id=%(id)s",
        {"id": conversation_id},
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    svc = ChatService(db)
    result = svc.orchestrate(
        ChatOrchestrateRequest(
            conversation_id=conversation_id,
            tender_id=str(conv["tender_id"]) if conv.get("tender_id") else None,
            user_id=user.id,
            content=payload.content,
            dedupe=payload.dedupe,
            categorize=payload.categorize,
            insights=payload.insights,
        )
    )

    return ChatResponse(
        user_message=Message(**{**result.user_message, "id": str(result.user_message["id"]), "conversation_id": str(result.user_message["conversation_id"])}),
        assistant_message=Message(**{**result.assistant_message, "id": str(result.assistant_message["id"]), "conversation_id": str(result.assistant_message["conversation_id"])}),
        dedupe=result.dedupe,
        categorization=result.categorization,
        insights=result.insights,
    )


@router.get(
    "/conversations/{conversation_id}/history",
    summary="Get chat history",
    description="Fetch conversation and its messages.",
    operation_id="chat_get_history",
    response_model=HistoryResponse,
)
def get_history(conversation_id: str, _: AuthUser = Depends(get_current_user), db: Db = Depends(get_db)) -> HistoryResponse:
    """Return conversation + messages."""
    conv = db.fetch_one(
        """
        SELECT id, tender_id, created_by, status, title, metadata, created_at, updated_at
        FROM public.conversations
        WHERE id=%(id)s
        """,
        {"id": conversation_id},
    )
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = db.fetch_all(
        """
        SELECT id, conversation_id, role, content, tool_payload, token_count, created_at
        FROM public.messages
        WHERE conversation_id=%(id)s
        ORDER BY created_at ASC
        """,
        {"id": conversation_id},
    )

    return HistoryResponse(
        conversation=Conversation(
            id=str(conv["id"]),
            tender_id=str(conv["tender_id"]) if conv.get("tender_id") else None,
            created_by=str(conv["created_by"]) if conv.get("created_by") else None,
            status=str(conv["status"]),
            title=conv.get("title"),
            metadata=conv.get("metadata") or {},
            created_at=conv["created_at"],
            updated_at=conv["updated_at"],
        ),
        messages=[
            Message(
                id=str(m["id"]),
                conversation_id=str(m["conversation_id"]),
                role=str(m["role"]),
                content=m["content"],
                tool_payload=m.get("tool_payload"),
                token_count=m.get("token_count"),
                created_at=m["created_at"],
            )
            for m in msgs
        ],
    )
