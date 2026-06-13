from pydantic import BaseModel


class RagIngestionResponse(BaseModel):
    """Summary returned after rebuilding the local RAG index."""

    collection_name: str
    document_count: int
    chunk_count: int
