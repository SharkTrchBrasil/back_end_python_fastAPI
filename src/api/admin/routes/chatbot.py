from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Depends, BackgroundTasks
import httpx  # cliente HTTP assíncrono para buscar dados do Node.js
from src.api.admin.schemas.chatbot_config import StoreChatbotConfigCreate, StoreChatbotConfig, StoreChatbotConfigUpdate
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Chatbot Config"], prefix="/stores/{store_id}/chatbot-config")

# Adicione esta dependência para criar um cliente httpx assíncrono
async def get_async_http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient() as client:
        yield client

@router.post("", response_model=StoreChatbotConfig)
def create_config(
    db: GetDBDep,
    store: GetStoreDep,
    config_data: Optional[StoreChatbotConfigCreate] = Body(default=None),
):
    if config_data is None:
        config_data = StoreChatbotConfigCreate()

    existing = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Config already exists")

    db_config = models.StoreChatbotConfig(
        **config_data.model_dump(),
        store_id=store.id,
    )

    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config


@router.get("", response_model=StoreChatbotConfig)
def get_config(
    db: GetDBDep,
    store: GetStoreDep,
):
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.patch("", response_model=StoreChatbotConfig)
def patch_config(
    db: GetDBDep,
    store: GetStoreDep,
    config_update: StoreChatbotConfigUpdate,
):
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    for field, value in config_update.model_dump(exclude_unset=True).items():
        setattr(config, field, value)

    db.commit()
    return config


@router.post("/qr-code")
def receber_qr_code(
    db: GetDBDep,
    store: GetStoreDep,
    body: dict = Body(...)
):
    qr = body.get("qr")
    if not qr:
        raise HTTPException(status_code=400, detail="QR code não enviado")

    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()
    if not config:
        config = models.StoreChatbotConfig(
            store_id=store.id,
            last_qr_code=qr,
            connection_status="awaiting_qr"
        )
        db.add(config)
    else:
        config.last_qr_code = qr
        config.connection_status = "awaiting_qr"

    db.commit()
    return {"message": "QR code salvo com sucesso"}


@router.post("/connect")
async def conectar_whatsapp(  # Alterado para async def
    store_id: int,
    background_tasks: BackgroundTasks,
    http_client: httpx.AsyncClient = Depends(get_async_http_client)
):
    try:
        response = await http_client.post(
            "https://chatbot-lr2h.onrender.com/connect",
            json={"store_id": store_id},
            timeout=10
        )
        response.raise_for_status()
        return {"message": "Solicitação de conexão enviada ao chatbot"}
    except httpx.HTTPError as e:
        raise HTTPException(status_code=response.status_code, detail=f"Erro ao conectar o chatbot: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno ao conectar o chatbot: {str(e)}")