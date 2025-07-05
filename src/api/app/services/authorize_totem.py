from src.core import models
from src.socketio_instance import sio


async def authorize_totem(db, token: str):
    totem = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.totem_token == token,
        models.TotemAuthorization.granted.is_(True),
    ).first()
    if not totem or not totem.store:
        return None
    return totem

async def update_sid(db, totem, sid: str):
    totem.sid = sid
    db.commit()

async def enter_store_room(sid: str, store_id: int):
    room_name = f"store_{store_id}"
    await sio.enter_room(sid, room_name)
    return room_name



