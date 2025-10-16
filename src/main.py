# src/main.py
"""
Aplicação Principal - PDVix API
================================

FastAPI + Socket.IO + APScheduler

Características:
- ✅ Startup/Shutdown gerenciados via lifespan
- ✅ Seeding automático de dados essenciais
- ✅ Jobs agendados (billing, lifecycle, etc.)
- ✅ WebSocket real-time (Socket.IO)
- ✅ Webhooks (Pagar.me, Chatbot)
- ✅ CORS configurável
- ✅ Logs estruturados

Autor: PDVix Team
Última atualização: 2025-01-16
"""

import logging
import sys
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates

# ✅ IMPORTS CORRETOS
from src.api.admin.routes import chatbot_api
from src.api.admin.webhooks.chatbot import chatbot_message_webhook
from src.api.scheduler import start_scheduler, stop_scheduler  # ✅ CORRIGIDO
from src.core.database import engine
from src.core.db_initialization import (
    initialize_roles,
    seed_chatbot_templates,
    seed_plans_and_features,
    seed_segments,
    seed_payment_methods
)
from src.api.admin.events.admin_namespace import AdminNamespace
from src.api.app.events.totem_namespace import TotemNamespace
from src.socketio_instance import sio
from src.api.admin import router as admin_router
from src.api.app import router as app_router
from src.api.admin.webhooks.chatbot.chatbot_webhook import router as chatbot_webhooks_router
from src.api.admin.webhooks.pagarme_webhook import router as pagarme_webhook_router
from src.core.config import config  # ✅ NOVO

# ✅ CONFIGURAÇÃO DE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    ✅ GERENCIA CICLO DE VIDA DA APLICAÇÃO

    Startup:
    - Seeding de dados essenciais
    - Inicialização do scheduler

    Shutdown:
    - Desligamento gracioso do scheduler
    """

    # ═══════════════════════════════════════════════════════════
    # STARTUP
    # ═══════════════════════════════════════════════════════════

    logger.info("=" * 60)
    logger.info("🚀 INICIANDO APLICAÇÃO PDVix")
    logger.info("=" * 60)

    # ✅ 1. SEEDING DE DADOS ESSENCIAIS
    try:
        with Session(bind=engine) as db_session:
            logger.info("📋 Verificando dados essenciais...")

            # Roles
            try:
                logger.info("   → Roles...")
                initialize_roles(db_session)
                logger.info("   ✅ Roles OK")
            except Exception as e:
                logger.error(f"   ❌ Erro ao inicializar roles: {e}", exc_info=True)
                # Não bloqueia startup

            # Templates Chatbot
            try:
                logger.info("   → Templates chatbot...")
                seed_chatbot_templates(db_session)
                logger.info("   ✅ Templates chatbot OK")
            except Exception as e:
                logger.error(f"   ❌ Erro ao seed chatbot templates: {e}", exc_info=True)

            # Planos e Features
            try:
                logger.info("   → Planos e features...")
                seed_plans_and_features(db_session)
                logger.info("   ✅ Planos e features OK")
            except Exception as e:
                logger.error(f"   ❌ Erro ao seed planos: {e}", exc_info=True)

            # Segmentos
            try:
                logger.info("   → Segmentos...")
                seed_segments(db_session)
                logger.info("   ✅ Segmentos OK")
            except Exception as e:
                logger.error(f"   ❌ Erro ao seed segmentos: {e}", exc_info=True)

            # Formas de Pagamento
            try:
                logger.info("   → Formas de pagamento...")
                seed_payment_methods(db_session)
                logger.info("   ✅ Formas de pagamento OK")
            except Exception as e:
                logger.error(f"   ❌ Erro ao seed payment methods: {e}", exc_info=True)

        logger.info("✅ Seeding concluído")

    except Exception as e:
        logger.error(f"❌ Erro crítico no seeding: {e}", exc_info=True)
        # Decide se aborta ou continua
        # raise  # Descomente para abortar em erro crítico

    # ✅ 2. INICIA SCHEDULER
    try:
        logger.info("⏰ Iniciando scheduler de jobs...")
        start_scheduler()
        logger.info("✅ Scheduler iniciado com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro ao iniciar scheduler: {e}", exc_info=True)
        # Não bloqueia startup (jobs não rodarão)

    logger.info("=" * 60)
    logger.info("✅ APLICAÇÃO PRONTA!")
    logger.info(f"📡 Environment: {config.ENVIRONMENT}")
    logger.info(f"🔧 Debug Mode: {config.DEBUG}")
    logger.info("=" * 60)

    yield

    # ═══════════════════════════════════════════════════════════
    # SHUTDOWN
    # ═══════════════════════════════════════════════════════════

    logger.info("=" * 60)
    logger.info("🛑 DESLIGANDO APLICAÇÃO...")
    logger.info("=" * 60)

    # ✅ DESLIGA SCHEDULER CORRETAMENTE
    try:
        logger.info("⏹️  Desligando scheduler...")
        stop_scheduler()
        logger.info("✅ Scheduler desligado")
    except Exception as e:
        logger.error(f"❌ Erro ao desligar scheduler: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info("✅ APLICAÇÃO DESLIGADA")
    logger.info("=" * 60)


# ✅ REGISTRA NAMESPACES ANTES DE CRIAR ASGI APP
logger.info("🔌 Registrando namespaces Socket.IO...")
sio.register_namespace(AdminNamespace('/admin'))
sio.register_namespace(TotemNamespace('/'))
logger.info("✅ Namespaces registrados")

# ✅ CRIA APLICAÇÃO FASTAPI
fast_app = FastAPI(
    title="PDVix API",
    description="API para sistema de gestão de pedidos e delivery",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if config.DEBUG else None,  # ✅ Desabilita docs em produção
    redoc_url="/redoc" if config.DEBUG else None
)

# ✅ CORS CONFIGURÁVEL
allowed_origins = (
    config.ALLOWED_ORIGINS.split(",")
    if hasattr(config, 'ALLOWED_ORIGINS') and config.ALLOWED_ORIGINS
    else ["*"]  # Fallback apenas para desenvolvimento
)

logger.info(f"🌐 CORS configurado para: {allowed_origins}")

fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ TEMPLATES
templates = Jinja2Templates(directory="src/templates")

# ✅ ROTAS
logger.info("📍 Registrando rotas...")
fast_app.include_router(admin_router, prefix="/admin", tags=["Admin"])
fast_app.include_router(app_router, prefix="/app", tags=["App"])
fast_app.include_router(chatbot_webhooks_router, prefix="/webhooks/chatbot", tags=["Webhooks - Chatbot"])
fast_app.include_router(chatbot_message_webhook.router, prefix="/webhooks", tags=["Webhooks"])
fast_app.include_router(pagarme_webhook_router, prefix="/webhooks/pagarme", tags=["Webhooks - Pagar.me"])
logger.info("✅ Rotas registradas")


# ✅ HEALTH CHECK
@fast_app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de health check para monitoring"""
    return {
        "status": "healthy",
        "environment": config.ENVIRONMENT,
        "version": "1.0.0"
    }


# ✅ CRIA ASGI APP COM SOCKET.IO
app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    logger.info("🚀 Iniciando servidor Uvicorn...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

__all__ = ["app"]