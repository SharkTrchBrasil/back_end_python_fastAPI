from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.core import database
from src.core.models import Base

from src.api.admin import router as admin_router
from src.api.app import router as app_router

Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="TotemPRO API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_router)
app.include_router(app_router)