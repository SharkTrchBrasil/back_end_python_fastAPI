# src/api/app/events/totem_namespace.py

from socketio import AsyncNamespace


from src.api.app.events.handlers.connection_handler import handler_totem_on_connect, handler_totem_on_disconnect



class TotemNamespace(AsyncNamespace):
    def __init__(self, namespace=None):
        super().__init__(namespace or "/")


    async def on_connect(self, sid, environ):
        await handler_totem_on_connect(self, sid, environ)

    async def on_disconnect(self, sid):
        await handler_totem_on_disconnect(self, sid)
