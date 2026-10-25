"""
Router de autenticação — magic links sem senha
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr

from database import get_database
from auth_utils import create_access_token, create_magic_link_token, get_current_user
from services.email_service import send_magic_link

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["autenticação"])


class MagicLinkRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    company_id: str
    name: str
    role: str


@router.post("/magic-link")
async def request_magic_link(data: MagicLinkRequest):
    """
    Solicita um magic link para o email informado.
    Se o usuário existir, envia o link. Se não existir, retorna erro genérico
    (não revelamos se o email está cadastrado por segurança).
    """
    db = get_database()
    user = await db.users.find_one({"email": data.email.lower()})

    if user:
        token = create_magic_link_token()
        expires = datetime.utcnow() + timedelta(minutes=30)

        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"magic_link_token": token, "magic_link_expires": expires}},
        )

        await send_magic_link(
            email=user["email"],
            name=user["name"],
            token=token,
        )

    # Sempre retorna sucesso (não revelar se email existe)
    return {"message": "Se o email estiver cadastrado, você receberá o link em instantes."}


@router.get("/verify/{token}", response_model=TokenResponse)
async def verify_magic_link(token: str):
    """
    Verifica o magic link e retorna o JWT de acesso.
    O token expira em 30 minutos e é de uso único.
    """
    db = get_database()
    user = await db.users.find_one({"magic_link_token": token})

    if not user:
        raise HTTPException(status_code=400, detail="Link inválido ou já utilizado")

    if user["magic_link_expires"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Link expirado. Solicite um novo.")

    # Invalida o token (uso único)
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {
                "magic_link_token": None,
                "magic_link_expires": None,
                "last_login": datetime.utcnow(),
            }
        },
    )

    access_token = create_access_token(user["user_id"], user["company_id"])

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user["user_id"],
        "company_id": user["company_id"],
        "name": user["name"],
        "role": user["role"],
    }


@router.get("/dev-token")
async def dev_get_token(email: str):
    """DEBUG ONLY — retorna magic link token para testes. Remover antes de ir a público."""
    from config import settings
    db = get_database()
    user = await db.users.find_one({"email": email.lower()}, {"magic_link_token": 1, "_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return {"token": user.get("magic_link_token"), "verify_url": f"{settings.app_url}/auth/verify/{user.get('magic_link_token')}"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Retorna os dados do usuário logado."""
    return {
        "user_id": current_user["user_id"],
        "company_id": current_user["company_id"],
        "name": current_user["name"],
        "email": current_user["email"],
        "role": current_user["role"],
        "last_login": current_user.get("last_login"),
    }


@router.post("/logout")
async def logout():
    """Logout — no frontend basta remover o token do localStorage."""
    return {"message": "Sessão encerrada com sucesso."}
