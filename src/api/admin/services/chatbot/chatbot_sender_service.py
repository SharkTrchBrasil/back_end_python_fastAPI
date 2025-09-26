# src/services/chatbot_sender_service.py

import os
import httpx

# Carrega as variáveis de ambiente necessárias para a comunicação
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL")
CHATBOT_WEBHOOK_SECRET = os.getenv("CHATBOT_WEBHOOK_SECRET")


async def send_whatsapp_message(store_id: int, chat_id: str, text_content: str) -> bool:
    """
    Envia uma mensagem de texto para um chat específico através do serviço Node.js.

    Args:
        store_id: ID da loja que está enviando.
        chat_id: O ID do chat do destinatário (ex: '5531..._@_s.whatsapp.net').
        text_content: O texto da mensagem a ser enviada.

    Returns:
        True se a mensagem foi enviada com sucesso ao serviço, False caso contrário.
    """
    if not CHATBOT_SERVICE_URL or not CHATBOT_WEBHOOK_SECRET:
        print("ERRO CRÍTICO: CHATBOT_SERVICE_URL ou CHATBOT_WEBHOOK_SECRET não configurado.")
        return False

    # 1. Prepara a requisição
    send_url = f"{CHATBOT_SERVICE_URL}/send-message"

    # O endpoint do Node.js espera a chave 'number', então limpamos o JID do WhatsApp
    number = chat_id.split('@')[0]

    payload = {
        "storeId": store_id,
        "number": number,
        "message": text_content
    }
    headers = {
        "x-webhook-secret": CHATBOT_WEBHOOK_SECRET
    }

    # 2. Envia a requisição de forma assíncrona
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(send_url, json=payload, headers=headers, timeout=15.0)

            # Levanta um erro para respostas 4xx ou 5xx
            response.raise_for_status()

            print(f"✅ Mensagem para {number} enviada com sucesso para o serviço de chatbot.")
            return True
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        print(f"❌ ERRO: Falha ao comunicar com o serviço de chatbot para enviar mensagem para {number}. Detalhes: {e}")
        return False