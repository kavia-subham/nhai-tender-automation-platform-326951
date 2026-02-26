from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from src.api.core.db import Db
from src.api.llm.adapters import DeterministicStubLlmAdapter, LlmPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatOrchestrateRequest:
    """Request object for chat orchestration."""
    conversation_id: str
    tender_id: Optional[str]
    user_id: str
    content: str
    dedupe: bool
    categorize: bool
    insights: bool


@dataclass(frozen=True)
class ChatOrchestrateResult:
    """Result object from chat orchestration."""
    user_message: dict[str, Any]
    assistant_message: dict[str, Any]
    dedupe: Optional[dict[str, Any]] = None
    categorization: Optional[dict[str, Any]] = None
    insights: Optional[dict[str, Any]] = None


class ChatService:
    """Service for conversation persistence and orchestration."""

    def __init__(self, db: Db):
        self._db = db
        self._llm = DeterministicStubLlmAdapter()

    def _insert_message(self, conversation_id: str, role: str, content: str, sender_user_id: Optional[str]) -> dict[str, Any]:
        msg = self._db.fetch_one(
            """
            INSERT INTO public.messages (conversation_id, sender_user_id, role, content, tool_payload, token_count)
            VALUES (%(cid)s, %(uid)s, %(role)s, %(content)s, NULL, NULL)
            RETURNING id, conversation_id, role, content, token_count, tool_payload, created_at
            """,
            {"cid": conversation_id, "uid": sender_user_id, "role": role, "content": content},
        )
        return msg  # type: ignore[return-value]

    # PUBLIC_INTERFACE
    def orchestrate(self, req: ChatOrchestrateRequest) -> ChatOrchestrateResult:
        """Orchestrate chat message -> assistant response + optional analysis.

        Contract:
        - Persists both user and assistant messages in DB.
        - Uses self-hosted LLM adapter interface (stub by default).
        - Produces deterministic output (stub) with no external AI calls.
        """
        logger.info("chat_orchestrate.start cid=%s uid=%s", req.conversation_id, req.user_id)

        user_msg = self._insert_message(req.conversation_id, "user", req.content, req.user_id)

        system = "You are NHAI AIQPS assistant. Do not fabricate. Prefer citing tender documents when available."
        prompt = LlmPrompt(system=system, user=req.content, context=f"tender_id={req.tender_id}")
        llm_res = self._llm.generate(prompt)
        assistant_msg = self._insert_message(req.conversation_id, "assistant", llm_res.text, None)

        dedupe_obj: Optional[dict[str, Any]] = None
        cat_obj: Optional[dict[str, Any]] = None
        insights_obj: Optional[dict[str, Any]] = None

        if req.dedupe:
            dedupe_obj = {
                "is_duplicate": False,
                "reason": "Stub: no dedupe model wired yet.",
                "similar_message_ids": [],
            }
        if req.categorize:
            cat_obj = {"category": "general", "confidence": 0.2, "reason": "Stub categorization."}
        if req.insights:
            insights_obj = {
                "missing_info": ["Stub: Provide clause reference and document section."],
                "anomalies": [],
                "clarifications": ["Stub: Confirm interpretation with the tender schedule."],
            }

        logger.info("chat_orchestrate.end cid=%s", req.conversation_id)
        return ChatOrchestrateResult(
            user_message=user_msg,
            assistant_message=assistant_msg,
            dedupe=dedupe_obj,
            categorization=cat_obj,
            insights=insights_obj,
        )
