
import logging

from src.api.app.events.totem_namespace import TotemNamespace
from src.core.database import engine
from src.core.models import Base

logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

import socketio
import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.templating import Jinja2Templates


from contextlib import asynccontextmanager  # Para o lifespan
from sqlalchemy.orm import Session  # Para type hinting e criar sessão no lifespan



from src.core.db_initialization import initialize_roles



from src.api.admin.events.admin_namespace import AdminNamespace
from src.socketio_instance import sio

from src.api.admin import router as admin_router
from src.api.app import router as app_router


# -------------------------------------------------------------
# Defina o Lifespan para gerenciar o ciclo de vida da aplicação
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ao iniciar a aplicação (startup)
    print("Iniciando a aplicação e verificando roles...")

    # Obtenha uma sessão de banco de dados para inicializar as roles
    with Session(bind=engine) as db_session:
        initialize_roles(db_session)  # Chama a função para criar/verificar roles

    print("Roles verificadas. Aplicação pronta.")

    yield  # A aplicação estará ativa aqui

    # Ao desligar a aplicação (shutdown)
    print("Desligando a aplicação...")


# Registra namespaces ANTES de criar o ASGIApp
sio.register_namespace(AdminNamespace('/admin'))
sio.register_namespace(TotemNamespace('/'))  # Namespace padrão

# Crie sua instância FastAPI e associe o lifespan
fast_app = FastAPI(
    title="PDVix API",
    lifespan=lifespan  # <--- Associe o lifespan aqui
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

app = socketio.ASGIApp(sio, fast_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)