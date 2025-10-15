# src/main.py

from sqlalchemy.orm import Session
import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.api.admin.routes import chatbot_api
from src.api.admin.webhooks.chatbot import chatbot_message_webhook
from src.api.scheduler import start_scheduler
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

# ✅ NOVO IMPORT: Webhook do Pagar.me
from src.api.admin.webhooks.pagarme_webhook import router as pagarme_webhook_router


scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Ações de Startup ---
    print("Iniciando a aplicação...")
    with Session(bind=engine) as db_session:

        print("Semeando roles...")
        initialize_roles(db_session)
        print("Roles verificadas.")

        print("Semeando templates do chatbot...")
        seed_chatbot_templates(db_session)
        print("Templates do chatbot verificados.")

        print("Semeando planos e features...")
        seed_plans_and_features(db_session)
        print("Planos e features verificados.")

        print("Semeando Segmentos...")
        seed_segments(db_session)
        print("Segmentos verificados.")

        print("Semeando Formas de pagamentos...")
        seed_payment_methods(db_session)
        print("Formas de pagamentos verificados.")

    # ✅ Agendamento de jobs
    print("Agendando tarefas automáticas (cron jobs)...")
    start_scheduler()
    print("🚀 Agendador iniciado com todos os jobs.")

    print("Aplicação pronta.")
    yield

    # --- Ações de Shutdown ---
    print("Desligando a aplicação...")
    scheduler.shutdown()
    print("🛑 Agendador finalizado.")


# Registra namespaces ANTES de criar o ASGIApp
sio.register_namespace(AdminNamespace('/admin'))
sio.register_namespace(TotemNamespace('/'))

fast_app = FastAPI(
    title="PDVix API",
    lifespan=lifespan
)

fast_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="src/templates")

# ✅ ROTAS
fast_app.include_router(admin_router)
fast_app.include_router(app_router)
fast_app.include_router(chatbot_webhooks_router)
fast_app.include_router(chatbot_message_webhook.router)

# ✅ NOVO: Webhook do Pagar.me
fast_app.include_router(pagarme_webhook_router)


app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

__all__ = ["app"]