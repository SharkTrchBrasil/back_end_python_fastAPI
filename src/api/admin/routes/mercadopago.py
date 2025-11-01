"""
Rotas para integração com Mercado Pago
======================================
Gerencia conexão, pagamentos e webhooks
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.core.database import GetDBDep
from src.core import models
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.schemas.financial.mercadopago import (
    MercadoPagoConnectRequest,
    MercadoPagoConfigSchema,
    MercadoPagoPaymentRequest,
    MercadoPagoPaymentResponse,
    MercadoPagoRefundRequest
)
from src.api.admin.services.mercadopago_service import (
    get_mercadopago_service,
    MercadoPagoError
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mercadopago", tags=["Mercado Pago"])


@router.post("/{store_id}/connect")
async def connect_mercadopago(
    store_id: int,
    request_data: MercadoPagoConnectRequest,
    request: Request,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Conecta uma loja ao Mercado Pago
    
    Args:
        store_id: ID da loja
        request_data: Credenciais do Mercado Pago
        request: Request HTTP
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Status da conexão
    """

    logger.info(f"🔌 [MP Connect] Loja {store_id} conectando ao Mercado Pago")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    # Testa a conexão com as credenciais
    try:
        service = get_mercadopago_service()
        user_info = service._make_request(
            "GET",
            "/users/me",
            access_token=request_data.access_token
        )
        
        user_id = user_info.get('id')
        logger.info(f"✅ Credenciais válidas! User ID: {user_id}")
    except MercadoPagoError as e:
        logger.error(f"❌ Credenciais inválidas: {e}")
        raise HTTPException(status_code=400, detail=f"Credenciais inválidas: {str(e)}")

    # Salva as credenciais (criptografadas automaticamente)
    store.mercadopago_access_token = request_data.access_token
    store.mercadopago_public_key = request_data.public_key
    store.mercadopago_user_id = str(user_id)
    store.mercadopago_connected_at = datetime.now(timezone.utc)
    store.mercadopago_last_sync_at = datetime.now(timezone.utc)

    db.commit()

    logger.info(f"✅ Loja {store_id} conectada com sucesso ao Mercado Pago")

    return {
        "success": True,
        "message": "Loja conectada ao Mercado Pago com sucesso",
        "user_id": user_id
    }


@router.get("/{store_id}/status")
async def get_mercadopago_status(
    store_id: int,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Retorna o status da conexão com Mercado Pago
    
    Args:
        store_id: ID da loja
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Status da conexão
    """

    logger.info(f"📊 [MP Status] Verificando status da loja {store_id}")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    is_connected = store.mercadopago_access_token is not None

    if is_connected:
        # Testa a conexão
        try:
            is_valid = mercadopago_service.test_connection(store.mercadopago_access_token)
        except Exception as e:
            logger.error(f"❌ Erro ao testar conexão: {e}")
            is_valid = False
    else:
        is_valid = False

    return MercadoPagoConfigSchema(
        is_connected=is_connected and is_valid,
        access_token_encrypted="***" if is_connected else None,
        public_key=store.mercadopago_public_key,
        user_id=store.mercadopago_user_id,
        connected_at=store.mercadopago_connected_at,
        last_sync_at=store.mercadopago_last_sync_at
    )


@router.post("/{store_id}/payment/pix")
async def create_pix_payment(
    store_id: int,
    payment_data: MercadoPagoPaymentRequest,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Cria um pagamento PIX via Mercado Pago
    
    Args:
        store_id: ID da loja
        payment_data: Dados do pagamento
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Dados do pagamento criado
    """

    logger.info(f"💚 [MP PIX] Criando pagamento para loja {store_id}")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    # Verifica se está conectada
    if not store.mercadopago_access_token:
        raise HTTPException(
            status_code=400,
            detail="Loja não está conectada ao Mercado Pago"
        )

    # Cria o pagamento
    try:
        service = get_mercadopago_service()
        payment_response = service.create_pix_payment(
            amount=payment_data.amount,
            description=payment_data.description,
            payer_email=payment_data.payer_email,
            payer_first_name=payment_data.payer_first_name,
            payer_last_name=payment_data.payer_last_name,
            payer_document_type=payment_data.payer_document_type,
            payer_document_number=payment_data.payer_document_number,
            store_access_token=store.mercadopago_access_token,
            metadata={
                **(payment_data.metadata or {}),
                "store_id": str(store_id)
            }
        )
    except MercadoPagoError as e:
        logger.error(f"❌ Erro ao criar pagamento: {e}")
        raise HTTPException(status_code=400, detail=f"Erro ao criar pagamento: {str(e)}")

    # Extrai dados do PIX
    point_of_interaction = payment_response.get('point_of_interaction', {})
    transaction_data = point_of_interaction.get('transaction_data', {})

    response = MercadoPagoPaymentResponse(
        payment_id=str(payment_response.get('id')),
        status=payment_response.get('status'),
        status_detail=payment_response.get('status_detail'),
        qr_code_base64=transaction_data.get('qr_code_base64'),
        qr_code=transaction_data.get('qr_code'),
        ticket_url=None,
        transaction_amount=payment_response.get('transaction_amount'),
        created_at=datetime.fromisoformat(
            payment_response.get('date_created').replace('Z', '+00:00')
        ),
        payer=payment_response.get('payer'),
        point_of_interaction=point_of_interaction
    )

    logger.info(f"✅ Pagamento PIX criado: {response.payment_id}")

    return response


@router.get("/payment/{payment_id}")
async def get_payment_status(
    payment_id: str,
    store_id: int,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Consulta status de um pagamento
    
    Args:
        payment_id: ID do pagamento
        store_id: ID da loja
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Status do pagamento
    """

    logger.info(f"🔍 [MP Status] Consultando pagamento {payment_id}")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    if not store.mercadopago_access_token:
        raise HTTPException(
            status_code=400,
            detail="Loja não está conectada ao Mercado Pago"
        )

    try:
        payment_data = mercadopago_service.get_payment(
            payment_id=payment_id,
            store_access_token=store.mercadopago_access_token
        )
    except MercadoPagoError as e:
        logger.error(f"❌ Erro ao consultar pagamento: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    return payment_data


@router.post("/payment/{payment_id}/refund")
async def refund_payment(
    payment_id: str,
    store_id: int,
    refund_data: MercadoPagoRefundRequest,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Reembolsa um pagamento
    
    Args:
        payment_id: ID do pagamento
        store_id: ID da loja
        refund_data: Dados do reembolso
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Status do reembolso
    """

    logger.info(f"↩️ [MP Refund] Reembolsando pagamento {payment_id}")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    if not store.mercadopago_access_token:
        raise HTTPException(
            status_code=400,
            detail="Loja não está conectada ao Mercado Pago"
        )

    try:
        refund_response = mercadopago_service.refund_payment(
            payment_id=payment_id,
            amount=refund_data.amount,
            store_access_token=store.mercadopago_access_token
        )
    except MercadoPagoError as e:
        logger.error(f"❌ Erro ao reembolsar: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(f"✅ Reembolso realizado com sucesso")

    return refund_response


@router.delete("/{store_id}/disconnect")
async def disconnect_mercadopago(
    store_id: int,
    db: Session = Depends(GetDBDep),
    current_user: models.User = Depends(authorize_admin_by_jwt)
):
    """
    Desconecta uma loja do Mercado Pago
    
    Args:
        store_id: ID da loja
        db: Sessão do banco
        current_user: Usuário autenticado
    
    Returns:
        Status da desconexão
    """

    logger.info(f"🔌 [MP Disconnect] Desconectando loja {store_id}")

    # Busca a loja
    store = db.query(models.Store).filter_by(id=store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    # Limpa as credenciais
    store.mercadopago_access_token = None
    store.mercadopago_public_key = None
    store.mercadopago_user_id = None
    store.mercadopago_connected_at = None
    store.mercadopago_last_sync_at = None

    db.commit()

    logger.info(f"✅ Loja {store_id} desconectada do Mercado Pago")

    return {
        "success": True,
        "message": "Loja desconectada do Mercado Pago"
    }



