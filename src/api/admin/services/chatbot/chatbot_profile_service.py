# src/services/chatbot_profile_service.py

import os
import httpx
from src.core import models
from src.core.database import GetDBDep

CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL")
CHATBOT_WEBHOOK_SECRET = os.getenv("CHATBOT_WEBHOOK_SECRET")


async def fetch_and_update_profile(db: GetDBDep, store_id: int, chat_id: str):
    """
    Verifica se uma conversa já tem foto de perfil e, se não tiver,
    tenta buscar a URL no serviço Node.js e salvá-la no banco.
    """
    # 1. Verifica se já temos a URL para evitar chamadas desnecessárias
    metadata = db.query(models.ChatbotConversationMetadata).filter_by(store_id=store_id, chat_id=chat_id).first()
    if not metadata or metadata.customer_profile_pic_url:
        return  # Se não há metadados ou a foto já existe, não faz nada

    # 2. Prepara a chamada para o novo endpoint do Node.js
    if not CHATBOT_SERVICE_URL:
        return

    url = f"{CHATBOT_SERVICE_URL}/api/profile-picture/{store_id}/{chat_id}"
    headers = {"x-webhook-secret": CHATBOT_WEBHOOK_SECRET}

    # 3. Faz a chamada e atualiza o banco se encontrar a URL
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                profile_pic_url = data.get("profilePicUrl")
                if profile_pic_url:
                    metadata.customer_profile_pic_url = profile_pic_url
                    db.commit()
                    print(f"✅ Foto de perfil para {chat_id} atualizada com sucesso.")
    except Exception as e:
        print(f"AVISO: Não foi possível buscar a foto de perfil para {chat_id}. Erro: {e}")