"""
Payment Multi-tenant Service - Pagamentos por Loja
===================================================
Cada loja usa suas próprias credenciais de pagamento
"""

import mercadopago
import qrcode
import io
import base64
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from decimal import Decimal
import json
import hashlib
import hmac

from src.core import models
from src.core.config import config
from src.core.utils.enums import PaymentStatus, PaymentMethodType
from src.api.admin.socketio.socketio_manager import event_emitter


class PaymentMultiTenantService:
    """
    Serviço de pagamentos multi-tenant
    Cada loja tem suas próprias credenciais e configurações
    """
    
    def __init__(self, db: Session, store_id: int):
        self.db = db
        self.store_id = store_id
        self.store = self._load_store()
        self.sdk = self._initialize_sdk()
    
    def _load_store(self) -> models.Store:
        """Carrega dados e credenciais da loja"""
        
        store = self.db.query(models.Store).filter(
            models.Store.id == self.store_id,
            models.Store.is_active == True
        ).first()
        
        if not store:
            raise ValueError(f"Loja {self.store_id} não encontrada ou inativa")
        
        return store
    
    def _initialize_sdk(self) -> Optional[mercadopago.SDK]:
        """
        Inicializa SDK do Mercado Pago com credenciais da loja
        Retorna None se loja não tem Mercado Pago configurado
        """
        
        if not self.store.mercadopago_enabled:
            return None
        
        if not self.store.mercadopago_access_token:
            return None
        
        # Inicializa SDK com token DA LOJA
        sdk = mercadopago.SDK(self.store.mercadopago_access_token)
        
        # Define se é sandbox ou produção
        if self.store.mercadopago_sandbox_mode:
            # Modo sandbox para testes
            sdk.request_options.custom_headers = {
                'x-sandbox-mode': 'true'
            }
        
        return sdk
    
    # ═══════════════════════════════════════════════════════════
    # CONFIGURAÇÃO DE CREDENCIAIS
    # ═══════════════════════════════════════════════════════════
    
    def configure_mercadopago(
        self,
        access_token: str,
        public_key: str,
        webhook_secret: Optional[str] = None,
        sandbox_mode: bool = True
    ) -> Dict[str, Any]:
        """
        Configura ou atualiza credenciais do Mercado Pago para a loja
        
        Args:
            access_token: Token de acesso da loja no MP
            public_key: Chave pública para checkout
            webhook_secret: Secret para validar webhooks
            sandbox_mode: Se está em modo teste
            
        Returns:
            Status da configuração
        """
        
        # Valida token fazendo uma chamada de teste
        test_sdk = mercadopago.SDK(access_token)
        
        try:
            # Tenta buscar informações da conta
            response = test_sdk.user.get()
            
            if response["status"] != 200:
                raise ValueError("Token inválido ou sem permissões")
            
            user_info = response["response"]
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Erro ao validar token: {str(e)}"
            }
        
        # Salva credenciais antigas para auditoria
        old_token = self.store.mercadopago_access_token
        
        # Atualiza credenciais
        self.store.mercadopago_access_token = access_token
        self.store.mercadopago_public_key = public_key
        self.store.mercadopago_webhook_secret = webhook_secret
        self.store.mercadopago_sandbox_mode = sandbox_mode
        self.store.mercadopago_enabled = True
        
        # Log de auditoria
        log_entry = models.PaymentCredentialsLog(
            store_id=self.store_id,
            change_type="updated" if old_token else "created",
            credential_type="mercadopago",
            old_value=self._mask_token(old_token) if old_token else None,
            new_value=self._mask_token(access_token),
            notes=f"Conta MP: {user_info.get('email', 'N/A')}"
        )
        self.db.add(log_entry)
        
        self.db.commit()
        
        # Reinicializa SDK com novas credenciais
        self.sdk = self._initialize_sdk()
        
        return {
            "success": True,
            "message": "Mercado Pago configurado com sucesso",
            "account_info": {
                "id": user_info.get("id"),
                "email": user_info.get("email"),
                "site_id": user_info.get("site_id"),  # País (MLB = Brasil)
                "sandbox": sandbox_mode
            }
        }
    
    def configure_pix_direct(
        self,
        pix_key: str,
        pix_key_type: str,
        merchant_name: Optional[str] = None,
        merchant_city: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Configura PIX direto (sem intermediário) para a loja
        
        Args:
            pix_key: Chave PIX (CPF, CNPJ, email, telefone ou aleatória)
            pix_key_type: Tipo da chave (cpf, cnpj, email, phone, random)
            merchant_name: Nome do recebedor
            merchant_city: Cidade do recebedor
            
        Returns:
            Status da configuração
        """
        
        # Valida tipo de chave
        valid_types = ["cpf", "cnpj", "email", "phone", "random"]
        if pix_key_type not in valid_types:
            raise ValueError(f"Tipo de chave inválido. Use: {valid_types}")
        
        # Valida formato da chave baseado no tipo
        if pix_key_type == "cpf":
            if len(pix_key.replace(".", "").replace("-", "")) != 11:
                raise ValueError("CPF inválido")
        elif pix_key_type == "cnpj":
            if len(pix_key.replace(".", "").replace("-", "").replace("/", "")) != 14:
                raise ValueError("CNPJ inválido")
        elif pix_key_type == "email":
            if "@" not in pix_key:
                raise ValueError("Email inválido")
        elif pix_key_type == "phone":
            if not pix_key.startswith("+"):
                pix_key = "+55" + pix_key.replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
        
        # Atualiza configurações
        self.store.pix_enabled = True
        self.store.pix_key = pix_key
        self.store.pix_key_type = pix_key_type
        self.store.pix_merchant_name = merchant_name or self.store.name
        self.store.pix_merchant_city = merchant_city or self.store.city
        
        # Log de auditoria
        log_entry = models.PaymentCredentialsLog(
            store_id=self.store_id,
            change_type="updated",
            credential_type="pix",
            new_value=f"{pix_key_type}: {self._mask_pix_key(pix_key)}",
            notes=f"PIX configurado para {merchant_name}"
        )
        self.db.add(log_entry)
        
        self.db.commit()
        
        return {
            "success": True,
            "message": "PIX configurado com sucesso",
            "pix_info": {
                "key": self._mask_pix_key(pix_key),
                "type": pix_key_type,
                "merchant": merchant_name or self.store.name
            }
        }
    
    # ═══════════════════════════════════════════════════════════
    # CRIAÇÃO DE PAGAMENTOS
    # ═══════════════════════════════════════════════════════════
    
    def create_payment(
        self,
        order_id: int,
        payment_method: str,
        installments: int = 1,
        customer_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Cria pagamento usando as credenciais da loja
        
        Args:
            order_id: ID do pedido
            payment_method: Método (pix, credit, debit, cash)
            installments: Parcelas (para cartão)
            customer_info: Dados do cliente
            
        Returns:
            Dados do pagamento criado
        """
        
        # Busca pedido
        order = self.db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.store_id == self.store_id
        ).first()
        
        if not order:
            raise ValueError("Pedido não encontrado")
        
        # Verifica método de pagamento disponível
        payment_methods = self.get_available_payment_methods()
        
        if payment_method not in [m["code"] for m in payment_methods]:
            raise ValueError(f"Método {payment_method} não disponível para esta loja")
        
        # Processa baseado no método
        if payment_method == "pix":
            if self.store.mercadopago_enabled and self.sdk:
                # PIX via Mercado Pago
                return self._create_mercadopago_pix(order, customer_info)
            elif self.store.pix_enabled:
                # PIX direto
                return self._create_direct_pix(order)
            else:
                raise ValueError("PIX não configurado para esta loja")
        
        elif payment_method in ["credit", "debit"]:
            if not self.sdk:
                raise ValueError("Cartão não configurado (Mercado Pago necessário)")
            return self._create_mercadopago_card(order, payment_method, installments, customer_info)
        
        elif payment_method == "cash":
            return self._create_cash_payment(order)
        
        else:
            raise ValueError(f"Método {payment_method} não implementado")
    
    def _create_mercadopago_pix(
        self,
        order: models.Order,
        customer_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Cria pagamento PIX via Mercado Pago"""
        
        payment_data = {
            "transaction_amount": float(order.total_price / 100),
            "description": f"Pedido #{order.order_number}",
            "payment_method_id": "pix",
            "installments": 1,
            "payer": {
                "email": customer_info.get("email", "cliente@example.com") if customer_info else "cliente@example.com",
                "first_name": customer_info.get("name", "Cliente") if customer_info else "Cliente",
                "identification": {
                    "type": "CPF",
                    "number": customer_info.get("cpf", "00000000000") if customer_info else "00000000000"
                }
            },
            "external_reference": f"order_{order.id}",
            "notification_url": f"{config.API_BASE_URL}/webhook/mercadopago/{self.store_id}",
            "metadata": {
                "store_id": self.store_id,
                "order_id": order.id,
                "table_id": order.command.table_id if order.command else None
            }
        }
        
        # Cria pagamento
        payment_response = self.sdk.payment.create(payment_data)
        
        if payment_response["status"] != 201:
            raise ValueError(f"Erro ao criar pagamento: {payment_response}")
        
        payment = payment_response["response"]
        
        # Salva transação
        transaction = models.MercadoPagoTransaction(
            store_id=self.store_id,
            payment_id=str(payment["id"]),
            order_id=order.id,
            amount=int(payment["transaction_amount"] * 100),
            payment_method="pix",
            status=payment["status"],
            qr_code=payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code"),
            qr_code_base64=payment.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code_base64"),
            external_reference=payment.get("external_reference"),
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(transaction)
        self.db.commit()
        
        return {
            "payment_id": payment["id"],
            "status": payment["status"],
            "qr_code": payment["point_of_interaction"]["transaction_data"]["qr_code"],
            "qr_code_base64": payment["point_of_interaction"]["transaction_data"]["qr_code_base64"],
            "expires_at": payment.get("date_of_expiration"),
            "total": payment["transaction_amount"]
        }
    
    def _create_direct_pix(self, order: models.Order) -> Dict[str, Any]:
        """Cria PIX direto (sem intermediário)"""
        
        # Gera código PIX Copia e Cola
        pix_payload = self._generate_pix_payload(
            pix_key=self.store.pix_key,
            merchant_name=self.store.pix_merchant_name,
            merchant_city=self.store.pix_merchant_city,
            amount=float(order.total_price / 100),
            tx_id=f"ORDER{order.id}"
        )
        
        # Gera QR Code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(pix_payload)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Salva referência do pagamento
        order.payment_method = "pix_direct"
        order.payment_reference = pix_payload[:50]  # Primeiros 50 chars como referência
        self.db.commit()
        
        return {
            "payment_method": "pix_direct",
            "status": "pending",
            "qr_code": pix_payload,
            "qr_code_base64": f"data:image/png;base64,{qr_base64}",
            "pix_key": self._mask_pix_key(self.store.pix_key),
            "merchant": self.store.pix_merchant_name,
            "total": float(order.total_price / 100),
            "message": "Escaneie o QR Code ou copie o código PIX"
        }
    
    def _create_cash_payment(self, order: models.Order) -> Dict[str, Any]:
        """Registra pagamento em dinheiro"""
        
        order.payment_method = "cash"
        order.payment_status = PaymentStatus.PENDING
        self.db.commit()
        
        return {
            "payment_method": "cash",
            "status": "pending",
            "total": float(order.total_price / 100),
            "message": "Dirija-se ao caixa para efetuar o pagamento em dinheiro"
        }
    
    # ═══════════════════════════════════════════════════════════
    # WEBHOOK HANDLER MULTI-TENANT
    # ═══════════════════════════════════════════════════════════
    
    def process_webhook(
        self,
        webhook_data: Dict[str, Any],
        headers: Dict[str, str],
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Processa webhook de pagamento para a loja específica
        
        Args:
            webhook_data: Payload do webhook
            headers: Headers da requisição
            ip_address: IP de origem
            
        Returns:
            Status do processamento
        """
        
        # Registra webhook recebido
        webhook_log = models.PaymentGatewayWebhook(
            store_id=self.store_id,
            gateway="mercadopago",
            webhook_id=webhook_data.get("id"),
            webhook_type=webhook_data.get("type"),
            payload=webhook_data,
            headers=dict(headers),
            received_at=datetime.now(timezone.utc),
            ip_address=ip_address
        )
        self.db.add(webhook_log)
        
        # Valida assinatura se configurado
        if self.store.mercadopago_webhook_secret:
            signature = headers.get("X-Signature")
            if not self._validate_webhook_signature(webhook_data, signature):
                webhook_log.signature_valid = False
                webhook_log.processing_result = "Invalid signature"
                self.db.commit()
                return {"success": False, "error": "Invalid signature"}
        
        webhook_log.signature_valid = True
        
        # Processa baseado no tipo
        try:
            if webhook_data.get("type") == "payment":
                result = self._process_payment_webhook(webhook_data)
            else:
                result = {"success": True, "message": "Webhook type not processed"}
            
            webhook_log.processed = True
            webhook_log.processed_at = datetime.now(timezone.utc)
            webhook_log.processing_result = json.dumps(result)
            
            self.db.commit()
            return result
            
        except Exception as e:
            webhook_log.processing_result = str(e)
            self.db.commit()
            raise
    
    def _validate_webhook_signature(
        self,
        data: Dict[str, Any],
        signature: str
    ) -> bool:
        """Valida assinatura HMAC do webhook"""
        
        if not signature or not self.store.mercadopago_webhook_secret:
            return False
        
        # Formato: ts=timestamp,v1=hash
        parts = dict(part.split("=") for part in signature.split(","))
        timestamp = parts.get("ts", "")
        hash_v1 = parts.get("v1", "")
        
        # Constrói string para validar
        signed_payload = f"id:{data.get('id', '')};timestamp:{timestamp};"
        
        # Calcula HMAC
        expected_hash = hmac.new(
            self.store.mercadopago_webhook_secret.encode(),
            signed_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(hash_v1, expected_hash)
    
    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ═══════════════════════════════════════════════════════════
    
    def get_available_payment_methods(self) -> List[Dict[str, Any]]:
        """Retorna métodos de pagamento disponíveis para a loja"""
        
        methods = []
        
        # Verifica métodos configurados
        if self.store.mercadopago_enabled and self.sdk:
            methods.extend([
                {
                    "code": "pix",
                    "name": "PIX",
                    "icon": "📱",
                    "gateway": "mercadopago",
                    "enabled": True
                },
                {
                    "code": "credit",
                    "name": "Cartão de Crédito",
                    "icon": "💳",
                    "gateway": "mercadopago",
                    "enabled": True
                },
                {
                    "code": "debit",
                    "name": "Cartão de Débito",
                    "icon": "💳",
                    "gateway": "mercadopago",
                    "enabled": True
                }
            ])
        
        if self.store.pix_enabled and self.store.pix_key:
            methods.append({
                "code": "pix",
                "name": "PIX",
                "icon": "📱",
                "gateway": "direct",
                "enabled": True
            })
        
        if self.store.cash_enabled:
            methods.append({
                "code": "cash",
                "name": "Dinheiro",
                "icon": "💵",
                "gateway": "manual",
                "enabled": True
            })
        
        if self.store.card_machine_enabled:
            methods.append({
                "code": "card_machine",
                "name": "Maquininha",
                "icon": "🏧",
                "gateway": "manual",
                "enabled": True
            })
        
        # Remove duplicatas mantendo prioridade
        seen = set()
        unique_methods = []
        for method in methods:
            if method["code"] not in seen:
                seen.add(method["code"])
                unique_methods.append(method)
        
        return unique_methods
    
    def _mask_token(self, token: str) -> str:
        """Mascara token para logs"""
        if not token:
            return ""
        return f"{token[:10]}...{token[-4:]}"
    
    def _mask_pix_key(self, pix_key: str) -> str:
        """Mascara chave PIX para exibição"""
        if not pix_key:
            return ""
        if "@" in pix_key:  # Email
            parts = pix_key.split("@")
            return f"{parts[0][:3]}***@{parts[1]}"
        elif len(pix_key) == 11:  # CPF
            return f"{pix_key[:3]}.***.***-{pix_key[-2:]}"
        elif len(pix_key) == 14:  # CNPJ
            return f"{pix_key[:2]}.***.***/****-{pix_key[-2:]}"
        else:
            return f"{pix_key[:5]}...{pix_key[-5:]}"
    
    def _generate_pix_payload(
        self,
        pix_key: str,
        merchant_name: str,
        merchant_city: str,
        amount: float,
        tx_id: str
    ) -> str:
        """
        Gera payload PIX Copia e Cola (BRCode)
        Formato EMV padronizado pelo Banco Central
        """
        
        # IDs padronizados
        payload_format = "01"  # Formato
        merchant_account = "26"  # Conta do comerciante
        merchant_category = "52" + "0000"  # MCC genérico
        currency = "53" + "03" + "986"  # BRL
        country = "58" + "02" + "BR"  # Brasil
        merchant_name_field = "59" + str(len(merchant_name)).zfill(2) + merchant_name
        merchant_city_field = "60" + str(len(merchant_city)).zfill(2) + merchant_city
        
        # Valor
        amount_str = f"{amount:.2f}"
        amount_field = "54" + str(len(amount_str)).zfill(2) + amount_str
        
        # ID da transação
        tx_id_field = "05" + str(len(tx_id)).zfill(2) + tx_id
        
        # Monta chave PIX
        pix_key_field = "01" + str(len(pix_key)).zfill(2) + pix_key
        
        # GUI do arranjo (PIX do BCB)
        gui = "00" + "14" + "br.gov.bcb.pix"
        
        # Monta merchant account info
        merchant_info = gui + pix_key_field + tx_id_field
        merchant_account_field = merchant_account + str(len(merchant_info)).zfill(2) + merchant_info
        
        # Payload parcial
        partial = (
            "00" + "02" + payload_format +
            merchant_account_field +
            merchant_category +
            currency +
            amount_field +
            country +
            merchant_name_field +
            merchant_city_field +
            "62" + "04" + "****"  # Placeholder para CRC
        )
        
        # Calcula CRC16
        crc = self._calculate_crc16(partial)
        
        # Payload final
        return partial[:-4] + crc.upper()
    
    def _calculate_crc16(self, data: str) -> str:
        """Calcula CRC16 para PIX"""
        
        crc = 0xFFFF
        polynomial = 0x1021
        
        for byte in data.encode():
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ polynomial
                else:
                    crc = crc << 1
                crc &= 0xFFFF
        
        return format(crc, '04X')
