from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional
import hashlib


@dataclass(frozen=True)
class LlmPrompt:
    """Prompt for a self-hosted LLM call."""
    system: str
    user: str
    context: Optional[str] = None


@dataclass(frozen=True)
class LlmResult:
    """Result of a self-hosted LLM call."""
    text: str
    token_count: int


class LlmAdapter(Protocol):
    """Protocol for self-hosted LLM adapters (no external network calls)."""

    # PUBLIC_INTERFACE
    def generate(self, prompt: LlmPrompt) -> LlmResult:
        """Generate a response.

        Contract:
        - Must not call external AI services.
        - Must be deterministic in stub/testing modes.
        """


class DeterministicStubLlmAdapter:
    """A deterministic local-only adapter used until a real on-prem model is wired.

    It produces a stable response derived from the prompt hash so:
    - downstream flows can be implemented end-to-end
    - OpenAPI + UI can be exercised
    """

    # PUBLIC_INTERFACE
    def generate(self, prompt: LlmPrompt) -> LlmResult:
        """Generate a deterministic assistant response without external calls."""
        h = hashlib.sha256(
            (prompt.system + "\n" + prompt.user + "\n" + (prompt.context or "")).encode("utf-8")
        ).hexdigest()[:12]
        text = (
            "This is a self-hosted LLM stub response.\n"
            f"prompt_hash={h}\n"
            "Next step: wire an on-prem inference service behind this adapter."
        )
        # token_count is a placeholder; in real adapter compute from tokenizer.
        return LlmResult(text=text, token_count=len(text.split()))
