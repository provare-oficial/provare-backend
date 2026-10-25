"""
Router do Dashboard — métricas, projetos recentes e feed de atividade
"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from database import get_database
from auth_utils import get_current_user, get_current_company

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """
    Retorna dados do dashboard: métricas, projetos recentes e feed de atividade.
    """
    db = get_database()
    company_id = company["company_id"]

    # ── Métricas ──────────────────────────────────────────────────────────
    total = await db.projects.count_documents({"company_id": company_id, "deleted": {"$ne": True}})
    active = await db.projects.count_documents({"company_id": company_id, "status": "ativo", "deleted": {"$ne": True}})
    completed = await db.projects.count_documents({"company_id": company_id, "status": "concluido", "deleted": {"$ne": True}})

    # Books enviados: total de entradas na coleção book_sends
    books_sent = await db.book_sends.count_documents({"company_id": company_id})

    # Aceites pendentes: projects com book_sent=True mas accepted=False
    pending_acceptances = await db.projects.count_documents({
        "company_id": company_id,
        "book_sent": True,
        "accepted": {"$ne": True},
        "deleted": {"$ne": True},
    })

    metrics = {
        "total_projects": total,
        "active_projects": active,
        "completed_projects": completed,
        "books_sent": books_sent,
        "pending_acceptances": pending_acceptances,
        "avg_satisfaction": None,  # Futuro: calcular a partir de reviews
    }

    # ── Projetos recentes ─────────────────────────────────────────────────
    cursor = db.projects.find(
        {"company_id": company_id, "deleted": {"$ne": True}},
        {"_id": 0, "project_id": 1, "title": 1, "client_name": 1, "status": 1,
         "current_phase": 1, "progress": 1, "created_at": 1}
    ).sort("created_at", -1).limit(5)

    recent_projects = []
    async for p in cursor:
        recent_projects.append({
            "id": p.get("project_id"),
            "title": p.get("title"),
            "client_name": p.get("client_name"),
            "status": p.get("status", "ativo"),
            "current_phase": p.get("current_phase", ""),
            "progress": p.get("progress", 0),
        })

    # ── Feed de atividade ─────────────────────────────────────────────────
    # Busca eventos recentes: fases avançadas, books enviados, aceites
    activity = []

    # Fases avançadas recentemente
    phase_cursor = db.phases.find(
        {"company_id": company_id, "status": "done", "completed_at": {"$exists": True}},
        {"_id": 0, "name": 1, "project_title": 1, "completed_at": 1}
    ).sort("completed_at", -1).limit(5)
    async for ph in phase_cursor:
        activity.append({
            "icon": "✓",
            "message": f"Fase '{ph.get('name')}' concluída — {ph.get('project_title', '')}",
            "time": _format_time(ph.get("completed_at")),
            "ts": ph.get("completed_at"),
        })

    # Books enviados recentemente
    book_cursor = db.book_sends.find(
        {"company_id": company_id},
        {"_id": 0, "project_title": 1, "sent_at": 1, "client_name": 1}
    ).sort("sent_at", -1).limit(5)
    async for b in book_cursor:
        activity.append({
            "icon": "📲",
            "message": f"Book enviado para {b.get('client_name', '')} — {b.get('project_title', '')}",
            "time": _format_time(b.get("sent_at")),
            "ts": b.get("sent_at"),
        })

    # Aceites recebidos
    accept_cursor = db.projects.find(
        {"company_id": company_id, "accepted": True, "accepted_at": {"$exists": True}},
        {"_id": 0, "client_name": 1, "title": 1, "accepted_at": 1}
    ).sort("accepted_at", -1).limit(5)
    async for a in accept_cursor:
        activity.append({
            "icon": "✍",
            "message": f"Aceite recebido de {a.get('client_name', '')} — {a.get('title', '')}",
            "time": _format_time(a.get("accepted_at")),
            "ts": a.get("accepted_at"),
        })

    # Ordena por timestamp e pega os 8 mais recentes
    activity.sort(key=lambda x: x.get("ts") or datetime.min, reverse=True)
    recent_activity = [{"icon": a["icon"], "message": a["message"], "time": a["time"]} for a in activity[:8]]

    return {
        "metrics": metrics,
        "recent_projects": recent_projects,
        "recent_activity": recent_activity,
    }


def _format_time(dt: datetime | None) -> str:
    """Formata datetime como 'há X minutos/horas/dias'."""
    if not dt:
        return ""
    now = datetime.utcnow()
    diff = now - dt
    if diff < timedelta(minutes=1):
        return "agora"
    if diff < timedelta(hours=1):
        m = int(diff.total_seconds() / 60)
        return f"há {m} min"
    if diff < timedelta(days=1):
        h = int(diff.total_seconds() / 3600)
        return f"há {h}h"
    d = diff.days
    return f"há {d} dia{'s' if d > 1 else ''}"
