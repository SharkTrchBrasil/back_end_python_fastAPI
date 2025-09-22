# src/main.py

import logging
from sqlalchemy.orm import Session
import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from contextlib import asynccontextmanager

# Seus imports existentes
from src.api.app.events.totem_namespace import TotemNamespace
from src.core.database import engine
from src.core.db_initialization import initialize_roles, seed_chatbot_templates  # ✅ 1. IMPORTE A NOVA FUNÇÃO
from src.api.admin.events.admin_namespace import AdminNamespace
from src.socketio_instance import sio
from src.api.admin import router as admin_router
from src.api.app import router as app_router
from src.api.admin.webhooks.chatbot_webhook import router as webhooks_router


# -------------------------------------------------------------
# Defina o Lifespan para gerenciar o ciclo de vida da aplicação
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ao iniciar a aplicação (startup)
    print("Iniciando a aplicação...")
    with Session(bind=engine) as db_session:
        print("Verificando roles...")
        initialize_roles(db_session)
        print("Roles verificadas.")

        # ✅ 2. CHAME A FUNÇÃO PARA SEMEAR OS TEMPLATES DO CHATBOT
        print("Semeando templates do chatbot...")
        seed_chatbot_templates(db_session)
        print("Templates do chatbot verificados.")

    print("Aplicação pronta.")
    yield
    # Ao desligar a aplicação (shutdown)
    print("Desligando a aplicação...")


# --- O RESTANTE DO SEU ARQUIVO main.py CONTINUA IGUAL ---

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

fast_app.include_router(admin_router)
fast_app.include_router(app_router)
fast_app.include_router(webhooks_router)

app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

__all__ = ["app"]