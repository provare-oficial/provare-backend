"""
Router de mídias (fotos e vídeos) — upload para Cloudflare R2
"""
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query

from database import get_database
from auth_utils import get_current_company
from models.media import MediaUpdate, build_media_doc
from services.storage_service import upload_file, delete_file

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/media", tags=["mídias"])

ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/heic"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime", "video/mov"]
MAX_IMAGE_SIZE = 20 * 1024 * 1024   # 20MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200MB


def _serialize(doc: dict) -> dict:
    doc.pop("_id", None)
    doc.pop("deleted", None)
    return doc


@router.get("")
async def list_media(
    project_id: str,
    phase_id: Optional[str] = Query(None),
    media_type: Optional[str] = Query(None),
    in_book_only: bool = Query(False),
    company: dict = Depends(get_current_company),
):
    """Lista mídias de um projeto, com filtros opcionais."""
    db = get_database()
    query = {
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    }
    if phase_id:
        query["phase_id"] = phase_id
    if media_type:
        query["type"] = media_type
    if in_book_only:
        query["include_in_book"] = True

    cursor = db.media.find(query).sort("uploaded_at", -1)
    items = await cursor.to_list(length=500)
    return [_serialize(m) for m in items]


@router.post("", status_code=201)
async def upload_media(
    project_id: str,
    file: UploadFile = File(...),
    phase_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    company: dict = Depends(get_current_company),
):
    """
    Faz upload de foto ou vídeo para o Cloudflare R2.
    Detecta o tipo automaticamente pelo content-type.
    """
    db = get_database()

    # Verifica projeto
    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    content_type = file.content_type or ""
    is_image = content_type in ALLOWED_IMAGE_TYPES
    is_video = content_type in ALLOWED_VIDEO_TYPES

    if not is_image and not is_video:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {content_type}. Use JPG, PNG, WEBP, MP4 ou MOV."
        )

    contents = await file.read()
    max_size = MAX_VIDEO_SIZE if is_video else MAX_IMAGE_SIZE

    if len(contents) > max_size:
        limit_mb = max_size // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"Arquivo muito grande. Máximo {limit_mb}MB.")

    # Gera nome único para evitar colisões
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else ("mp4" if is_video else "jpg")
    unique_name = f"{uuid.uuid4().hex}.{ext}"

    # Upload para R2
    url = await upload_file(
        file_bytes=contents,
        filename=unique_name,
        company_id=company["company_id"],
        project_id=project_id,
        content_type=content_type,
    )

    media_type = "video" if is_video else "photo"
    doc = build_media_doc(
        project_id=project_id,
        company_id=company["company_id"],
        phase_id=phase_id,
        media_type=media_type,
        filename=unique_name,
        url=url,
        size_bytes=len(contents),
    )

    if caption:
        doc["caption"] = caption

    await db.media.insert_one(doc)

    # Atualiza contador de fotos na fase, se houver
    if phase_id and is_image:
        await db.phases.update_one(
            {"phase_id": phase_id},
            {"$inc": {"photo_count": 1}},
        )

    logger.info(f"Mídia enviada: {unique_name} ({media_type}) — projeto {project_id}")
    return _serialize(doc)


@router.put("/{media_id}")
async def update_media(
    project_id: str,
    media_id: str,
    data: MediaUpdate,
    company: dict = Depends(get_current_company),
):
    """Atualiza legenda ou inclusão no Book."""
    db = get_database()
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")

    result = await db.media.update_one(
        {"media_id": media_id, "project_id": project_id, "company_id": company["company_id"]},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")
    return {"message": "Mídia atualizada."}


@router.post("/{media_id}/toggle-book")
async def toggle_in_book(
    project_id: str,
    media_id: str,
    company: dict = Depends(get_current_company),
):
    """Alterna se a mídia aparece ou não no Provare Book."""
    db = get_database()
    media = await db.media.find_one({"media_id": media_id, "company_id": company["company_id"]})
    if not media:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")

    new_value = not media.get("include_in_book", True)
    await db.media.update_one({"media_id": media_id}, {"$set": {"include_in_book": new_value}})
    return {"include_in_book": new_value}


@router.delete("/{media_id}")
async def delete_media(
    project_id: str,
    media_id: str,
    company: dict = Depends(get_current_company),
):
    """Remove a mídia do banco e do R2."""
    db = get_database()
    media = await db.media.find_one({
        "media_id": media_id,
        "project_id": project_id,
        "company_id": company["company_id"],
    })
    if not media:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")

    # Remove do R2
    await delete_file(media["url"])

    # Soft delete no banco
    await db.media.update_one({"media_id": media_id}, {"$set": {"deleted": True}})

    # Decrementa contador na fase
    if media.get("phase_id") and media.get("type") == "photo":
        await db.phases.update_one(
            {"phase_id": media["phase_id"]},
            {"$inc": {"photo_count": -1}},
        )

    return {"message": "Mídia removida."}
