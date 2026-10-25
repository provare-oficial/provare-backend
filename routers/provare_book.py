"""
Router do Provare Book — documento do cliente e envio por WhatsApp
"""
import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional

from database import get_database
from auth_utils import get_current_user, get_current_company
from services.ai_service import generate_whatsapp_message
from services.qr_service import generate_qr_code_base64, get_verify_url
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["provare book"])


class SendBookRequest(BaseModel):
    message_text: str
    was_edited: bool = False


class AcceptBookRequest(BaseModel):
    accepted_by: Optional[str] = None   # Nome de quem assinou
    signer_name: Optional[str] = None   # Alias frontend (ProvarBookPage.jsx usa signer_name)


# ─── ROTAS PÚBLICAS (sem autenticação — cliente acessa) ───────────────────────

@router.get("/book/{book_slug}")
async def get_provare_book(book_slug: str, request: Request):
    """
    Retorna os dados do Provare Book para o cliente.
    Endpoint público — acessado via link enviado por WhatsApp.
    Nunca retorna dados internos (notas, financeiro se desativado, etc.)
    """
    db = get_database()

    project = await db.projects.find_one({"book_slug": book_slug, "deleted": {"$ne": True}})
    if not project:
        raise HTTPException(status_code=404, detail="Provare Book não encontrado")

    company = await db.companies.find_one({"company_id": project["company_id"]})
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    # Fases (sem notas internas)
    phases_cursor = db.phases.find(
        {"project_id": project["project_id"], "company_id": project["company_id"]}
    ).sort("index", 1)
    phases_raw = await phases_cursor.to_list(length=100)
    phases = []
    for p in phases_raw:
        phases.append({
            "phase_id": p["phase_id"],
            "index": p["index"],
            "title": p["title"],
            "description": p.get("description"),
            # internal_notes NUNCA vai para o cliente
            "status": p["status"],
            "started_at": p.get("started_at"),
            "completed_at": p.get("completed_at"),
            "photo_count": p.get("photo_count", 0),
        })

    # Mídias marcadas para incluir no Book
    media_cursor = db.media.find({
        "project_id": project["project_id"],
        "company_id": project["company_id"],
        "include_in_book": True,
        "deleted": {"$ne": True},
    }).sort("uploaded_at", 1)
    media = await media_cursor.to_list(length=200)
    media_clean = [
        {
            "media_id": m["media_id"],
            "phase_id": m.get("phase_id"),
            "type": m["type"],
            "url": m["url"],
            "caption": m.get("caption"),
            "uploaded_at": m["uploaded_at"],
        }
        for m in media
    ]

    # Registra visualização
    await db.book_sends.update_many(
        {"project_id": project["project_id"], "first_read_at": None},
        {"$set": {"first_read_at": datetime.utcnow()}, "$inc": {"read_count": 1}},
    )

    # Monta resposta
    response = {
        "project_id": project["project_id"],
        "book_slug": book_slug,
        "title": project["title"],
        "client_name": project["client_name"],
        "status": project["status"],
        "current_phase_index": project["current_phase_index"],
        "total_phases": project["total_phases"],
        "start_date": project.get("start_date"),
        "estimated_end_date": project.get("estimated_end_date"),
        "book_accepted_at": project.get("book_accepted_at"),
        "phases": phases,
        "media": media_clean,
        "qr_code": generate_qr_code_base64(book_slug),
        "verify_url": get_verify_url(book_slug),
        "generated_at": datetime.utcnow().isoformat(),
        # Dados da empresa (white-label)
        "company": {
            "name": company["name"],
            "logo_url": company.get("logo_url"),
            "primary_color": company.get("primary_color", "#C9A84C"),
            "secondary_color": company.get("secondary_color", "#0A0A0A"),
            "whatsapp": company.get("whatsapp"),
        },
    }

    # Financeiro — só se o operador habilitou
    if project.get("include_financial_in_book"):
        total = project.get("total_value") or 0
        paid = project.get("paid_amount") or 0
        response["financial"] = {
            "total_value": total,
            "paid_amount": paid,
            "balance_due": max(0, total - paid),
        }

    return response


@router.post("/book/{book_slug}/view")
async def register_book_view(book_slug: str, request: Request):
    """
    Registra uma visualização do Provare Book pelo cliente.
    Endpoint público — chamado automaticamente pelo ProvarBookPage.jsx.
    """
    db = get_database()
    project = await db.projects.find_one({"book_slug": book_slug, "deleted": {"$ne": True}})
    if not project:
        return {"ok": True}  # Retorna OK mesmo se não encontrar (não bloqueia a leitura)

    now = datetime.utcnow()
    # Incrementa contador de visualizações do projeto
    await db.projects.update_one(
        {"project_id": project["project_id"]},
        {"$inc": {"book_view_count": 1}, "$set": {"book_last_viewed_at": now}},
    )

    return {"ok": True}


@router.post("/book/{book_slug}/accept")
async def accept_provare_book(book_slug: str, data: AcceptBookRequest):
    """
    Registra o aceite digital do cliente.
    Endpoint público — o cliente assina no próprio celular.
    """
    db = get_database()

    project = await db.projects.find_one({"book_slug": book_slug, "deleted": {"$ne": True}})
    if not project:
        raise HTTPException(status_code=404, detail="Provare Book não encontrado")

    if project.get("book_accepted_at"):
        return {
            "message": "Este Provare Book já foi aceito.",
            "accepted_at": project["book_accepted_at"],
            "accepted_by": project.get("book_accepted_by"),
        }

    signer = data.signer_name or data.accepted_by or "Anônimo"
    now = datetime.utcnow()
    await db.projects.update_one(
        {"project_id": project["project_id"]},
        {"$set": {
            "book_accepted_at": now,
            "book_accepted_by": signer,
            "accepted": True,
            "accepted_at": now,
            "updated_at": now,
        }},
    )

    logger.info(f"Provare Book aceito: {book_slug} por {signer}")
    return {
        "message": "Aceite registrado com sucesso.",
        "accepted_at": now.isoformat(),
        "accepted_by": signer,
        "book_slug": book_slug,
    }


# ─── ROTAS AUTENTICADAS (operador) ────────────────────────────────────────────

@router.get("/projects/{project_id}/book/history")
async def get_book_history(
    project_id: str,
    company: dict = Depends(get_current_company),
):
    """Retorna o histórico de envios do Provare Book."""
    db = get_database()
    cursor = db.book_sends.find(
        {"project_id": project_id, "company_id": company["company_id"]}
    ).sort("sent_at", -1)
    sends = await cursor.to_list(length=50)
    for s in sends:
        s.pop("_id", None)
    return sends


@router.post("/projects/{project_id}/book/generate-message")
async def generate_book_message(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """
    Gera mensagem WhatsApp via IA para envio do Provare Book.
    Cada mensagem é única — nunca repete o estilo das anteriores.
    """
    db = get_database()

    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    # Fase atual
    current_phase = await db.phases.find_one({
        "project_id": project_id,
        "index": project.get("current_phase_index", 0),
    })
    phase_title = current_phase["title"] if current_phase else None

    # Histórico de mensagens anteriores
    prev_sends = await db.book_sends.find(
        {"project_id": project_id}
    ).sort("sent_at", -1).to_list(5)
    previous_messages = [s["message_text"] for s in prev_sends]

    is_first = project.get("book_sent_count", 0) == 0
    book_url = f"{settings.app_url}/book/{project['book_slug']}"

    # Horário de Brasília
    from datetime import timezone, timedelta
    brasilia = datetime.now(timezone(timedelta(hours=-3)))
    time_str = brasilia.strftime("%H:%M · %d/%m/%Y")

    message = await generate_whatsapp_message(
        company_name=company["name"],
        company_industry=company.get("industry", "serviço premium"),
        client_name=project["client_name"],
        project_title=project["title"],
        current_phase_title=phase_title,
        is_first_send=is_first,
        previous_messages=previous_messages,
        book_url=book_url,
        current_time_brasilia=time_str,
    )

    return {
        "message": message,
        "book_url": book_url,
        "is_first_send": is_first,
        "whatsapp_url": f"https://wa.me/{project.get('client_whatsapp', '').replace('+', '').replace(' ', '')}?text={__import__('urllib.parse', fromlist=['quote']).quote(message)}" if project.get("client_whatsapp") else None,
    }


@router.post("/projects/{project_id}/book/send")
async def register_book_send(
    project_id: str,
    data: SendBookRequest,
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """Registra no histórico que o Book foi enviado."""
    db = get_database()

    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    current_phase = await db.phases.find_one({
        "project_id": project_id,
        "index": project.get("current_phase_index", 0),
    })

    now = datetime.utcnow()
    send_doc = {
        "send_id": str(uuid.uuid4()),
        "project_id": project_id,
        "company_id": company["company_id"],
        "message_text": data.message_text,
        "sent_by_user_id": current_user["user_id"],
        "sent_at": now,
        "was_edited": data.was_edited,
        "phase_at_send": current_phase["title"] if current_phase else None,
        "read_count": 0,
        "first_read_at": None,
    }
    await db.book_sends.insert_one(send_doc)

    # Atualiza contadores no projeto
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"book_last_sent_at": now, "updated_at": now}, "$inc": {"book_sent_count": 1}},
    )

    send_doc.pop("_id", None)
    return send_doc
