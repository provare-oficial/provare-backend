"""
Modelo de Usuário do Provare
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class UserResponse(BaseModel):
    user_id: str
    company_id: str
    name: str
    email: str
    role: str
    last_login: Optional[datetime] = None
    created_at: datetime


def build_user_doc(company_id: str, name: str, email: str, role: str = "owner") -> dict:
    """Constrói o documento do usuário para inserção no MongoDB."""
    return {
        "user_id": str(uuid.uuid4()),
        "company_id": company_id,
        "name": name,
        "email": email,
        "role": role,
        "magic_link_token": None,
        "magic_link_expires": None,
        "last_login": None,
        "created_at": datetime.utcnow(),
    }
