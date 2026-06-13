from dataclasses import dataclass


@dataclass(frozen=True)
class ConversationMessage:
    """One chat message sent to the local LLM."""

    role: str
    content: str


@dataclass(frozen=True)
class RetrievedPassage:
    """One context passage retrieved from the vector store."""

    content: str
    source_path: str = "unknown"
    distance: float | None = None
    heading: str | None = None
    section_slug: str | None = None
