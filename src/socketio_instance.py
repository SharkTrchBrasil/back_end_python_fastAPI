import socketio

sio = socketio.AsyncServer(cors_allowed_origins='*', logger=True, engineio_logger=True, async_mode="asgi")

