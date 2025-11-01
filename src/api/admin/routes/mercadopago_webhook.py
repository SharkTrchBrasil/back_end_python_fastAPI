"""
Rotas de Webhook do Mercado Pago
================================
Processa notificações de pagamento em tempo real
"""

from fastapi import APIRouter, HTTPException, Request, Response, Header
from typing import Optional
import logging

from src.core.database import GetDBDep
from src.api.admin.services.mercadopago_extended_service import MercadoPagoExtendedService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["MercadoPago Webhook"], prefix="/webhook")


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    db: GetDBDep,
    x_signature: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None)
):
    """
    Processa webhooks do Mercado Pago
    
    Headers esperados:
    - x-signature: Assinatura HMAC para validação
    - x-request-id: ID único da requisição
    """
    
    logger.info("=" * 60)
    logger.info("📨 [WEBHOOK] Recebendo notificação do Mercado Pago")
    
    try:
        # Parse do body
        body = await request.json()
        
        logger.info(f"📦 [WEBHOOK] Tipo: {body.get('type', body.get('topic'))}")
        logger.info(f"📦 [WEBHOOK] ID: {body.get('id')}")
        logger.info(f"📦 [WEBHOOK] Action: {body.get('action')}")
        
        # Log dos headers para debug
        if x_signature:
            logger.info(f"🔐 [WEBHOOK] Signature: {x_signature[:20]}...")
        if x_request_id:
            logger.info(f"🆔 [WEBHOOK] Request ID: {x_request_id}")
        
        # Processa com o serviço
        service = MercadoPagoExtendedService(db)
        
        # Processa o webhook
        success = service.process_webhook(body, x_signature)
        
        if success:
            logger.info("✅ [WEBHOOK] Processado com sucesso")
            return Response(status_code=200)
        else:
            logger.error("❌ [WEBHOOK] Falha no processamento")
            return Response(status_code=400)
            
    except Exception as e:
        logger.error(f"❌ [WEBHOOK] Erro ao processar: {e}")
        logger.exception(e)
        # Retorna 200 mesmo em erro para evitar retry do MP
        return Response(status_code=200)
    finally:
        logger.info("=" * 60)


@router.post("/mercadopago/ipn")
async def mercadopago_ipn(
    request: Request,
    db: GetDBDep,
    topic: Optional[str] = None,
    id: Optional[str] = None
):
    """
    Processa IPN (Instant Payment Notification) do Mercado Pago
    
    Query params esperados:
    - topic: Tipo de notificação (payment, merchant_order, etc)
    - id: ID do recurso
    """
    
    logger.info("=" * 60)
    logger.info("📨 [IPN] Recebendo notificação IPN do Mercado Pago")
    logger.info(f"📦 [IPN] Topic: {topic}")
    logger.info(f"📦 [IPN] ID: {id}")
    
    try:
        # Para IPN, o Mercado Pago envia apenas topic e id
        # Precisamos buscar os detalhes
        if topic == "payment" and id:
            service = MercadoPagoExtendedService(db)
            
            # Busca detalhes do pagamento
            payment_details = service.get_payment_details(id)
            
            # Processa como webhook normal
            webhook_data = {
                "type": "payment",
                "action": "payment.updated",
                "data": {
                    "id": id
                }
            }
            
            success = service.process_webhook(webhook_data)
            
            if success:
                logger.info("✅ [IPN] Processado com sucesso")
            else:
                logger.error("❌ [IPN] Falha no processamento")
        
        # Sempre retorna 200 para evitar retry
        return Response(status_code=200)
        
    except Exception as e:
        logger.error(f"❌ [IPN] Erro ao processar: {e}")
        logger.exception(e)
        return Response(status_code=200)
    finally:
        logger.info("=" * 60)


@router.get("/mercadopago/test")
async def test_webhook():
    """
    Endpoint de teste para verificar se o webhook está acessível
    """
    return {
        "status": "ok",
        "message": "Webhook endpoint is working",
        "timestamp": datetime.utcnow().isoformat()
    }


# Import para timestamp
from datetime import datetime
