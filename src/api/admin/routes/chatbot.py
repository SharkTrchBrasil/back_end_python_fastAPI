from typing import Optional

from fastapi import APIRouter, HTTPException, Body, Depends, BackgroundTasks
import httpx  # cliente HTTP assíncrono para buscar dados do Node.js
from src.api.schemas.chatbot_config import StoreChatbotConfigCreate, StoreChatbotConfig, StoreChatbotConfigUpdate
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
async def conectar_whatsapp(
    store_id: int, # FastAPI pega o store_id da URL automaticamente
    db: GetDBDep,
    http_client: httpx.AsyncClient = Depends(get_async_http_client)
):
    # URL do seu serviço de chatbot Node.js
    CHATBOT_SERVICE_URL = "https://chatbot-production-f10b.up.railway.app/iniciar-sessao"

    # Garante que existe uma configuração antes de tentar conectar
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store_id).first()
    if not config:
        # Cria uma configuração padrão se não existir
        config = models.StoreChatbotConfig(store_id=store_id, connection_status="pending")
        db.add(config)
    else:
        # Atualiza o status para indicar que uma nova conexão está sendo tentada
        config.connection_status = "pending"
        config.last_qr_code = None # Limpa o QR code antigo

    db.commit()

    try:
        # Passo 3: Comanda o serviço Node.js para iniciar a sessão
        response = await http_client.post(
            CHATBOT_SERVICE_URL,
            json={"lojaId": store_id}, # O serviço Node.js espera 'lojaId'
            timeout=15.0 # Aumenta um pouco o timeout
        )
        response.raise_for_status()
        return {"message": "Solicitação de conexão enviada ao serviço de chatbot"}
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Erro de comunicação com o serviço de chatbot: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"O serviço de chatbot retornou um erro: {e.response.text}")
