"""
Modelo de Projeto do Provare
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid
import secrets


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    client_name: str = Field(..., min_length=2)
    client_email: Optional[str] = None
    client_whatsapp: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    start_date: Optional[datetime] = None
    estimated_end_date: Optional[datetime] = None
    total_value: Optional[float] = None
    architect_name: Optional[str] = None
    architect_email: Optional[str] = None
    include_financial_in_book: bool = False


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    client_whatsapp: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    estimated_end_date: Optional[datetime] = None
    total_value: Optional[float] = None
    paid_amount: Optional[float] = None
    architect_name: Optional[str] = None
    architect_email: Optional[str] = None
    include_financial_in_book: Optional[bool] = None
    status: Optional[Literal["active", "completed", "paused", "canceled"]] = None


class ProjectResponse(BaseModel):
    project_id: str
    company_id: str
    title: str
    client_name: str
    client_email: Optional[str] = None
    client_whatsapp: Optional[str] = None
    description: Optional[str] = None
    status: str
    current_phase_index: int
    total_phases: int
    progress_percent: float
    address: Optional[str] = None
    start_date: Optional[datetime] = None
    estimated_end_date: Optional[datetime] = None
    completed_date: Optional[datetime] = None
    include_financial_in_book: bool
    total_value: Optional[float] = None
    paid_amount: Optional[float] = None
    balance_due: Optional[float] = None
    architect_name: Optional[str] = None
    book_slug: str
    book_sent_count: int
    book_last_sent_at: Optional[datetime] = None
    book_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


def build_project_doc(company_id: str, data: ProjectCreate) -> dict:
    """Constrói o documento do projeto para inserção no MongoDB."""
    now = datetime.utcnow()
    book_slug = secrets.token_urlsafe(10)

    return {
        "project_id": str(uuid.uuid4()),
        "company_id": company_id,
        "title": data.title,
        "client_name": data.client_name,
        "client_email": data.client_email,
        "client_whatsapp": data.client_whatsapp,
        "description": data.description,
        "status": "active",
        "current_phase_index": 0,
        "total_phases": 0,
        "address": data.address,
        "start_date": data.start_date or now,
        "estimated_end_date": data.estimated_end_date,
        "completed_date": None,
        "include_financial_in_book": data.include_financial_in_book,
        "total_value": data.total_value,
        "paid_amount": 0.0,
        "architect_name": data.architect_name,
        "architect_email": data.architect_email,
        "book_slug": book_slug,
        "book_sent_count": 0,
        "book_last_sent_at": None,
        "book_accepted_at": None,
        "book_accepted_by": None,
        "created_at": now,
        "updated_at": now,
        "deleted": False,
    }
