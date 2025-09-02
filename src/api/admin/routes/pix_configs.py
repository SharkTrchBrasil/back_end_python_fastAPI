import datetime
import random
from typing import Annotated

from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException

from src.api.schemas.financial.pix_config import StorePixConfig


from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStore, GetStoreDep
from src.core.models import Store
from src.api.app.services import payment as payment_services
from dateutil import parser

from src.core.utils.enums import Roles

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

    return {
        'pix_key': pix_config.pix_key,
        'is_active': True
    }


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


@router.get("/new-charge")
def new_charge(
    db: GetDBDep,
    store: GetStoreDep
):
    pix_config = db.query(models.StorePixConfig).filter_by(store_id=store.id).first()
    efi_charge = payment_services.create_charge(pix_config, 250, '60025637096', 'Teste 123')
    db_charge = models.Charge(
        status='pending',
        amount=int(float(efi_charge['valor']['original']) * 100),
        tx_id=efi_charge['txid'],
        copy_key=efi_charge['pixCopiaECola'],
        store_id=store.id,
        expires_at=parser.isoparse(efi_charge['calendario']['criacao']) +
                   datetime.timedelta(seconds=int(efi_charge['calendario']['expiracao']))
    )
    db.add(db_charge)
    db.commit()
    db.refresh(db_charge)
    return db_charge

@router.get("/devolution")
def new_devolution(
    e2eid: str,
    amount: int,
    store: GetStoreDep,
    db: GetDBDep,
):
    pix_config = db.query(models.StorePixConfig).filter_by(store_id=store.id).first()
    result = payment_services.pix_devolution(pix_config, e2eid, amount)
    db_devolution = models.PixDevolution(
        store_id=store.id,
        e2e_id=e2eid,
        amount=amount,
        status=result['status'],
        rtr_id=result['rtrId'],
    )
    db.add(db_devolution)
    db.commit()


@router.post("/resend")
def resend(
    e2eids: list[str],
    store: GetStoreDep,
    db: GetDBDep,
):
    pix_config = db.query(models.StorePixConfig).filter_by(store_id=store.id).first()
    return payment_services.resend_events(pix_config, e2eids)