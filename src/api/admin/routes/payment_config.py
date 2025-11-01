"""
Payment Configuration Routes - Configuração de Pagamentos por Loja
==================================================================
Rotas admin para configurar métodos de pagamento
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.api.admin.services.payment_multitenant_service import PaymentMultiTenantService
from src.core.database import GetDBDep
from src.core.dependencies import GetAuditLoggerDep, GetCurrentUserDep, GetStoreDep
from src.core.utils.enums import AuditAction, AuditEntityType

# Router para configuração de pagamentos
router = APIRouter(
    tags=["Payment Configuration"],
    prefix="/stores/{store_id}/payment-config"
)


# ═══════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════

class MercadoPagoConfig(BaseModel):
    """Configuração do Mercado Pago"""
    
    access_token: str = Field(..., min_length=20, description="Token de acesso da conta MP")
    public_key: str = Field(..., min_length=20, description="Chave pública para checkout")
    webhook_secret: Optional[str] = Field(None, description="Secret para validar webhooks")
    sandbox_mode: bool = Field(True, description="Modo sandbox (teste)")


class PIXDirectConfig(BaseModel):
    """Configuração de PIX direto"""
    
    pix_key: str = Field(..., description="Chave PIX")
    pix_key_type: str = Field(
        ...,
        pattern="^(cpf|cnpj|email|phone|random)$",
        description="Tipo da chave"
    )
    merchant_name: Optional[str] = Field(None, max_length=100, description="Nome do recebedor")
    merchant_city: Optional[str] = Field(None, max_length=100, description="Cidade do recebedor")


class PaymentMethodToggle(BaseModel):
    """Habilitar/desabilitar método de pagamento"""
    
    enabled: bool = Field(..., description="Status do método")


class ServiceFeeConfig(BaseModel):
    """Configuração de taxas"""
    
    service_fee_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Taxa de serviço (%)"
    )
    platform_fee_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Taxa da plataforma (%)"
    )
    minimum_order_value: int = Field(
        ...,
        ge=0,
        description="Valor mínimo do pedido (em centavos)"
    )


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO MERCADO PAGO
# ═══════════════════════════════════════════════════════════

@router.post("/mercadopago")
async def configure_mercadopago(
    store_id: int,
    config: MercadoPagoConfig,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep
):
    """
    Configura credenciais do Mercado Pago para a loja
    
    - Valida token fazendo chamada de teste
    - Salva credenciais criptografadas
    - Registra auditoria da mudança
    """
    
    # Verifica permissão
    if store.id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão para configurar esta loja"
        )
    
    # Configura usando service
    service = PaymentMultiTenantService(db, store_id)
    
    try:
        result = service.configure_mercadopago(
            access_token=config.access_token,
            public_key=config.public_key,
            webhook_secret=config.webhook_secret,
            sandbox_mode=config.sandbox_mode
        )
        
        if not result["success"]:
            # Log falha
            audit.log_failed_action(
                action=AuditAction.UPDATE_SETTINGS,
                entity_type=AuditEntityType.STORE,
                entity_id=store_id,
                error=result.get("error", "Erro ao configurar Mercado Pago")
            )
            db.commit()
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Erro ao configurar")
            )
        
        # Log sucesso
        audit.log(
            action=AuditAction.UPDATE_SETTINGS,
            entity_type=AuditEntityType.STORE,
            entity_id=store_id,
            changes={
                "payment_gateway": "mercadopago",
                "sandbox": config.sandbox_mode,
                "account": result["account_info"]
            },
            description=f"Mercado Pago configurado para {store.name}"
        )
        db.commit()
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/mercadopago")
async def remove_mercadopago(
    store_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep
):
    """
    Remove configuração do Mercado Pago
    """
    
    if store.id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão"
        )
    
    # Remove credenciais
    store.mercadopago_enabled = False
    store.mercadopago_access_token = None
    store.mercadopago_public_key = None
    store.mercadopago_webhook_secret = None
    
    # Log
    audit.log(
        action=AuditAction.DELETE_SETTINGS,
        entity_type=AuditEntityType.STORE,
        entity_id=store_id,
        changes={
            "payment_gateway": "mercadopago",
            "action": "removed"
        },
        description=f"Mercado Pago removido de {store.name}"
    )
    
    db.commit()
    
    return {"success": True, "message": "Mercado Pago removido"}


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO PIX DIRETO
# ═══════════════════════════════════════════════════════════

@router.post("/pix-direct")
async def configure_pix_direct(
    store_id: int,
    config: PIXDirectConfig,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep
):
    """
    Configura PIX direto (sem intermediário)
    
    - Valida formato da chave PIX
    - Gera QR code de teste
    """
    
    if store.id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sem permissão"
        )
    
    service = PaymentMultiTenantService(db, store_id)
    
    try:
        result = service.configure_pix_direct(
            pix_key=config.pix_key,
            pix_key_type=config.pix_key_type,
            merchant_name=config.merchant_name,
            merchant_city=config.merchant_city
        )
        
        # Log
        audit.log(
            action=AuditAction.UPDATE_SETTINGS,
            entity_type=AuditEntityType.STORE,
            entity_id=store_id,
            changes={
                "payment_method": "pix_direct",
                "pix_type": config.pix_key_type,
                "merchant": config.merchant_name
            },
            description=f"PIX configurado para {store.name}"
        )
        db.commit()
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ═══════════════════════════════════════════════════════════
# HABILITAR/DESABILITAR MÉTODOS
# ═══════════════════════════════════════════════════════════

@router.patch("/cash")
async def toggle_cash_payment(
    store_id: int,
    config: PaymentMethodToggle,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    """Habilita/desabilita pagamento em dinheiro"""
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    store.cash_enabled = config.enabled
    db.commit()
    
    return {
        "success": True,
        "cash_enabled": config.enabled
    }


@router.patch("/card-machine")
async def toggle_card_machine(
    store_id: int,
    config: PaymentMethodToggle,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    """Habilita/desabilita maquininha física"""
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    store.card_machine_enabled = config.enabled
    db.commit()
    
    return {
        "success": True,
        "card_machine_enabled": config.enabled
    }


@router.patch("/voucher")
async def toggle_voucher(
    store_id: int,
    config: PaymentMethodToggle,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    """Habilita/desabilita vale refeição"""
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    store.voucher_enabled = config.enabled
    db.commit()
    
    return {
        "success": True,
        "voucher_enabled": config.enabled
    }


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE TAXAS
# ═══════════════════════════════════════════════════════════

@router.patch("/fees")
async def configure_fees(
    store_id: int,
    config: ServiceFeeConfig,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep,
    audit: GetAuditLoggerDep
):
    """
    Configura taxas de serviço e plataforma
    """
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    # Salva valores antigos
    old_values = {
        "service_fee": float(store.service_fee_percentage),
        "platform_fee": float(store.platform_fee_percentage),
        "minimum_order": store.minimum_order_value
    }
    
    # Atualiza
    store.service_fee_percentage = config.service_fee_percentage
    store.platform_fee_percentage = config.platform_fee_percentage
    store.minimum_order_value = config.minimum_order_value
    
    # Log
    audit.log(
        action=AuditAction.UPDATE_SETTINGS,
        entity_type=AuditEntityType.STORE,
        entity_id=store_id,
        changes={
            "old_values": old_values,
            "new_values": {
                "service_fee": config.service_fee_percentage,
                "platform_fee": config.platform_fee_percentage,
                "minimum_order": config.minimum_order_value
            }
        },
        description=f"Taxas atualizadas para {store.name}"
    )
    
    db.commit()
    
    return {
        "success": True,
        "service_fee_percentage": config.service_fee_percentage,
        "platform_fee_percentage": config.platform_fee_percentage,
        "minimum_order_value": config.minimum_order_value
    }


# ═══════════════════════════════════════════════════════════
# LISTAR CONFIGURAÇÕES
# ═══════════════════════════════════════════════════════════

@router.get("/")
async def get_payment_config(
    store_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    """
    Retorna configuração atual de pagamentos
    """
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    service = PaymentMultiTenantService(db, store_id)
    
    return {
        "mercadopago": {
            "enabled": store.mercadopago_enabled,
            "sandbox": store.mercadopago_sandbox_mode,
            "public_key": store.mercadopago_public_key,
            "has_webhook_secret": bool(store.mercadopago_webhook_secret),
            "account": None  # TODO: Buscar dados da conta se configurado
        },
        "pix_direct": {
            "enabled": store.pix_enabled,
            "key_type": store.pix_key_type,
            "merchant_name": store.pix_merchant_name,
            "merchant_city": store.pix_merchant_city,
            "masked_key": service._mask_pix_key(store.pix_key) if store.pix_key else None
        },
        "other_methods": {
            "cash_enabled": store.cash_enabled,
            "card_machine_enabled": store.card_machine_enabled,
            "voucher_enabled": store.voucher_enabled
        },
        "fees": {
            "service_fee_percentage": float(store.service_fee_percentage),
            "platform_fee_percentage": float(store.platform_fee_percentage),
            "minimum_order_value": store.minimum_order_value
        },
        "available_methods": service.get_available_payment_methods()
    }


@router.get("/test-credentials")
async def test_payment_credentials(
    store_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    user: GetCurrentUserDep
):
    """
    Testa se as credenciais estão funcionando
    """
    
    if store.id != store_id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    
    service = PaymentMultiTenantService(db, store_id)
    results = {}
    
    # Testa Mercado Pago
    if store.mercadopago_enabled and service.sdk:
        try:
            response = service.sdk.user.get()
            results["mercadopago"] = {
                "status": "ok" if response["status"] == 200 else "error",
                "message": "Credenciais válidas" if response["status"] == 200 else "Erro na autenticação"
            }
        except Exception as e:
            results["mercadopago"] = {
                "status": "error",
                "message": str(e)
            }
    
    # Testa PIX
    if store.pix_enabled:
        results["pix_direct"] = {
            "status": "ok" if store.pix_key else "error",
            "message": "PIX configurado" if store.pix_key else "Chave PIX não configurada"
        }
    
    return results
