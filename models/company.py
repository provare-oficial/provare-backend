"""
Modelo de Empresa (tenant) do Provare
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    industry: Literal["marmoraria", "marcenaria", "reforma", "revestimento", "outro"] = "marmoraria"
    whatsapp: Optional[str] = None
    owner_name: str = Field(..., min_length=2)


class CompanyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    industry: Optional[Literal["marmoraria", "marcenaria", "reforma", "revestimento", "outro"]] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None


class CompanyResponse(BaseModel):
    company_id: str
    name: str
    slug: str
    email: str
    logo_url: Optional[str] = None
    primary_color: str
    secondary_color: str
    plan: str
    plan_status: str
    trial_ends_at: Optional[datetime] = None
    industry: str
    whatsapp: Optional[str] = None
    website: Optional[str] = None
    created_at: datetime


def build_company_doc(data: CompanyCreate) -> dict:
    """Constrói o documento completo da empresa para inserção no MongoDB."""
    import re
    from datetime import timedelta

    slug = re.sub(r'[^a-z0-9]', '-', data.name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')

    return {
        "company_id": str(uuid.uuid4()),
        "name": data.name,
        "slug": slug,
        "email": data.email,
        "logo_url": None,
        "primary_color": "#C9A84C",
        "secondary_color": "#0A0A0A",
        "plan": "starter",
        "plan_status": "trial",
        "trial_ends_at": datetime.utcnow() + timedelta(days=7),
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "industry": data.industry,
        "whatsapp": data.whatsapp,
        "website": None,
        "created_at": datetime.utcnow(),
    }
