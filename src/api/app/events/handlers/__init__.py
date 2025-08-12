# Versão final do __init__.py
print("🔵 Carregando event handlers do Socket.IO...")

from . import cart_handler
from . import order_handler
from . import coupon_handler
from . import session_handler

print("✅ Event handlers carregados com sucesso.")