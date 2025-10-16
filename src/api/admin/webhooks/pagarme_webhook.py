"""
Webhook do Pagar.me com Autenticação Básica
===========================================
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Response, Request, status, HTTPException, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging
import json
import secrets

from src.core import models
from src.core.database import GetDBDep
from src.core.config import config

router = APIRouter(tags=["Webhooks - Pagar.me"], prefix="/webhook")
logger = logging.getLogger(__name__)

# ✅ Configuração de autenticação básica
security = HTTPBasic()


def verify_webhook_auth(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """
    ✅ Valida credenciais de autenticação básica do webhook

    Usa timing-safe comparison para prevenir timing attacks
    """
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        config.PAGARME_WEBHOOK_USER.encode("utf8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        config.PAGARME_WEBHOOK_PASSWORD.encode("utf8")
    )

    if not (correct_username and correct_password):
        logger.warning("pagarme_webhook_invalid_credentials", extra={
            "username_provided": credentials.username
        })
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )

    return True


@router.post("/pagarme")
async def pagarme_webhook_handler(
        request: Request,
        db: GetDBDep,
        authenticated: bool = Depends(verify_webhook_auth)
):
    """
    ✅ WEBHOOK SEGURO - Pagar.me com Autenticação e Idempotência
    """

    logger.info("pagarme_webhook_received", extra={
        "url": str(request.url),
        "method": request.method,
        "client_ip": request.client.host,
        "authenticated": authenticated
    })

    # ═══════════════════════════════════════════════════════════
    # 1. CAPTURA O PAYLOAD
    # ═══════════════════════════════════════════════════════════

    try:
        body = await request.body()
        body_str = body.decode('utf-8')

        logger.info("pagarme_webhook_payload_received", extra={
            "payload_size": len(body),
            "payload_preview": body_str[:200]
        })

    except Exception as e:
        logger.error("pagarme_webhook_payload_error", extra={
            "error": str(e)
        }, exc_info=True)
        return Response(status_code=status.HTTP_200_OK)

    # ═══════════════════════════════════════════════════════════
    # 2. PARSE DO EVENTO
    # ═══════════════════════════════════════════════════════════

    try:
        event_data = json.loads(body_str)
        event_id = event_data.get("id")  # ✅ ID único do evento
        event_type = event_data.get("type")
        charge_data = event_data.get("data")

        if not charge_data or not event_id:
            logger.warning("pagarme_webhook_incomplete_data", extra={
                "event_type": event_type,
                "has_charge_data": bool(charge_data),
                "has_event_id": bool(event_id)
            })
            return Response(status_code=status.HTTP_200_OK)

        charge_id = charge_data.get("id")
        charge_status = charge_data.get("status")

        logger.info("pagarme_webhook_processing", extra={
            "event_id": event_id,
            "event_type": event_type,
            "charge_id": charge_id,
            "charge_status": charge_status
        })

        # ═══════════════════════════════════════════════════════
        # 3. VERIFICAÇÃO DE IDEMPOTÊNCIA
        # ═══════════════════════════════════════════════════════

        processed_event = db.query(models.ProcessedWebhookEvent).filter_by(
            event_id=event_id,
            event_type=event_type
        ).first()

        if processed_event:
            logger.info("pagarme_webhook_already_processed", extra={
                "event_id": event_id,
                "event_type": event_type,
                "processed_at": processed_event.processed_at.isoformat()
            })
            return Response(status_code=status.HTTP_200_OK)

        # ═══════════════════════════════════════════════════════
        # 4. BUSCA A COBRANÇA NO BANCO
        # ═══════════════════════════════════════════════════════

        db_charge = db.query(models.MonthlyCharge).filter_by(
            gateway_transaction_id=str(charge_id)
        ).first()

        if not db_charge:
            logger.warning("pagarme_webhook_charge_not_found", extra={
                "charge_id": charge_id,
                "event_type": event_type
            })

            # ✅ Mesmo assim, registra como processado
            new_event = models.ProcessedWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload=event_data,
                processed_at=datetime.now(timezone.utc)
            )
            db.add(new_event)
            db.commit()

            return Response(status_code=status.HTTP_200_OK)

        if not db_charge.subscription:
            logger.warning("pagarme_webhook_charge_without_subscription", extra={
                "charge_id": charge_id,
                "db_charge_id": db_charge.id
            })
            return Response(status_code=status.HTTP_200_OK)

        old_status = db_charge.status
        old_subscription_status = db_charge.subscription.status

        # ═══════════════════════════════════════════════════════
        # 5. ATUALIZA STATUS CONFORME O EVENTO
        # ═══════════════════════════════════════════════════════

        if event_type == "charge.paid":
            db_charge.status = "paid"

            # Reativa assinatura se estava em atraso
            if db_charge.subscription.status in ['past_due', 'unpaid']:
                db_charge.subscription.status = "active"

            logger.info("pagarme_webhook_charge_paid", extra={
                "charge_id": db_charge.id,
                "store_id": db_charge.store_id,
                "old_status": old_status,
                "old_subscription_status": old_subscription_status,
                "new_subscription_status": db_charge.subscription.status
            })

        elif event_type in ["charge.payment_failed", "charge.refunded", "charge.partial_canceled"]:
            db_charge.status = "failed"
            db_charge.subscription.status = "past_due"

            logger.warning("pagarme_webhook_charge_failed", extra={
                "charge_id": db_charge.id,
                "store_id": db_charge.store_id,
                "event_type": event_type,
                "old_status": old_status,
                "charge_status": charge_status
            })

        else:
            logger.info("pagarme_webhook_event_ignored", extra={
                "event_type": event_type,
                "charge_id": charge_id
            })

            # ✅ Registra como processado mesmo se ignorado
            new_event = models.ProcessedWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload=event_data,
                processed_at=datetime.now(timezone.utc)
            )
            db.add(new_event)
            db.commit()

            return Response(status_code=status.HTTP_200_OK)

        # ═══════════════════════════════════════════════════════
        # 6. REGISTRA EVENTO COMO PROCESSADO
        # ═══════════════════════════════════════════════════════

        new_event = models.ProcessedWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            payload=event_data,
            processed_at=datetime.now(timezone.utc)
        )
        db.add(new_event)

        # ✅ SALVA TUDO NO BANCO
        db.commit()

        logger.info("pagarme_webhook_processed_successfully", extra={
            "event_id": event_id,
            "charge_id": db_charge.id,
            "store_id": db_charge.store_id,
            "event_type": event_type,
            "final_status": db_charge.status
        })

        return Response(status_code=status.HTTP_200_OK)

    except json.JSONDecodeError as e:
        logger.error("pagarme_webhook_invalid_json", extra={
            "error": str(e)
        }, exc_info=True)
        return Response(status_code=status.HTTP_200_OK)

    except Exception as e:
        db.rollback()
        logger.error("pagarme_webhook_processing_error", extra={
            "error": str(e),
            "error_type": type(e).__name__
        }, exc_info=True)

        return Response(status_code=status.HTTP_200_OK)


@router.get("/pagarme/health")
async def pagarme_webhook_health():
    """
    Endpoint de health check (sem autenticação)
    """
    return {
        "status": "healthy",
        "webhook": "pagarme",
        "version": "1.0.0",
        "auth": "basic"
    }