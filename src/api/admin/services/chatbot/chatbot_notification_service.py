# src/api/admin/services/chatbot_notification_service.py - VERSÃO CORRIGIDA
import os
from typing import Optional

from sqlalchemy.orm import Session

from src.api.admin.services.chatbot.chatbot_client import chatbot_client
from src.core import models

from src.core.utils.enums import OrderStatus

STATUS_TO_MESSAGE_KEY = {
    OrderStatus.PREPARING: 'order_accepted',
    OrderStatus.READY: 'order_ready',
    OrderStatus.ON_ROUTE: 'order_on_route',
    OrderStatus.DELIVERED: 'order_delivered',
    OrderStatus.CANCELED: 'order_canceled',
}


async def send_order_status_update(db: Session, order: models.Order):
    """Envia atualização de status de pedido de forma robusta"""

    # ✅ 1. Validações iniciais
    if not order or not order.store:
        print("❌ Pedido ou loja inválida")
        return

    message_key = STATUS_TO_MESSAGE_KEY.get(order.order_status)
    if not message_key:
        print(f"ℹ️ Nenhum template para status: {order.order_status}")
        return

    # ✅ 2. Verificar configuração do chatbot
    if not order.store.chatbot_config or order.store.chatbot_config.connection_status != 'connected':
        print(f"ℹ️ Chatbot não conectado para loja {order.store_id}")
        return

    # ✅ 3. Buscar configuração da mensagem
    message_config = db.query(models.StoreChatbotMessage).filter_by(
        store_id=order.store_id,
        template_key=message_key
    ).first()

    if not message_config or not message_config.is_active:
        print(f"ℹ️ Mensagem {message_key} inativa para loja {order.store_id}")
        return

    # ✅ 4. Obter telefone do cliente
    phone_number = await _get_customer_phone(order)
    if not phone_number:
        print(f"⚠️ Pedido {order.id} sem telefone válido")
        return

    # ✅ 5. Formatar e enviar mensagem
    final_message = _format_message(message_config.final_content, order, order.store)

    success = await chatbot_client.send_message(
        store_id=order.store_id,
        number=phone_number,
        message=final_message
    )

    if success:
        print(f"✅ Status {order.order_status} enviado para pedido {order.id}")
    else:
        print(f"❌ Falha ao enviar status para pedido {order.id}")


async def _get_customer_phone(order: models.Order) -> Optional[str]:
    """Extrai e formata telefone do cliente de forma segura"""
    try:
        raw_phone = None

        # Tentativa 1: Via relação customer
        if order.customer and order.customer.phone:
            raw_phone = order.customer.phone
        # Tentativa 2: Via campo direto
        elif order.customer_phone:
            raw_phone = order.customer_phone

        if not raw_phone:
            return None

        # ✅ Limpar e validar número
        clean_phone = "".join(filter(str.isdigit, str(raw_phone)))

        if clean_phone.startswith('55'):
            if len(clean_phone) in [12, 13]:  # 55 + DDD + 8 ou 9 dígitos
                return clean_phone
        else:
            if len(clean_phone) in [10, 11]:  # DDD + 8 ou 9 dígitos
                return f"55{clean_phone}"

        print(f"⚠️ Número inválido: {raw_phone} -> {clean_phone}")
        return None

    except Exception as e:
        print(f"❌ Erro ao processar telefone: {e}")
        return None


def _format_message(content: str, order: models.Order, store: models.Store) -> str:
    """Substitui variáveis na mensagem de forma segura"""
    base_url = f"https://{store.url_slug}.{os.getenv('PLATFORM_DOMAIN', 'menuhub.com.br')}"

    replacements = {
        "{client.name}": order.customer_name or "Cliente",
        "{order.public_id}": order.public_id,
        "{order.url}": f"{base_url}/orders/{order.public_id}",
        "{company.name}": store.name,
    }

    for key, value in replacements.items():
        content = content.replace(key, value or "")

    return content