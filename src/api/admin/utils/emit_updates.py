import asyncio

from sqlalchemy.orm import selectinload

from src.api.admin.socketio.emitters import admin_emit_products_updated, admin_emit_store_updated
from src.api.app.services.rating import get_store_ratings_summary
from src.api.app.socketio.socketio_emitters import emit_products_updated, emit_store_updated
from src.api.schemas.products.product import ProductOut
from src.core import models
from src.core.cache.cache_manager import cache_manager, logger
from src.core.models import Category, Variant
from src.socketio_instance import sio


async def emit_updates_products(db, store_id: int):
    """
    Dispara os eventos de atualização para o admin e para o totem
    de forma concorrente e segura.
    """
    try:
        print(f"🚀 Disparando eventos de atualização para a loja {store_id}...")

        # ✅ 1. USA asyncio.gather PARA EXECUTAR AS TAREFAS EM PARALELO
        #    Isso é mais rápido, pois as duas emissões acontecem ao mesmo tempo.
        await asyncio.gather(
            admin_emit_products_updated(db, store_id),
            emit_products_updated(db, store_id)
        )

        # ✅ ADICIONAR: Invalida cache de produtos
        cache_manager.on_product_change(store_id)

        logger.info(f"✅ Produtos atualizados e cache invalidado para loja {store_id}")

        # ✅ 2. PRINT CORRETAMENTE INDENTADO
        print(f"✅ Eventos para a loja {store_id} emitidos com sucesso.")

    except Exception as e:
        # ✅ 3. TRATAMENTO DE ERROS
        #    Se algo der errado com o  Socket.IO, apenas registramos o erro
        #    e não quebramos a requisição principal da API.
        print(f"❌ Erro ao emitir eventos para a loja {store_id}: {e}")


import asyncio



async def emit_store_updates(db, store_id: int):
    """
    Dispara os eventos de atualização de dados da LOJA para o admin e para o totem
    de forma concorrente e segura.
    """
    try:
        print(f"🚀 Disparando eventos de atualização da loja {store_id}...")

        # Usa asyncio.gather para executar as duas emissões ao mesmo tempo
        await asyncio.gather(
            admin_emit_store_updated(db, store_id),
            # Supondo que você tenha ou crie um emissor para o totem também
             emit_store_updated(db, store_id)
        )
        # ✅ ADICIONAR: Invalida cache de produtos
       # cache_manager.on_product_change(store_id)
        print(f"✅ Eventos da loja {store_id} emitidos com sucesso.")

    except Exception as e:
        # Se algo der errado, apenas registramos o erro
        print(f"❌ Erro ao emitir eventos da loja {store_id}: {e}")



