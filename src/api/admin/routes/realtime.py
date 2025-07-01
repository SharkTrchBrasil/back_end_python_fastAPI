import datetime
from operator import or_
from urllib.parse import parse_qs


import sqlalchemy
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.services.order_code import generate_unique_public_id, gerar_sequencial_do_dia

from src.api.app.schemas.new_order import NewOrder
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.check_variants import validate_order_variants

from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)

from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

from src.api.app.schemas.order import Order
from src.core.helpers.authorize_totem import authorize_totem
from src.core.models import Coupon
from src.api.app.schemas.coupon import Coupon as CouponSchema
from src.core.security import verify_access_token
from src.socketio_instance import sio


@sio.event(namespace="/admin")
async def connect(sid, environ, auth):
    try:
        print(f"\n[SOCKET ADMIN] Tentando conectar: SID={sid}")

        # 1. Obtem o token da autenticação
        token = (
            auth.get("token_admin")
            if auth
            else parse_qs(environ.get("QUERY_STRING", "")).get("token_admin", [None])[0]
        )
        print(f"[SOCKET ADMIN] Token recebido: {token}")

        if not token:
            print(f"[SOCKET ADMIN] Token ausente para SID {sid}")
            raise ConnectionRefusedError("Missing admin token")

        # 2. Decodifica e valida o token
        token_data = verify_access_token(token)
        if not token_data or "store_id" not in token_data:
            print(f"[SOCKET ADMIN] Token inválido ou sem store_id")
            raise ConnectionRefusedError("Invalid or expired token")

        store_id = token_data["store_id"]
        print(f"[SOCKET ADMIN] store_id extraído do token: {store_id}")

        # 3. Consulta o TotemAuthorization baseado no store_id
        with get_db_manager() as db:
            totem = db.query(models.TotemAuthorization).filter(
                models.TotemAuthorization.store_id == store_id,
                models.TotemAuthorization.granted.is_(True),
            ).first()

            if not totem or not totem.store:
                print(f"[SOCKET ADMIN] Totem não encontrado para store_id={store_id}")
                raise ConnectionRefusedError("Totem not authorized or store not found")

            # (Opcional) Salva o SID se necessário
            totem.sid = sid
            db.commit()

        # 4. Entra na sala da loja
        room_name = f"store_{store_id}"
        await sio.enter_room(sid, room_name, namespace="/admin")
        print(f"[SOCKET ADMIN] Conectado à sala: {room_name}")

        # 5. Emite evento de confirmação de conexão
        await sio.emit(
            "admin_connected",
            {
                "status": "connected",
                "store_id": store_id,
            },
            to=sid,
            namespace="/admin",
        )

    except ConnectionRefusedError as e:
        print(f"[SOCKET ADMIN] Conexão recusada: {e}\n")
        raise
    except Exception as e:
        print(f"[SOCKET ADMIN] Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
        raise ConnectionRefusedError("Internal error")

# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print("disconnect", sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()

