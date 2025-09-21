# Em: src/api/routers/chatbot.py

from typing import List
from fastapi import APIRouter, HTTPException, Body, Depends
import httpx
from sqlalchemy.orm import Session

from src.api.schemas.chatbot_config import StoreChatbotMessageSchema, StoreChatbotMessageUpdateSchema
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep




# Adicione esta dependência para criar um cliente httpx assíncrono
async def get_async_http_client() -> httpx.AsyncClient:
    async with httpx.AsyncClient() as client:
        yield client


# Mantemos o prefixo, pois todas as operações são dentro de um chatbot de uma loja
router = APIRouter(tags=["Chatbot Config"], prefix="/stores/{store_id}/chatbot-config")


# --- ROTA PRINCIPAL PARA OBTER TODAS AS MENSAGENS ---
@router.get("", response_model=List[StoreChatbotMessageSchema])
def get_all_message_configs(store: GetStoreDep, db: GetDBDep):
    """
    Retorna uma lista de TODAS as configurações de mensagem para uma loja.
    Esta é a rota principal para popular a sua tela no Flutter.
    """
    # 1. Busca todos os templates de mensagem disponíveis no sistema
    all_templates = db.query(models.ChatbotMessageTemplate).all()

    # 2. Busca todas as configurações que a loja já personalizou
    store_configs_list = db.query(models.StoreChatbotMessage).filter_by(store_id=store.id).all()
    # Converte para um dicionário para busca rápida: {'welcome_message': config_obj, ...}
    store_configs_map = {config.template_key: config for config in store_configs_list}

    # 3. Monta a resposta final
    final_configs = []
    for template in all_templates:
        store_config = store_configs_map.get(template.message_key)

        # Monta o objeto de resposta, combinando o template com a configuração da loja
        final_config_obj = {
            "template_key": template.message_key,
            "is_active": store_config.is_active if store_config else True,  # Padrão é ativo
            "final_content": store_config.custom_content if store_config and store_config.custom_content else template.default_content,
            "template": template  # Aninha os detalhes do template
        }
        final_configs.append(final_config_obj)

    return final_configs


# --- ROTA PARA ATUALIZAR UMA MENSAGEM ESPECÍFICA ---
@router.patch("/{message_key}", response_model=StoreChatbotMessageSchema)
def update_message_config(
        message_key: str,
        config_update: StoreChatbotMessageUpdateSchema,
        store: GetStoreDep,
        db: GetDBDep
):
    """
    Atualiza (ou cria) a configuração de uma mensagem específica para uma loja.
    """
    # Verifica se o template para essa message_key existe
    template = db.query(models.ChatbotMessageTemplate).filter_by(message_key=message_key).first()
    if not template:
        raise HTTPException(status_code=404, detail=f"Message template '{message_key}' not found.")

    # Tenta encontrar uma configuração existente para essa loja e template
    db_config = db.query(models.StoreChatbotMessage).filter_by(
        store_id=store.id,
        template_key=message_key
    ).first()

    # Se não existir, cria uma nova
    if not db_config:
        db_config = models.StoreChatbotMessage(
            store_id=store.id,
            template_key=message_key
        )
        db.add(db_config)

    # Atualiza os campos com os dados recebidos
    update_data = config_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_config, key, value)

    db.commit()
    db.refresh(db_config)

    # Monta a resposta final para devolver ao Flutter
    return {
        "template_key": db_config.template_key,
        "is_active": db_config.is_active,
        "final_content": db_config.custom_content if db_config.custom_content else template.default_content,
        "template": template
    }


# --- ROTAS DE CONEXÃO (Mantidas e Corrigidas) ---

@router.post("/connect")
async def conectar_whatsapp(
        store_id: int,  # store_id vem da URL, não precisa de GetStoreDep aqui
        db: GetDBDep,
        http_client: httpx.AsyncClient = Depends(get_async_http_client)
):
    CHATBOT_SERVICE_URL = "https://chatbot-production-f10b.up.railway.app/iniciar-sessao"



    # A lógica para garantir que um StoreChatbotConfig exista é uma boa prática
    config = db.query(models.StoreChatbotConfig).filter_by(store_id=store_id).first()
    if not config:
        config = models.StoreChatbotConfig(store_id=store_id, connection_status="pending")
        db.add(config)
    else:
        config.connection_status = "pending"
        config.last_qr_code = None
    db.commit()

    try:
        response = await http_client.post(CHATBOT_SERVICE_URL, json={"lojaId": store_id}, timeout=15.0)
        response.raise_for_status()
        return {"message": "Solicitação de conexão enviada ao serviço de chatbot"}
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        raise HTTPException(status_code=503, detail=f"Erro de comunicação com o serviço de chatbot: {e}")




@router.post("/disconnect", status_code=200)
async def desconectar_whatsapp(
        store: GetStoreDep,  # Usa a mesma segurança para garantir que o usuário tem acesso à loja
        db: GetDBDep,
        http_client: httpx.AsyncClient = Depends(get_async_http_client)
):
    """
    Inicia o processo de desconexão do chatbot para uma loja.
    """
    CHATBOT_SERVICE_URL = "https://chatbot-production-f10b.up.railway.app/desconectar"  # Use a variável de ambiente aqui!

    # 1. Comanda o serviço Node.js para encerrar a sessão do WhatsApp
    try:
        response = await http_client.post(
            CHATBOT_SERVICE_URL,
            json={"lojaId": store.id},
            timeout=15.0
        )
        response.raise_for_status()  # Lança um erro se a resposta não for 2xx
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        # Se o serviço de chatbot estiver offline ou der erro, ainda assim atualizamos nosso status
        print(f"Aviso: O serviço de chatbot não respondeu à desconexão, mas o status será atualizado. Erro: {e}")

    # 2. Atualiza o status no nosso banco de dados, independentemente da resposta do Node.js
    chatbot_config = db.query(models.StoreChatbotConfig).filter_by(store_id=store.id).first()

    if chatbot_config:
        chatbot_config.connection_status = 'disconnected'
        chatbot_config.whatsapp_name = None
        chatbot_config.whatsapp_number = None
        chatbot_config.last_qr_code = None
        db.commit()

        # Opcional, mas recomendado: Emitir um evento de socket para avisar a UI
        # await realtime_manager.emit_store_details_update(store.id)

    return {"message": "Solicitação de desconexão processada com sucesso."}