# src/api/admin/services/chatbot_notification_service.py

import os
import httpx
from sqlalchemy.orm import Session
from src.core import models
from src.core.config import config
from src.core.utils.enums import OrderStatus

# Mapeamento de status de pedido para a chave do template de mensagem
STATUS_TO_MESSAGE_KEY = {
    OrderStatus.PREPARING: 'order_accepted',
    OrderStatus.READY: 'order_ready',
    OrderStatus.ON_ROUTE: 'order_on_route',
    OrderStatus.DELIVERED: 'order_delivered',
    OrderStatus.CANCELED: 'order_cancelled',
}

# Carrega as variáveis de ambiente uma vez
CHATBOT_SERVICE_URL = os.getenv("CHATBOT_SERVICE_URL")
CHATBOT_WEBHOOK_SECRET = os.getenv("CHATBOT_WEBHOOK_SECRET")


# --- FUNÇÃO HELPER PARA FORMATAR A MENSAGEM DO RESUMO ---
def _build_order_summary_message(order: models.Order) -> str:
    """ Constrói a string formatada do resumo do pedido para o WhatsApp. """

    # Helper para formatar moeda
    def format_currency(value_in_cents: int) -> str:
        return f"R$ {(value_in_cents / 100):.2f}".replace('.', ',')

    # 1. Cabeçalho
    message_parts = [f"*Pedido:* {order.public_id}\n"]

    # 2. Dados do Cliente
    message_parts.append("*Cliente:*")
    message_parts.append(f"Nome: {order.customer_name or 'Não informado'}")
    message_parts.append(f"Telefone: {order.customer_phone or 'Não informado'}\n")

    # 3. Itens do Pedido (loop)
    message_parts.append("*Itens:*")
    for item in order.products:
        item_total = format_currency(item.price * item.quantity)
        message_parts.append(f"Nome: {item.name}")
        message_parts.append(f"Quantidade: {item.quantity}x, Valor: {item_total}")
        if item.note:
            message_parts.append(f"  _Obs: {item.note}_")
    message_parts.append("")  # Linha em branco

    # 4. Valores
    message_parts.append("*Valores:*")
    message_parts.append(f"Pedido: {format_currency(order.subtotal_price)}")
    message_parts.append(f"Taxa de Entrega: {format_currency(order.delivery_fee)}")
    message_parts.append(f"*Total: {format_currency(order.discounted_total_price)}*\n")

    # 5. Forma de Pagamento
    message_parts.append(f"*Forma de Pagamento:* {order.payment_method_name or 'Não informada'}\n")

    # 6. Endereço
    message_parts.append("*Endereço:*")
    message_parts.append(f"{order.street}, Nº {order.number or 's/n'}")
    message_parts.append(f"{order.city}")
    message_parts.append(f"{order.neighborhood}")
    if order.complement:
        message_parts.append(f"Complemento: {order.complement}")
    message_parts.append("")

    # 7. Link de Acompanhamento
    tracking_link = f"https://{order.store.url_slug}.{config.PLATFORM_DOMAIN}/orders/waiting?order={order.public_id}"
    message_parts.append("Acompanhe seu pedido no link:")
    message_parts.append(tracking_link)

    return "\n".join(message_parts)


# --- NOVA FUNÇÃO PARA ENVIAR O RESUMO ---
async def send_new_order_summary(db: Session, order: models.Order):
    """ Envia o resumo completo de um novo pedido para o cliente. """
    message_key = 'new_order_summary'

    if not order.store.chatbot_config or order.store.chatbot_config.connection_status != 'connected':
        return print(
            f"INFO: Chatbot não conectado para loja {order.store_id}. Resumo do pedido {order.id} não enviado.")

    message_config = db.query(models.StoreChatbotMessage).filter_by(store_id=order.store_id,
                                                                    template_key=message_key).first()

    if not message_config or not message_config.is_active:
        return print(f"INFO: Mensagem '{message_key}' inativa para a loja {order.store_id}.")

    customer_phone = order.customer.phone if order.customer else order.customer_phone
    if not customer_phone:
        return print(f"AVISO: Pedido {order.id} não possui telefone de cliente. Resumo não enviado.")

    final_message = _build_order_summary_message(order)

    send_url = f"{CHATBOT_SERVICE_URL}/send-message"
    payload = {"lojaId": order.store_id, "number": customer_phone, "message": final_message}
    headers = {'x-webhook-secret': CHATBOT_WEBHOOK_SECRET}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(send_url, json=payload, headers=headers, timeout=20.0)
            response.raise_for_status()
            print(f"✅ Resumo do pedido {order.id} enviado com sucesso.")
    except Exception as e:
        print(f"❌ ERRO ao enviar resumo do pedido {order.id}: {e}")


def _format_message(content: str, order: models.Order, store: models.Store) -> str:
    """ Substitui as variáveis no template da mensagem. """
    customer_phone = order.customer.phone if order.customer else order.customer_phone

    # Adapte a base da URL para o seu ambiente (produção/desenvolvimento)
    base_url = f"https://{store.url_slug}.{config.PLATFORM_DOMAIN}"

    replacements = {
        "{client.name}": order.customer_name or "Cliente",
        "{client.number}": customer_phone or "",
        "{order.public_id}": order.public_id,
        "{order.url}": f"{base_url}/orders/{order.public_id}",
        "{company.name}": store.name,
        "{company.url}": base_url,
    }

    for key, value in replacements.items():
        content = content.replace(key, value or "")

    return content


async def send_order_status_update(db: Session, order: models.Order):
    """
    Função principal que orquestra o envio da notificação de status de pedido.
    """
    # 1. Mapeia o status do pedido para a chave da mensagem
    message_key = STATUS_TO_MESSAGE_KEY.get(order.order_status)
    if not message_key:
        print(f"INFO: Nenhum template de mensagem definido para o status '{order.order_status.value}'.")
        return

    # 2. Verifica se o chatbot está conectado
    if not order.store.chatbot_config or order.store.chatbot_config.connection_status != 'connected':
        print(f"INFO: Chatbot não está conectado para a loja {order.store_id}. Mensagem não enviada.")
        return

    # 3. Busca a mensagem no banco de dados
    message_config = db.query(models.StoreChatbotMessage).filter_by(
        store_id=order.store_id,
        template_key=message_key
    ).first()

    if not message_config or not message_config.is_active:
        print(f"INFO: Mensagem '{message_key}' está inativa ou não configurada para a loja {order.store_id}.")
        return

    # 4. Pega o número de telefone do cliente
    customer_phone = order.customer.phone if order.customer else order.customer_phone
    if not customer_phone:
        print(f"AVISO: Pedido {order.id} não possui telefone de cliente. Mensagem não enviada.")
        return

    # 5. Formata a mensagem final
    content_to_send = message_config.final_content  # Usa a hybrid_property que criamos!
    final_message = _format_message(content_to_send, order, order.store)

    # 6. Envia a requisição para o serviço Node.js
    send_url = f"{CHATBOT_SERVICE_URL}/send-message"
    payload = {
        "lojaId": order.store_id,
        "number": customer_phone,
        "message": final_message
    }
    headers = {'x-webhook-secret': CHATBOT_WEBHOOK_SECRET}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(send_url, json=payload, headers=headers, timeout=20.0)
            response.raise_for_status()
            print(f"✅ Mensagem de status '{order.order_status.value}' enviada com sucesso para o pedido {order.id}.")
    except httpx.RequestError as e:
        print(f"❌ ERRO: Falha de comunicação ao tentar enviar mensagem de status para o pedido {order.id}: {e}")
    except httpx.HTTPStatusError as e:
        print(
            f"❌ ERRO: O serviço de chatbot retornou um erro para o pedido {order.id}: {e.response.status_code} - {e.response.text}")