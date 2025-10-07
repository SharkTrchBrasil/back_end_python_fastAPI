# Crie um novo arquivo: src/api/services/platform_notification_service.py

import httpx
from src.core.config import config


class PlatformNotificationService:
    """
    Serviço centralizado para enviar notificações via o Bot da Plataforma.
    """

    @staticmethod
    async def send_whatsapp_message(phone_number: str, message: str) -> bool:
        """
        Envia uma mensagem de texto simples usando o bot oficial da plataforma.

        Args:
            phone_number: O número do destinatário (ex: "5531999998888").
            message: O conteúdo da mensagem.

        Returns:
            True se a mensagem foi enviada com sucesso, False caso contrário.
        """
        if not config.CHATBOT_SERVICE_URL:
            print("❌ ERRO: CHATBOT_SERVICE_URL não configurada. Não é possível enviar a mensagem.")
            return False

        # ✅ Endpoint que criamos no Node.js
        url = f"{config.CHATBOT_SERVICE_URL}/platform-bot/send-message"
        payload = {"number": phone_number, "message": message}
        headers = {"x-webhook-secret": config.CHATBOT_WEBHOOK_SECRET}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=15.0)
                response.raise_for_status()  # Lança uma exceção para erros HTTP (4xx, 5xx)
                print(f"✅ Notificação de plataforma enviada para {phone_number}.")
                return True
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"❌ Falha ao enviar notificação de plataforma para {phone_number}. Erro: {e}")
            return False

# --- Exemplo de Uso em Outra Parte do Código ---

# Em uma rota de verificação de usuário, por exemplo:
# from src.api.services.platform_notification_service import PlatformNotificationService

# async def send_verification_code(user: User):
#     code = "123456"
#     message = f"Olá, {user.name}! Seu código de verificação na plataforma PDVix é: {code}"
#     await PlatformNotificationService.send_whatsapp_message(user.phone, message)
