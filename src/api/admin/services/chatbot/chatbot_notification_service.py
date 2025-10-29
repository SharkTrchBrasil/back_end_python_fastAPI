# src/api/admin/services/chatbot_notification_service.py - VERSÃO FINAL (REFATORADA)

import os
from sqlalchemy.orm import Session
from typing import Optional

from src.api.admin.services.chatbot.chatbot_client import chatbot_client
# ❌ REMOVIDO: importação de format_phone (não usada)
from src.api.admin.utils.track_order_url import _get_tracking_link
from src.core import models
from src.core.config import config
from src.core.utils.enums import OrderStatus

STATUS_TO_MESSAGE_KEY = {
    OrderStatus.PREPARING: 'order_accepted',
    OrderStatus.READY: 'order_ready',
    OrderStatus.ON_ROUTE: 'order_on_route',
    OrderStatus.DELIVERED: 'order_delivered',
    OrderStatus.CANCELED: 'order_canceled',
}


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
    tracking_link = _get_tracking_link(order)
    message_parts.append("Acompanhe seu pedido no link:")
    message_parts.append(tracking_link)

    return "\n".join(message_parts)


# ✅ NOVA FUNÇÃO HELPER (Refatorada)
def _get_formatted_customer_phone(raw_phone: str) -> Optional[str]:
    """
    Limpa, valida e formata o número de telefone para o padrão E.164 (55+DDD+Numero).
    Retorna None se o número for inválido.
    """
    if not raw_phone:
        return None

    try:
        # 1. Pega apenas os dígitos do número
        clean_phone = "".join(filter(str.isdigit, raw_phone))

        # 2. Se o número já tiver o 55 no início (seja com 8 ou 9 dígitos), ele já está pronto.
        if clean_phone.startswith('55'):
            # Verifica se o tamanho é válido (12 = 55+DDD+8dígitos, 13 = 55+DDD+9dígitos)
            if len(clean_phone) not in [12, 13]:
                raise ValueError(f"Número '{raw_phone}' com 55 tem tamanho inválido.")
            return clean_phone
        # 3. Se for um número local (sem 55), apenas adicionamos o código do país.
        else:
            # Verifica se o tamanho é válido (10 = DDD+8dígitos, 11 = DDD+9dígitos)
            if len(clean_phone) not in [10, 11]:
                raise ValueError(f"Número '{raw_phone}' sem 55 tem tamanho inválido.")
            return f"55{clean_phone}"

    except ValueError as e:
        print(f"AVISO: Número de telefone inválido: {e}")
        return None


# --- FUNÇÃO PARA ENVIAR O RESUMO ---
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

    raw_phone = order.customer.phone if order.customer else order.customer_phone

    # ✅ LÓGICA DE TELEFONE CENTRALIZADA
    customer_phone = _get_formatted_customer_phone(raw_phone)
    if not customer_phone:
        print(f"AVISO: Pedido {order.id} não possui telefone de cliente válido. Resumo não enviado.")
        return

    print(f"DEBUG: Número final e limpo enviado para a API: {customer_phone}")

    final_message = _build_order_summary_message(order)

    # ✅ USANDO O NOVO CLIENTE ROBUSTO
    success = await chatbot_client.send_message(
        store_id=order.store_id,
        number=customer_phone,
        message=final_message
    )

    if success:
        print(f"✅ Resumo do pedido {order.id} enviado com sucesso.")
    else:
        print(f"❌ ERRO ao enviar resumo do pedido {order.id}.")


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

    # 4. Busca o telefone (com fallback)
    raw_phone = None
    try:
        if order.customer and order.customer.phone:
            raw_phone = order.customer.phone
        elif order.customer_phone:
            raw_phone = order.customer_phone
    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao tentar acessar o telefone do cliente: {e}")
        return

    # ✅ LÓGICA DE TELEFONE CENTRALIZADA
    customer_phone = _get_formatted_customer_phone(raw_phone)
    if not customer_phone:
        print(f"AVISO FINAL: Pedido {order.id} não possui telefone de cliente válido. Mensagem não enviada.")
        return

    print(f"DEBUG: Número final e limpo enviado para a API: {customer_phone}")

    # 5. Formata a mensagem final
    content_to_send = message_config.final_content
    final_message = _format_message(content_to_send, order, order.store)

    # 6. Envia a requisição usando o novo cliente robusto
    success = await chatbot_client.send_message(
        store_id=order.store_id,
        number=customer_phone,
        message=final_message
    )

    if success:
        print(f"✅ Mensagem de status '{order.order_status.value}' enviada com sucesso para o pedido {order.id}.")
    else:
        print(f"❌ ERRO: Falha ao enviar mensagem de status para o pedido {order.id}.")