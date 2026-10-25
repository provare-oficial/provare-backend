"""
Router de empresas (tenants) — registro e configurações
"""
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from datetime import datetime

from database import get_database
from auth_utils import get_current_user, get_current_company
from models.company import CompanyCreate, CompanyUpdate, CompanyResponse, build_company_doc
from models.user import build_user_doc
from services.storage_service import upload_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/companies", tags=["empresas"])


@router.post("/register", status_code=201)
async def register_company(data: CompanyCreate):
    """
    Registra uma nova empresa e seu usuário owner.
    Este endpoint é público — usado no onboarding.
    """
    db = get_database()

    # Verifica se email já existe
    existing = await db.users.find_one({"email": data.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado.")

    # Cria a empresa
    company_doc = build_company_doc(data)

    # Garante slug único
    base_slug = company_doc["slug"]
    slug = base_slug
    counter = 1
    while await db.companies.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1
    company_doc["slug"] = slug

    await db.companies.insert_one(company_doc)

    # Cria o usuário owner
    user_doc = build_user_doc(
        company_id=company_doc["company_id"],
        name=data.owner_name,
        email=data.email.lower(),
        role="owner",
    )
    await db.users.insert_one(user_doc)

    logger.info(f"Nova empresa registrada: {data.name} ({company_doc['company_id']})")

    return {
        "message": "Empresa criada com sucesso! Verifique seu email para acessar.",
        "company_id": company_doc["company_id"],
        "company_name": company_doc["name"],
        "trial_ends_at": company_doc["trial_ends_at"],
    }


@router.get("/me", response_model=CompanyResponse)
async def get_my_company(company: dict = Depends(get_current_company)):
    """Retorna os dados da empresa do usuário logado."""
    return company


@router.put("/me")
async def update_my_company(
    data: CompanyUpdate,
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """Atualiza dados da empresa (nome, cores, setor, etc.)."""
    db = get_database()

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")

    update_data["updated_at"] = datetime.utcnow()

    await db.companies.update_one(
        {"company_id": company["company_id"]},
        {"$set": update_data},
    )

    return {"message": "Empresa atualizada com sucesso."}


@router.post("/me/logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """
    Faz upload do logo da empresa para o R2.
    Aceita PNG, JPG, SVG. Máximo 5MB.
    """
    if file.content_type not in ["image/png", "image/jpeg", "image/svg+xml", "image/webp"]:
        raise HTTPException(status_code=400, detail="Formato inválido. Use PNG, JPG ou SVG.")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo muito grande. Máximo 5MB.")

    ext = file.filename.split(".")[-1].lower()
    filename = f"logo.{ext}"

    logo_url = await upload_file(
        file_bytes=contents,
        filename=filename,
        company_id=company["company_id"],
        project_id="assets",
        content_type=file.content_type,
    )

    db = get_database()
    await db.companies.update_one(
        {"company_id": company["company_id"]},
        {"$set": {"logo_url": logo_url}},
    )

    return {"logo_url": logo_url}
