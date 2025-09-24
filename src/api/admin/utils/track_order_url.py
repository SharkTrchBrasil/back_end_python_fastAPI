# Crie esta nova função auxiliar
from src.core import models
from src.core.config import config


def _get_tracking_link(order: models.Order) -> str:
    """Gera o link de rastreamento para um pedido."""
    return f"https://{order.store.url_slug}.{config.PLATFORM_DOMAIN}/orders/waiting?order={order.public_id}"
