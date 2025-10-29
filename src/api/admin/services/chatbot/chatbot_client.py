# src/core/services/chatbot_client.py - NOVO ARQUIVO
import os
import httpx
from typing import Optional, Dict, Any
import asyncio
from contextlib import asynccontextmanager


class ChatbotClient:
    def __init__(self):
        self.base_url = os.getenv("CHATBOT_SERVICE_URL")
        self.secret = os.getenv("CHATBOT_WEBHOOK_SECRET")
        self.timeout = httpx.Timeout(15.0)
        self.max_retries = 3

        if not self.base_url or not self.secret:
            raise ValueError("CHATBOT_SERVICE_URL e CHATBOT_WEBHOOK_SECRET são obrigatórios")

    @asynccontextmanager
    async def get_client(self):
        """Context manager para cliente HTTP com retry automático"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            yield client

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Método base para todas as requisições com retry e tratamento de erro"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'x-webhook-secret': self.secret,
            'user-agent': 'FastAPI-Chatbot-Client/1.0'
        }

        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))

        for attempt in range(self.max_retries):
            try:
                async with self.get_client() as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=headers,
                        **kwargs
                    )

                    # ✅ Log detalhado para debugging
                    print(f"🔗 Chatbot API: {method} {endpoint} - Status: {response.status_code}")

                    if response.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error: {response.status_code}",
                            request=response.request,
                            response=response
                        )

                    response.raise_for_status()
                    return response.json() if response.content else {}

            except httpx.TimeoutException:
                if attempt == self.max_retries - 1:
                    raise Exception(f"Timeout após {self.max_retries} tentativas")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except httpx.ConnectError:
                if attempt == self.max_retries - 1:
                    raise Exception("Não foi possível conectar ao serviço de chatbot")
                await asyncio.sleep(2 ** attempt)

            except httpx.HTTPStatusError as e:
                # ❌ Erros 4xx não fazem retry
                if 400 <= e.response.status_code < 500:
                    error_detail = e.response.json().get('error', 'Erro do cliente')
                    raise Exception(f"Erro do serviço: {error_detail}")
                elif attempt == self.max_retries - 1:
                    raise Exception(f"Erro do servidor após {self.max_retries} tentativas")
                await asyncio.sleep(2 ** attempt)

        raise Exception("Todas as tentativas falharam")

    # ✅ MÉTODOS ESPECÍFICOS
    async def send_message(self, store_id: int, number: str, message: str,
                           media_url: Optional[str] = None, media_type: Optional[str] = None) -> bool:
        payload = {
            "storeId": store_id,
            "number": number,
            "message": message
        }

        if media_url and media_type:
            payload.update({
                "mediaUrl": media_url,
                "mediaType": media_type
            })

        try:
            result = await self._make_request("POST", "/send-message", json=payload)
            return True
        except Exception as e:
            print(f"❌ Falha ao enviar mensagem: {e}")
            return False

    async def pause_chat(self, store_id: int, chat_id: str) -> bool:
        payload = {
            "storeId": store_id,
            "chatId": chat_id
        }

        try:
            await self._make_request("POST", "/pause-chat", json=payload)
            return True
        except Exception as e:
            print(f"❌ Falha ao pausar chat: {e}")
            return False

    async def start_session(self, store_id: int, method: str, phone_number: Optional[str] = None) -> bool:
        payload = {
            "storeId": store_id,
            "method": method
        }

        if phone_number:
            payload["phoneNumber"] = phone_number

        try:
            await self._make_request("POST", "/start-session", json=payload)
            return True
        except Exception as e:
            print(f"❌ Falha ao iniciar sessão: {e}")
            return False

    async def disconnect_session(self, store_id: int) -> bool:
        payload = {"storeId": store_id}

        try:
            await self._make_request("POST", "/disconnect", json=payload)
            return True
        except Exception as e:
            print(f"❌ Falha ao desconectar: {e}")
            return False

    async def get_profile_picture(self, store_id: int, chat_id: str) -> Optional[str]:
        try:
            result = await self._make_request("GET", f"/profile-picture/{store_id}/{chat_id}")
            return result.get("profilePicUrl")
        except Exception as e:
            print(f"❌ Falha ao buscar foto: {e}")
            return None

    async def get_contact_name(self, store_id: int, chat_id: str) -> Optional[str]:
        try:
            result = await self._make_request("GET", f"/contact-name/{store_id}/{chat_id}")
            return result.get("name")
        except Exception as e:
            print(f"❌ Falha ao buscar nome: {e}")
            return None

    async def update_status(self, store_id: int, is_active: bool) -> bool:
        """
        Atualiza o status (ativo/inativo) do chatbot no serviço Node.js
        """
        payload = {
            "storeId": store_id,
            "isActive": is_active
        }

        try:
            await self._make_request("POST", "/update-status", json=payload)
            return True
        except Exception as e:
            print(f"❌ Falha ao atualizar status do chatbot: {e}")
            return False


# Instância global
chatbot_client = ChatbotClient()