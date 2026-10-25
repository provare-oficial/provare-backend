"""
Conexão com MongoDB e criação de índices
"""
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings

logger = logging.getLogger(__name__)

# Cliente global
_client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None


def get_database() -> AsyncIOMotorDatabase:
    """Retorna a instância do banco de dados."""
    return _db


async def connect_db():
    """Conecta ao MongoDB e cria índices."""
    global _client, _db
    logger.info("Conectando ao MongoDB...")
    _client = AsyncIOMotorClient(settings.mongodb_url)
    _db = _client.provare
    await _create_indexes()
    logger.info("MongoDB conectado com sucesso.")


async def disconnect_db():
    """Fecha a conexão com o MongoDB."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB desconectado.")


async def _create_indexes():
    """Cria índices para performance e unicidade."""
    db = _db

    # Companies
    await db.companies.create_index("email", unique=True)
    await db.companies.create_index("slug", unique=True)
    await db.companies.create_index("stripe_customer_id", sparse=True)

    # Users
    await db.users.create_index([("email", 1), ("company_id", 1)])
    await db.users.create_index("magic_link_token", sparse=True)

    # Projects
    await db.projects.create_index([("company_id", 1), ("status", 1)])
    await db.projects.create_index([("company_id", 1), ("created_at", -1)])
    await db.projects.create_index("book_slug", unique=True, sparse=True)

    # Phases
    await db.phases.create_index([("project_id", 1), ("index", 1)])
    await db.phases.create_index("company_id")

    # Media
    await db.media.create_index([("project_id", 1), ("uploaded_at", -1)])
    await db.media.create_index("phase_id")
    await db.media.create_index("company_id")

    # Book sends (histórico de envios)
    await db.book_sends.create_index([("project_id", 1), ("sent_at", -1)])
    await db.book_sends.create_index("company_id")

    logger.info("Índices MongoDB criados.")
