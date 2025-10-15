# src/api/routers/webhooks/subscription_webhook.py

from fastapi import APIRouter, Response, Request, status, Form, Query, HTTPException
from typing import Annotated
import logging

from src.api.admin.services.payment import get_notification
from src.core import models
from src.core.database import GetDBDep
from src.core.config import config

router = APIRouter(tags=["Webhook"], prefix="/webhook")
logger = logging.getLogger(__name__)

# ✅ IPs oficiais da Efí (ATUALIZE COM A LISTA COMPLETA)
EFI_WEBHOOK_IPS = [
    "177.54.206.130",
    "177.54.206.131",
    # TODO: Adicionar mais IPs da documentação oficial
]


def get_client_ip(request: Request) -> str:
    """Extrai o IP real do cliente"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host


def is_efi_ip(request: Request) -> bool:
    """Valida se a requisição vem de um IP da Efí"""
    client_ip = get_client_ip(request)
    is_valid = client_ip in EFI_WEBHOOK_IPS

    logger.info("webhook_ip_validation", extra={
        "client_ip": client_ip,
        "is_valid": is_valid
    })

    return is_valid


@router.post("/subscriptions")
def post_billing_notification(
        request: Request,
        db: GetDBDep,
        notification: Annotated[str, Form()],
        token: str = Query(None, description="Token de segurança")
):
    """
    ✅ WEBHOOK SEGURO - Versão Produção

    Segurança em 3 camadas:
    1. Certificado mTLS (Efí)
    2. Token customizado
    3. Validação de IP
    """

    # 🔒 CAMADA 1: Token
    if not token or token != config.WEBHOOK_TOKEN:
        logger.warning("webhook_rejected_invalid_token", extra={
            "client_ip": get_client_ip(request)
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token inválido"
        )

    # 🔒 CAMADA 2: IP (✅ ATIVADO EM PRODUÇÃO)
    if not is_efi_ip(request):
        logger.warning("webhook_rejected_invalid_ip", extra={
            "client_ip": get_client_ip(request)
        })
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="IP não autorizado"
        )

    try:
        events = get_notification(notification)

        last_charge_event = max(
            (event for event in events if event.get('type') == 'charge'),
            key=lambda e: e.get('id', 0),
            default=None
        )

        if not last_charge_event:
            logger.info("webhook_no_charge_event")
            return Response(status_code=status.HTTP_200_OK)

        charge_id = last_charge_event.get('identifiers', {}).get('charge_id')
        new_status = last_charge_event.get('status', {}).get('current')

        if not charge_id:
            logger.warning("webhook_missing_charge_id")
            return Response(status_code=status.HTTP_200_OK)

        db_charge = db.query(models.MonthlyCharge).filter_by(
            gateway_transaction_id=str(charge_id)
        ).first()

        if not db_charge or not db_charge.subscription:
            logger.warning("webhook_charge_not_found", extra={
                "charge_id": charge_id
            })
            return Response(status_code=status.HTTP_200_OK)

        old_status = db_charge.status

        if new_status == 'paid':
            db_charge.status = "paid"
            if db_charge.subscription.status == 'past_due':
                db_charge.subscription.status = "active"

            logger.info("webhook_charge_paid", extra={
                "charge_id": db_charge.id,
                "store_id": db_charge.store_id,
                "old_status": old_status
            })

        elif new_status in ['canceled', 'failed']:
            db_charge.status = "failed"
            db_charge.subscription.status = "past_due"

            logger.warning("webhook_charge_failed", extra={
                "charge_id": db_charge.id,
                "store_id": db_charge.store_id,
                "new_status": new_status,
                "old_status": old_status
            })

        else:
            logger.info("webhook_status_ignored", extra={
                "charge_id": charge_id,
                "status": new_status
            })

        db.commit()
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        db.rollback()
        logger.error("webhook_processing_error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)

        return Response(status_code=status.HTTP_200_OK)