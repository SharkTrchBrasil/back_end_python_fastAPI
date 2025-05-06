import random
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException

from src.api.admin.schemas.pix_config import StorePixConfig
from src.api.admin.schemas.store import Roles
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore
from src.core.models import Store
from src.api.admin.services import payment as payment_services

router = APIRouter(tags=["Pix Config"], prefix="/stores/{store_id}/pix-configs")


@router.put("")
def create_or_update_pix_config(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
    client_id: str = Form(...),
    client_secret: str = Form(...),
    pix_key: str = Form(...),
    certificate: UploadFile = File(...),
):
    pix_config = StorePixConfig(
        client_id=client_id,
        client_secret=client_secret,
        pix_key=pix_key,
        certificate=certificate.file.read()
    )

    last_config = db.query(models.StorePixConfig).filter_by(store_id=store.id).first()

    hmac_key = random.getrandbits(128)

    try:
        result = payment_services.create_webhook(store.id, pix_config, str(hmac_key))
        if 'webhookUrl' not in result:
            raise HTTPException(status_code=400, detail=f"Erro ao criar webhook: {result}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro ao criar webhook: {e}")

    if last_config is not None:
        db.delete(last_config)
        db.commit()
    config = models.StorePixConfig(**pix_config.model_dump(), store_id=store.id, hmac_key=hmac_key)

    db.add(config)
    db.commit()


@router.get("")
def get_pix_config(
    db: GetDBDep,
    store: Annotated[Store, Depends(GetStore([Roles.OWNER]))],
):
    pix_config = db.query(models.StorePixConfig).filter_by(store_id=store.id).first()
    if not pix_config:
        return None

    result = payment_services.get_webhook(pix_config)
    if 'webhookUrl' not in result:
        return None

    return {
        'pix_key': pix_config.pix_key,
        'is_active': True
    }
