# src/main.py

import logging

# Seus imports existentes
from src.api.app.events.totem_namespace import TotemNamespace
from src.core.database import engine
from src.core.models import Base
import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from src.core.db_initialization import initialize_roles
from src.api.admin.events.admin_namespace import AdminNamespace
from src.socketio_instance import sio
from src.api.admin import router as admin_router
from src.api.app import router as app_router

# 👇 1. IMPORTE O NOVO ROUTER DO WEBHOOK
from src.api.admin.webhooks.chatbot_webhook import router as webhooks_router


# -------------------------------------------------------------
# Defina o Lifespan para gerenciar o ciclo de vida da aplicação
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ao iniciar a aplicação (startup)
    print("Iniciando a aplicação e verificando roles...")
    with Session(bind=engine) as db_session:
        initialize_roles(db_session)
    print("Roles verificadas. Aplicação pronta.")
    yield
    # Ao desligar a aplicação (shutdown)
    print("Desligando a aplicação...")


# Registra namespaces ANTES de criar o ASGIApp
sio.register_namespace(AdminNamespace('/admin'))
sio.register_namespace(TotemNamespace('/'))

# Crie sua instância FastAPI e associe o lifespan
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

# --- Registrando suas rotas principais ---
fast_app.include_router(admin_router)
fast_app.include_router(app_router)

# 👇 2. INCLUA O NOVO ROUTER DE WEBHOOKS NO SEU APP PRINCIPAL
fast_app.include_router(webhooks_router)


# --- Montando o app final com Socket.IO ---
app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

__all__ = ["app"]