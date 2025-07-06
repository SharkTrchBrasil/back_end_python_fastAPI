# import socketio
#
# sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True, async_mode="asgi")



# src/socketio_instance.py
import socketio
from src.api.admin.admin_namespace import AdminNamespace


sio = socketio.AsyncServer(
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    async_mode="asgi"
)

# Registra namespaces
sio.register_namespace(AdminNamespace('/admin'))  # Painel administrativo
