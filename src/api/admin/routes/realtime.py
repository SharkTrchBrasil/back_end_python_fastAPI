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
        print(f"[ADMIN SOCKET] Conectando SID={sid}")
        token = auth.get("totem_token")
        store_url = auth.get("store_url")

        if not token or not store_url:
            raise ConnectionRefusedError("Token ou store_url ausente")

        with get_db_manager() as db:
            totem = db.query(models.TotemAuthorization).filter_by(
                totem_token=token,
                store_url=store_url,
                granted=True
            ).first()

            if not totem:
                raise ConnectionRefusedError("Token inválido ou não autorizado")

            # Atualiza o SID para rastrear desconexão
            totem.sid = sid
            db.commit()

            room_name = f"store_{totem.store_id}"
            await sio.enter_room(sid, room_name, namespace="/admin")

            await sio.emit("admin_connected", {"store_id": totem.store_id}, to=sid, namespace="/admin")
            print(f"[ADMIN SOCKET] Conectado e entrou na sala {room_name}")

    except Exception as e:
        print(f"[ADMIN SOCKET] Erro na conexão: {e}")
        raise ConnectionRefusedError("Falha na autenticação")


@sio.event
async def disconnect(sid, reason):
    print(f"[SOCKET] Desconectado: SID={sid}, reason={reason}")

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()
            print(f"[SOCKET] SID {sid} saiu da sala store_{totem.store_id}")
