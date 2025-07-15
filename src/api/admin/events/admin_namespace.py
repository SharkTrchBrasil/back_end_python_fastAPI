from socketio import AsyncNamespace
from .handlers.connection_handler import (
    handle_admin_connect,
    handle_admin_disconnect
)
from .handlers.order_handler import handle_update_order_status
from .handlers.store_handler import (
    handle_join_store_room,
    handle_leave_store_room,
    handle_update_store_settings,
    handle_set_consolidated_stores
)

class AdminNamespace(AsyncNamespace):
    def __init__(self, namespace=None):
        super().__init__(namespace)
        self.environ = {}

    async def on_connect(self, sid, environ):
        await handle_admin_connect(self, sid, environ)

    async def on_disconnect(self, sid):
        await handle_admin_disconnect(self, sid)

    async def on_update_order_status(self, sid, data):
        return await handle_update_order_status(self, sid, data)

    async def on_join_store_room(self, sid, data):
        await handle_join_store_room(self, sid, data)

    async def on_leave_store_room(self, sid, data):
        await handle_leave_store_room(self, sid, data)

    async def on_update_store_settings(self, sid, data):
        return await handle_update_store_settings(self, sid, data)

    async def on_set_consolidated_stores(self, sid, data):
        return await handle_set_consolidated_stores(self, sid, data)
