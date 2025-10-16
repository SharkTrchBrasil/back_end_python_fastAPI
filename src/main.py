# src/main.py
"""
Aplicação Principal - PDVix API
================================
"""

import logging
import sys
from contextlib import asynccontextmanager

import socketio
import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware

from src.api.scheduler import start_scheduler, stop_scheduler
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
from src.api.admin.webhooks.chatbot import chatbot_message_webhook
from src.api.admin.webhooks.pagarme_webhook import router as pagarme_webhook_router
from src.core.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicação"""

    logger.info("=" * 60)
    logger.info("🚀 INICIANDO APLICAÇÃO PDVix")
    logger.info("=" * 60)

    # STARTUP
    try:
        with Session(bind=engine) as db_session:
            logger.info("📋 Verificando dados essenciais...")

            initialize_roles(db_session)
            seed_chatbot_templates(db_session)
            seed_plans_and_features(db_session)
            seed_segments(db_session)
            seed_payment_methods(db_session)

            logger.info("✅ Seeding concluído")

        logger.info("⏰ Iniciando scheduler...")
        start_scheduler()
        logger.info("✅ Scheduler iniciado")

    except Exception as e:
        logger.error(f"❌ Erro no startup: {e}", exc_info=True)

    logger.info("✅ APLICAÇÃO PRONTA!")
    logger.info("=" * 60)

    yield

    # SHUTDOWN
    logger.info("🛑 Desligando aplicação...")
    try:
        stop_scheduler()
        logger.info("✅ Scheduler desligado")
    except Exception as e:
        logger.error(f"❌ Erro no shutdown: {e}", exc_info=True)

    logger.info("✅ APLICAÇÃO DESLIGADA")


# ✅ REGISTRA NAMESPACES
logger.info("🔌 Registrando namespaces Socket.IO...")
sio.register_namespace(AdminNamespace('/admin'))
sio.register_namespace(TotemNamespace('/'))

# ✅ CRIA APLICAÇÃO
fast_app = FastAPI(
    title="PDVix API",
    version="1.0.0",
    lifespan=lifespan
)

# ✅ CORS
fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure isso em produção!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ ROTAS (SEM PREFIXOS DUPLICADOS!)
logger.info("📍 Registrando rotas...")

# ❌ ANTES (ERRADO):
# fast_app.include_router(admin_router, prefix="/admin", tags=["Admin"])

# ✅ DEPOIS (CORRETO):
fast_app.include_router(admin_router)  # Cada rota JÁ TEM seu prefixo!
fast_app.include_router(app_router)
fast_app.include_router(chatbot_webhooks_router)
fast_app.include_router(chatbot_message_webhook.router)
fast_app.include_router(pagarme_webhook_router)

logger.info("✅ Rotas registradas")


@fast_app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


# ✅ CRIA ASGI APP
app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

__all__ = ["app"]