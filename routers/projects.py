"""
Router de projetos — CRUD completo com isolamento multi-tenant
"""
import logging
from typing import Optional, Literal
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Query

from database import get_database
from auth_utils import get_current_user, get_current_company
from models.project import ProjectCreate, ProjectUpdate, build_project_doc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projetos"])


def _serialize(doc: dict) -> dict:
    """Prepara o documento do MongoDB para retorno (remove _id, calcula campos)."""
    doc.pop("_id", None)
    doc.pop("deleted", None)

    # Calcula progresso
    total = doc.get("total_phases", 0)
    current = doc.get("current_phase_index", 0)
    doc["progress_percent"] = round((current / total * 100) if total > 0 else 0, 1)

    # Calcula saldo
    total_val = doc.get("total_value") or 0
    paid = doc.get("paid_amount") or 0
    doc["balance_due"] = max(0, total_val - paid)

    return doc


@router.get("/stats")
async def get_stats(company: dict = Depends(get_current_company)):
    """Retorna métricas resumidas da empresa."""
    db = get_database()
    cid = company["company_id"]

    total = await db.projects.count_documents({"company_id": cid, "deleted": {"$ne": True}})
    active = await db.projects.count_documents({"company_id": cid, "status": "active", "deleted": {"$ne": True}})
    completed = await db.projects.count_documents({"company_id": cid, "status": "completed", "deleted": {"$ne": True}})

    # Total de books enviados
    pipeline = [
        {"$match": {"company_id": cid, "deleted": {"$ne": True}}},
        {"$group": {"_id": None, "total_sent": {"$sum": "$book_sent_count"}}},
    ]
    result = await db.projects.aggregate(pipeline).to_list(1)
    books_sent = result[0]["total_sent"] if result else 0

    # Projetos com aceite pendente
    pending_acceptance = await db.projects.count_documents({
        "company_id": cid,
        "status": "active",
        "book_sent_count": {"$gt": 0},
        "book_accepted_at": None,
        "deleted": {"$ne": True},
    })

    return {
        "total_projects": total,
        "active_projects": active,
        "completed_projects": completed,
        "books_sent": books_sent,
        "pending_acceptance": pending_acceptance,
    }


@router.get("")
async def list_projects(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    company: dict = Depends(get_current_company),
):
    """Lista projetos da empresa com filtros opcionais."""
    db = get_database()
    query = {"company_id": company["company_id"], "deleted": {"$ne": True}}

    if status:
        query["status"] = status

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"client_name": {"$regex": search, "$options": "i"}},
        ]

    cursor = db.projects.find(query).sort("created_at", -1).skip(skip).limit(limit)
    projects = await cursor.to_list(length=limit)

    return [_serialize(p) for p in projects]


@router.post("", status_code=201)
async def create_project(
    data: ProjectCreate,
    current_user: dict = Depends(get_current_user),
    company: dict = Depends(get_current_company),
):
    """Cria um novo projeto."""
    db = get_database()
    doc = build_project_doc(company["company_id"], data)
    await db.projects.insert_one(doc)
    logger.info(f"Projeto criado: {doc['project_id']} — {data.title}")
    return _serialize(doc)


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    company: dict = Depends(get_current_company),
):
    """Retorna detalhes de um projeto."""
    db = get_database()
    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return _serialize(project)


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    company: dict = Depends(get_current_company),
):
    """Atualiza dados de um projeto."""
    db = get_database()

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")

    update_data["updated_at"] = datetime.utcnow()

    result = await db.projects.update_one(
        {"project_id": project_id, "company_id": company["company_id"], "deleted": {"$ne": True}},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    return {"message": "Projeto atualizado com sucesso."}


@router.post("/{project_id}/advance-phase")
async def advance_phase_convenience(
    project_id: str,
    company: dict = Depends(get_current_company),
):
    """
    Rota de conveniência: avança a fase atual do projeto sem precisar do phase_id.
    Chamado pelo TabFases no ProjectDetailPage.jsx.
    """
    db = get_database()
    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    # Encontra a fase atual (status active ou current)
    current_phase = await db.phases.find_one({
        "project_id": project_id,
        "company_id": company["company_id"],
        "status": {"$in": ["active", "current"]},
    })

    # Se não há fase active, tenta a primeira com status diferente de done/completed
    if not current_phase:
        current_phase = await db.phases.find_one(
            {"project_id": project_id, "company_id": company["company_id"],
             "status": {"$nin": ["done", "completed"]}},
            sort=[("index", 1)],
        )

    if not current_phase:
        raise HTTPException(status_code=400, detail="Nenhuma fase em andamento.")

    now = datetime.utcnow()
    phase_id = current_phase["phase_id"]
    current_index = current_phase.get("index", 0)

    # Conclui a fase atual
    await db.phases.update_one(
        {"phase_id": phase_id},
        {"$set": {"status": "done", "completed_at": now}},
    )

    # Ativa a próxima fase
    next_phase = await db.phases.find_one(
        {"project_id": project_id, "company_id": company["company_id"],
         "index": current_index + 1},
    )
    if next_phase:
        await db.phases.update_one(
            {"phase_id": next_phase["phase_id"]},
            {"$set": {"status": "current", "started_at": now}},
        )
        next_phase_name = next_phase.get("name", "")
    else:
        next_phase_name = None

    # Atualiza progresso no projeto
    total_phases = project.get("total_phases", 0)
    new_index = current_index + 1
    progress = round((new_index / total_phases * 100) if total_phases > 0 else 100)
    is_last = next_phase is None

    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {
            "current_phase_index": new_index,
            "current_phase": next_phase_name or current_phase.get("name", ""),
            "progress": progress,
            "status": "concluido" if is_last else "ativo",
            "updated_at": now,
        }},
    )

    return {
        "message": "Fase concluída." + (" Projeto finalizado!" if is_last else f" Próxima fase: {next_phase_name}"),
        "project_completed": is_last,
        "next_phase": next_phase_name,
    }


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    company: dict = Depends(get_current_company),
):
    """Soft delete — projeto fica no banco mas não aparece mais."""
    db = get_database()
    result = await db.projects.update_one(
        {"project_id": project_id, "company_id": company["company_id"]},
        {"$set": {"deleted": True, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"message": "Projeto removido."}
