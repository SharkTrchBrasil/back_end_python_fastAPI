from fastapi import APIRouter, Body, HTTPException

from src.core import models
from src.core.database import GetDBDep

router = APIRouter(tags=["Webhooks"], prefix='/stores/{store_id}/pix-webhook')

@router.post("")
def pix_webhook(
    db: GetDBDep,
    store_id: int,
    hmac: str,
    body: dict = Body(...)
):
    if 'evento' in body and body['evento'] == 'teste_webhook':
        return

    # TODO: Verificar o IP
    pix_config = db.query(models.StorePixConfig).filter_by(store_id=store_id).first()

    if pix_config is None or pix_config.hmac_key != hmac:
        raise HTTPException(status_code=401, detail="Unauthorized")

    for event in body['pix']:
        charge = db.query(models.Charge).filter_by(tx_id=event['txid']).first()
        if not charge:
            raise HTTPException(status_code=400, detail="txid does not exist")

        charge.e2e_id = event['endToEndId']

        if 'devolucoes' in event:
            total_devolution = 0

            for devolution in event['devolucoes']:
                db_devolution = db.query(models.PixDevolution).filter_by(rtr_id=devolution['rtrId']).first()
                db_devolution.status = devolution['status']
                db_devolution.reason = devolution['motivo'] if 'motivo' in devolution else None

                if devolution['status'] == 'DEVOLVIDO':
                    total_devolution += float(devolution['valor'])

            print('TOTAL_DEVOLUTION' + str(int(total_devolution*100)))
            print('AMOUNT' + str(charge.amount))

            if int(total_devolution*100) == charge.amount:
                charge.status = 'cancelled'
            else:
                charge.status = 'partiallyCancelled'
        else:
            charge.status = 'paid'

            # TODO: Enviar ao totem que o pedido foi pago

        db.commit()