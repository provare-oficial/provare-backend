"""
Router de empresas (tenants) — registro e configurações
"""
import logging
import uuid
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from typing import Optional
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


@router.post("/onboarding", status_code=201)
async def onboarding(
    company_name: str = Form(...),
    user_name: str = Form(...),
    email: str = Form(...),
    segment: str = Form("outro"),
    whatsapp: Optional[str] = Form(None),
    primary_color: str = Form("#C9A84C"),
    plan: str = Form("pro"),
    logo: Optional[UploadFile] = File(None),
):
    """
    Endpoint público de onboarding — cria empresa + usuário em um único passo.
    Chamado pela OnboardingPage.jsx.
    """
    import re
    from datetime import timedelta

    db = get_database()

    # Normaliza email
    email_lower = email.lower().strip()

    # Verifica se email já existe
    existing = await db.users.find_one({"email": email_lower})
    if existing:
        raise HTTPException(status_code=400, detail="Este email já está cadastrado. Faça login.")

    # Mapeia segmento para industry (modelo usa enum em inglês/português)
    segment_map = {
        "marmoraria": "marmoraria",
        "marcenaria": "marcenaria",
        "reforma": "reforma",
        "revestimento": "revestimento",
        "outro": "outro",
    }
    industry = segment_map.get(segment.lower(), "outro")

    # Cria slug da empresa
    slug = re.sub(r'[^a-z0-9]', '-', company_name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    base_slug = slug
    counter = 1
    while await db.companies.find_one({"slug": slug}):
        slug = f"{base_slug}-{counter}"
        counter += 1

    company_id = str(uuid.uuid4())
    now = datetime.utcnow()

    company_doc = {
        "company_id": company_id,
        "name": company_name,
        "slug": slug,
        "email": email_lower,
        "logo_url": None,
        "primary_color": primary_color,
        "secondary_color": "#0A0A0A",
        "plan": plan,
        "plan_status": "trial",
        "trial_ends_at": now + timedelta(days=7),
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "industry": industry,
        "segment": segment,
        "whatsapp": whatsapp,
        "website": None,
        "created_at": now,
    }

    # Upload logo se fornecido
    if logo and logo.filename:
        logo_bytes = await logo.read()
        if len(logo_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo muito grande. Máximo 5MB.")
        ext = logo.filename.rsplit(".", 1)[-1].lower() if "." in logo.filename else "png"
        logo_url = await upload_file(
            file_bytes=logo_bytes,
            filename=f"logo.{ext}",
            company_id=company_id,
            project_id="assets",
            content_type=logo.content_type,
        )
        company_doc["logo_url"] = logo_url

    await db.companies.insert_one(company_doc)

    # Cria usuário owner
    user_doc = build_user_doc(
        company_id=company_id,
        name=user_name,
        email=email_lower,
        role="owner",
    )
    await db.users.insert_one(user_doc)

    logger.info(f"Onboarding completo: {company_name} ({company_id})")

    return {
        "message": "Conta criada! Verifique seu email para fazer login.",
        "company_id": company_id,
        "company_name": company_name,
        "email": email_lower,
    }


@router.patch("/settings")
async def patch_company(
    name: Optional[str] = Form(None),
    segment: Optional[str] = Form(None),
    whatsapp: Optional[str] = Form(None),
    primary_color: Optional[str] = Form(None),
    logo: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """
    Atualiza dados da empresa via multipart/form-data (chamado pela SettingsPage).
    Suporta upload de logo junto com os dados.
    """
    db = get_database()
    update = {}

    if name is not None:
        update["name"] = name
    if segment is not None:
        update["segment"] = segment
    if whatsapp is not None:
        update["whatsapp"] = whatsapp
    if primary_color is not None:
        update["primary_color"] = primary_color

    # Upload logo se fornecido
    if logo and logo.filename:
        logo_bytes = await logo.read()
        if len(logo_bytes) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo muito grande. Máximo 5MB.")
        ext = logo.filename.rsplit(".", 1)[-1].lower() if "." in logo.filename else "png"
        logo_url = await upload_file(
            file_bytes=logo_bytes,
            filename=f"logo.{ext}",
            company_id=company["company_id"],
            project_id="assets",
            content_type=logo.content_type,
        )
        update["logo_url"] = logo_url

    if update:
        update["updated_at"] = datetime.utcnow()
        await db.companies.update_one(
            {"company_id": company["company_id"]},
            {"$set": update},
        )

    return {"message": "Configurações salvas."}


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
