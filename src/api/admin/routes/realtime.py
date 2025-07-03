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
        print(f"[SOCKET] Tentando conectar SID={sid}")
        token = auth.get("token_admin")
        store_id = auth.get("store_id")
        print(f"[SOCKET] Token: {token}")
        print(f"[SOCKET] store_id: {store_id}")

        token_data = verify_access_token(token)
        print(f"[SOCKET] token_data: {token_data}")
        if not token_data:
            raise ConnectionRefusedError("Token inválido")

        email = token_data["sub"]
        print(f"[SOCKET] email extraído do token: {email}")

        with get_db_manager() as db:
            user = db.query(models.User).filter_by(email=email).first()
            if not user:
                raise ConnectionRefusedError("Usuário não encontrado")

            print(f"[SOCKET] user_id: {user.id}")

            has_access = db.query(models.StoreAccess).filter_by(
                user_id=user.id,
                store_id=store_id
            ).first()

            if not has_access:
                raise ConnectionRefusedError("Acesso negado à loja")

            await sio.enter_room(sid, f"store_{store_id}", namespace="/admin")
            await sio.emit("admin_connected", {"store_id": store_id}, to=sid, namespace="/admin")

    except ConnectionRefusedError as e:
        print(f"[SOCKET] Conexão recusada: {e}")
        raise
    except Exception as e:
        print(f"[SOCKET] Erro inesperado: {e}")
        raise ConnectionRefusedError("Erro interno")

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

