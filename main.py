"""
Provare API — Servidor principal FastAPI
Sistema multi-tenant para documentação de projetos premium
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import connect_db, disconnect_db
from routers import auth, companies, projects, phases, media, provare_book, billing, dashboard

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s · %(name)s · %(levelname)s · %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia conexão com o banco durante o ciclo de vida da aplicação."""
    await connect_db()
    logger.info("🚀 Provare API iniciada")
    yield
    await disconnect_db()
    logger.info("Provare API encerrada")


# Criação da aplicação
app = FastAPI(
    title="Provare API",
    description="Sistema de documentação premium para empresas de serviço",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",       # Swagger UI — desativar em produção se quiser
    redoc_url="/redoc",
)

# CORS — aceita requisições do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://provare.com.br",
        "https://www.provare.com.br",
        "https://provare-frontend.vercel.app",
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registra todos os routers
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(projects.router)
app.include_router(phases.router)
app.include_router(media.router)
app.include_router(provare_book.router)
app.include_router(billing.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health_check():
    """Health check — usado pelo Render para verificar se a API está no ar."""
    return {"status": "ok", "service": "provare-api", "version": "1.0.0"}


@app.get("/")
async def root():
    return {"message": "Provare API · provare.com.br"}
