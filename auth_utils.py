"""
Utilitários de autenticação JWT e extração de usuário logado
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from config import settings
from database import get_database

security = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, company_id: str) -> str:
    """Cria um JWT com user_id e company_id."""
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "company_id": company_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_magic_link_token() -> str:
    """Gera token seguro para magic link."""
    return secrets.token_urlsafe(32)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """
    Extrai e valida o usuário logado do JWT.
    Levanta 401 se o token for inválido ou ausente.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticação não fornecido",
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        company_id: str = payload.get("company_id")
        if not user_id or not company_id:
            raise HTTPException(status_code=401, detail="Token inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    db = get_database()
    user = await db.users.find_one({"user_id": user_id, "company_id": company_id})
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    return user


async def get_current_company(current_user: dict = Depends(get_current_user)):
    """Retorna a empresa do usuário logado."""
    db = get_database()
    company = await db.companies.find_one({"company_id": current_user["company_id"]})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return company
