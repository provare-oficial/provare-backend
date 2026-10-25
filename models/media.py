"""
Modelo de Mídia (fotos e vídeos) do Provare
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class MediaUpdate(BaseModel):
    caption: Optional[str] = None
    include_in_book: Optional[bool] = None


class MediaResponse(BaseModel):
    media_id: str
    project_id: str
    phase_id: Optional[str] = None
    company_id: str
    type: str
    filename: str
    url: str
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    include_in_book: bool
    size_bytes: int
    uploaded_at: datetime


def build_media_doc(
    project_id: str,
    company_id: str,
    phase_id: Optional[str],
    media_type: str,
    filename: str,
    url: str,
    size_bytes: int,
    thumbnail_url: Optional[str] = None,
) -> dict:
    """Constrói o documento de mídia para inserção no MongoDB."""
    return {
        "media_id": str(uuid.uuid4()),
        "project_id": project_id,
        "phase_id": phase_id,
        "company_id": company_id,
        "type": media_type,  # "photo" ou "video"
        "filename": filename,
        "url": url,
        "thumbnail_url": thumbnail_url,
        "caption": None,
        "include_in_book": True,  # Por padrão inclui no Book
        "size_bytes": size_bytes,
        "uploaded_at": datetime.utcnow(),
        "deleted": False,
    }
