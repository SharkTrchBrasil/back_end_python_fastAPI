import socketio
from src.core.config import config

# Restrict CORS for Socket.IO in production; allow all in development for local tooling
cors_origins = "*" if config.is_development else config.get_allowed_origins_list()

# Enable Redis manager when REDIS_URL is configured (scales Socket.IO horizontally)
client_manager = None
try:
	if config.REDIS_URL:
		client_manager = socketio.AsyncRedisManager(config.REDIS_URL)
except Exception:
	client_manager = None

sio = socketio.AsyncServer(
	cors_allowed_origins=cors_origins,
	logger=True,
	engineio_logger=True,
	async_mode="asgi",
	client_manager=client_manager
)

