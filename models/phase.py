"""
Modelo de Fase do Provare
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class PhaseCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    internal_notes: Optional[str] = None


class PhaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    internal_notes: Optional[str] = None
    status: Optional[Literal["pending", "active", "completed"]] = None


class PhaseResponse(BaseModel):
    phase_id: str
    project_id: str
    company_id: str
    index: int
    title: str
    description: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    photo_count: int
    created_at: datetime


def build_phase_doc(project_id: str, company_id: str, data: PhaseCreate, index: int) -> dict:
    """Constrói o documento da fase para inserção no MongoDB."""
    return {
        "phase_id": str(uuid.uuid4()),
        "project_id": project_id,
        "company_id": company_id,
        "index": index,
        "title": data.title,
        "description": data.description,
        "internal_notes": data.internal_notes,  # NUNCA vai para o Provare Book
        "status": "pending",
        "started_at": None,
        "completed_at": None,
        "photo_count": 0,
        "created_at": datetime.utcnow(),
    }
