from src.api.admin.events.admin_socketio_emitters import (
    emit_store_full_updated,
    product_list_all,
    emit_orders_initial
)

async def emit_initial_data(db, store_id: int, sid: str):
    """Função única para emitir dados iniciais"""
    await emit_store_full_updated(db, store_id, sid)
    await product_list_all(db, store_id, sid)
    await emit_orders_initial(db, store_id, sid)