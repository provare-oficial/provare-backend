"""
Router de fases dos projetos
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends

from database import get_database
from auth_utils import get_current_user, get_current_company
from models.phase import PhaseCreate, PhaseUpdate, build_phase_doc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}/phases", tags=["fases"])


async def _get_project_or_404(project_id: str, company_id: str, db):
    project = await db.projects.find_one({
        "project_id": project_id,
        "company_id": company_id,
        "deleted": {"$ne": True},
    })
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


def _serialize_phase(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


@router.get("")
async def list_phases(
    project_id: str,
    company: dict = Depends(get_current_company),
):
    """Lista todas as fases de um projeto, em ordem."""
    db = get_database()
    await _get_project_or_404(project_id, company["company_id"], db)

    cursor = db.phases.find(
        {"project_id": project_id, "company_id": company["company_id"]}
    ).sort("index", 1)
    phases = await cursor.to_list(length=100)
    return [_serialize_phase(p) for p in phases]


@router.post("", status_code=201)
async def create_phase(
    project_id: str,
    data: PhaseCreate,
    company: dict = Depends(get_current_company),
):
    """Cria uma nova fase no projeto."""
    db = get_database()
    project = await _get_project_or_404(project_id, company["company_id"], db)

    # Próximo índice
    count = await db.phases.count_documents({"project_id": project_id})
    doc = build_phase_doc(project_id, company["company_id"], data, index=count)

    await db.phases.insert_one(doc)

    # Atualiza total_phases no projeto
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"total_phases": count + 1, "updated_at": datetime.utcnow()}},
    )

    return _serialize_phase(doc)


@router.put("/{phase_id}")
async def update_phase(
    project_id: str,
    phase_id: str,
    data: PhaseUpdate,
    company: dict = Depends(get_current_company),
):
    """Atualiza dados de uma fase."""
    db = get_database()
    await _get_project_or_404(project_id, company["company_id"], db)

    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="Nenhum dado para atualizar.")

    result = await db.phases.update_one(
        {"phase_id": phase_id, "project_id": project_id, "company_id": company["company_id"]},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fase não encontrada")
    return {"message": "Fase atualizada."}


@router.post("/{phase_id}/advance")
async def advance_phase(
    project_id: str,
    phase_id: str,
    company: dict = Depends(get_current_company),
):
    """
    Marca a fase atual como concluída e ativa a próxima.
    Atualiza current_phase_index no projeto.
    """
    db = get_database()
    project = await _get_project_or_404(project_id, company["company_id"], db)

    # Conclui a fase atual
    now = datetime.utcnow()
    result = await db.phases.update_one(
        {"phase_id": phase_id, "project_id": project_id, "company_id": company["company_id"]},
        {"$set": {"status": "completed", "completed_at": now}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Fase não encontrada")

    # Ativa a próxima fase
    current_index = project.get("current_phase_index", 0)
    next_index = current_index + 1
    total = project.get("total_phases", 0)

    next_phase = await db.phases.find_one(
        {"project_id": project_id, "index": next_index, "company_id": company["company_id"]}
    )
    if next_phase:
        await db.phases.update_one(
            {"phase_id": next_phase["phase_id"]},
            {"$set": {"status": "active", "started_at": now}},
        )

    # Atualiza o projeto
    is_last = next_index >= total
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {
            "current_phase_index": next_index,
            "status": "completed" if is_last else "active",
            "completed_date": now if is_last else None,
            "updated_at": now,
        }},
    )

    return {
        "message": "Fase concluída." + (" Projeto finalizado." if is_last else " Próxima fase ativada."),
        "project_completed": is_last,
    }


@router.delete("/{phase_id}")
async def delete_phase(
    project_id: str,
    phase_id: str,
    company: dict = Depends(get_current_company),
):
    """Remove uma fase (apenas se estiver pendente)."""
    db = get_database()
    phase = await db.phases.find_one({"phase_id": phase_id, "company_id": company["company_id"]})

    if not phase:
        raise HTTPException(status_code=404, detail="Fase não encontrada")
    if phase["status"] != "pending":
        raise HTTPException(status_code=400, detail="Só é possível remover fases pendentes.")

    await db.phases.delete_one({"phase_id": phase_id})

    # Atualiza total_phases
    count = await db.phases.count_documents({"project_id": project_id})
    await db.projects.update_one(
        {"project_id": project_id},
        {"$set": {"total_phases": count, "updated_at": datetime.utcnow()}},
    )
    return {"message": "Fase removida."}
