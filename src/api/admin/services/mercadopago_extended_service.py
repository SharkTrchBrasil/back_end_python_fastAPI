"""
Serviço Estendido de Integração com Mercado Pago
================================================
Funcionalidades completas para produção
"""

import logging
import hmac
import hashlib
import uuid
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core import models
from src.core.config import config
from src.core.utils.enums import PaymentStatus, OrderStatus

logger = logging.getLogger(__name__)


class MercadoPagoExtendedService:
    """Serviço completo para integração com Mercado Pago em produção"""

    def __init__(self, db: Session):
        self.db = db
        self.app_id = config.MERCADOPAGO_APP_ID
        self.access_token = config.MERCADOPAGO_ACCESS_TOKEN
        self.public_key = config.MERCADOPAGO_PUBLIC_KEY
        self.base_url = config.MERCADOPAGO_API_URL
        self.environment = config.MERCADOPAGO_ENVIRONMENT
        self.webhook_secret = config.MERCADOPAGO_WEBHOOK_SECRET
        self.notification_url = config.MERCADOPAGO_NOTIFICATION_URL
        
        self.is_sandbox = self.environment.lower() in ["sandbox", "test", "testing"]
        
        # Session configurada com retry
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        # Headers padrão
        self.session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        logger.info(f"✅ MercadoPago Extended Service inicializado - Sandbox: {self.is_sandbox}")
    
    # ═══════════════════════════════════════════════════════════
    # CRIAÇÃO DE PAGAMENTO COMPLETO
    # ═══════════════════════════════════════════════════════════
    
    def create_command_payment(
        self,
        command_id: int,
        payment_method_type: str = "pix"
    ) -> Dict:
        """
        Cria um pagamento completo para uma comanda
        
        Args:
            command_id: ID da comanda
            payment_method_type: Tipo de pagamento (pix, credit, debit, boleto)
        
        Returns:
            Dados do pagamento com links e QR codes
        """
        
        # Busca a comanda com todos os pedidos
        command = self.db.query(models.Command).filter(
            models.Command.id == command_id
        ).first()
        
        if not command:
            raise ValueError("Comanda não encontrada")
        
        # Calcula o valor total
        total_amount = Decimal('0.00')
        description_items = []
        
        for order in command.orders:
            total_amount += Decimal(str(order.total_price / 100))  # Converte de centavos
            
            # Adiciona itens na descrição
            for product in order.products:
                description_items.append(f"{product.quantity}x {product.name}")
        
        # Aplica descontos e taxas
        if command.discount_amount:
            total_amount -= Decimal(str(command.discount_amount / 100))
        
        if command.service_charge:
            total_amount += Decimal(str(command.service_charge / 100))
        
        # Dados do cliente
        customer_name = command.customer_name or "Cliente"
        customer_email = command.customer_contact or f"mesa_{command.table_id}@restaurant.com"
        
        # Descrição do pagamento
        description = f"Mesa {command.table_id} - {', '.join(description_items[:3])}"
        if len(description_items) > 3:
            description += f" e mais {len(description_items) - 3} items"
        
        # Metadata para rastreamento
        metadata = {
            "command_id": command_id,
            "table_id": command.table_id,
            "store_id": command.store_id,
            "customer_name": customer_name,
            "items_count": len(description_items)
        }
        
        # Cria o pagamento baseado no tipo
        if payment_method_type == "pix":
            payment_data = self._create_pix_payment(
                amount=float(total_amount),
                description=description,
                customer_email=customer_email,
                customer_name=customer_name,
                metadata=metadata
            )
        elif payment_method_type == "credit":
            payment_data = self._create_credit_payment(
                amount=float(total_amount),
                description=description,
                customer_email=customer_email,
                customer_name=customer_name,
                metadata=metadata
            )
        elif payment_method_type == "boleto":
            payment_data = self._create_boleto_payment(
                amount=float(total_amount),
                description=description,
                customer_email=customer_email,
                customer_name=customer_name,
                metadata=metadata
            )
        else:
            raise ValueError(f"Método de pagamento não suportado: {payment_method_type}")
        
        # Salva referência do pagamento no banco
        self._save_payment_reference(command_id, payment_data)
        
        # Formata resposta para o frontend
        return self._format_payment_response(payment_data, payment_method_type)
    
    def _create_pix_payment(
        self,
        amount: float,
        description: str,
        customer_email: str,
        customer_name: str,
        metadata: Dict
    ) -> Dict:
        """Cria um pagamento PIX"""
        
        payload = {
            "transaction_amount": amount,
            "description": description[:200],  # Limite de caracteres
            "payment_method_id": "pix",
            "notification_url": self.notification_url,
            "payer": {
                "email": customer_email,
                "first_name": customer_name.split()[0] if customer_name else "Cliente",
                "last_name": customer_name.split()[-1] if len(customer_name.split()) > 1 else "Mesa",
                "identification": {
                    "type": "CPF",
                    "number": "00000000000"  # CPF teste para sandbox
                } if self.is_sandbox else {}
            },
            "metadata": metadata,
            "date_of_expiration": (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"
        }
        
        response = self._make_request("POST", "/v1/payments", payload)
        
        logger.info(f"✅ PIX Payment criado: {response.get('id')}")
        logger.info(f"   QR Code: {response.get('point_of_interaction', {}).get('transaction_data', {}).get('qr_code')[:50]}...")
        
        return response
    
    def _create_credit_payment(
        self,
        amount: float,
        description: str,
        customer_email: str,
        customer_name: str,
        metadata: Dict
    ) -> Dict:
        """Cria um link de pagamento para cartão de crédito"""
        
        # Para cartão, criamos um payment link
        payload = {
            "auto_return": "approved",
            "back_urls": {
                "success": f"{config.FRONTEND_URL}/payment/success",
                "failure": f"{config.FRONTEND_URL}/payment/failure",
                "pending": f"{config.FRONTEND_URL}/payment/pending"
            },
            "expires": True,
            "expiration_date_from": datetime.utcnow().isoformat() + "Z",
            "expiration_date_to": (datetime.utcnow() + timedelta(hours=2)).isoformat() + "Z",
            "items": [{
                "title": description[:100],
                "quantity": 1,
                "unit_price": amount,
                "currency_id": "BRL"
            }],
            "marketplace": "NONE",
            "metadata": metadata,
            "notification_url": self.notification_url,
            "payment_methods": {
                "excluded_payment_types": [
                    {"id": "ticket"},  # Remove boleto
                    {"id": "bank_transfer"},  # Remove transferência
                    {"id": "atm"}  # Remove saque
                ],
                "installments": 12,  # Até 12x
                "default_installments": 1
            },
            "payer": {
                "email": customer_email,
                "name": customer_name
            },
            "statement_descriptor": "RESTAURANTE"  # Nome na fatura
        }
        
        response = self._make_request("POST", "/checkout/preferences", payload)
        
        logger.info(f"✅ Payment Link criado: {response.get('id')}")
        logger.info(f"   Init Point: {response.get('init_point')}")
        
        return response
    
    def _create_boleto_payment(
        self,
        amount: float,
        description: str,
        customer_email: str,
        customer_name: str,
        metadata: Dict
    ) -> Dict:
        """Cria um pagamento por boleto"""
        
        payload = {
            "transaction_amount": amount,
            "description": description[:200],
            "payment_method_id": "bolbradesco",  # Boleto Bradesco
            "notification_url": self.notification_url,
            "payer": {
                "email": customer_email,
                "first_name": customer_name.split()[0] if customer_name else "Cliente",
                "last_name": customer_name.split()[-1] if len(customer_name.split()) > 1 else "Mesa",
                "identification": {
                    "type": "CPF",
                    "number": "00000000000"  # CPF teste
                } if self.is_sandbox else {},
                "address": {
                    "zip_code": "06233200",
                    "street_name": "Av. das Nações Unidas",
                    "street_number": "3003",
                    "neighborhood": "Bonfim",
                    "city": "Osasco",
                    "federal_unit": "SP"
                } if not self.is_sandbox else {}
            },
            "metadata": metadata,
            "date_of_expiration": (datetime.utcnow() + timedelta(days=3)).isoformat() + "Z"
        }
        
        response = self._make_request("POST", "/v1/payments", payload)
        
        logger.info(f"✅ Boleto criado: {response.get('id')}")
        logger.info(f"   Barcode: {response.get('barcode', {}).get('content')}")
        
        return response
    
    def _save_payment_reference(self, command_id: int, payment_data: Dict):
        """Salva referência do pagamento no banco"""
        
        # Cria registro de transação pendente
        transaction = models.MercadoPagoTransaction(
            command_id=command_id,
            payment_id=payment_data.get('id'),
            status=payment_data.get('status', 'pending'),
            payment_method_id=payment_data.get('payment_method_id'),
            transaction_amount=payment_data.get('transaction_amount'),
            metadata=payment_data.get('metadata', {}),
            created_at=datetime.utcnow()
        )
        
        self.db.add(transaction)
        self.db.commit()
        
        logger.info(f"💾 Payment reference saved: {transaction.id}")
    
    def _format_payment_response(self, payment_data: Dict, payment_method_type: str) -> Dict:
        """Formata a resposta do pagamento para o frontend"""
        
        response = {
            "payment_id": payment_data.get('id'),
            "status": payment_data.get('status'),
            "payment_method": payment_method_type,
            "amount": payment_data.get('transaction_amount'),
            "created_at": payment_data.get('date_created'),
            "expires_at": payment_data.get('date_of_expiration')
        }
        
        # Adiciona dados específicos por tipo
        if payment_method_type == "pix":
            poi = payment_data.get('point_of_interaction', {})
            transaction_data = poi.get('transaction_data', {})
            
            response.update({
                "qr_code": transaction_data.get('qr_code'),
                "qr_code_base64": transaction_data.get('qr_code_base64'),
                "pix_key": transaction_data.get('bank_info', {}).get('pix', {}).get('pix_key')
            })
        
        elif payment_method_type == "credit":
            response.update({
                "payment_url": payment_data.get('init_point'),
                "sandbox_url": payment_data.get('sandbox_init_point')
            })
        
        elif payment_method_type == "boleto":
            response.update({
                "barcode": payment_data.get('barcode', {}).get('content'),
                "boleto_url": payment_data.get('transaction_details', {}).get('external_resource_url')
            })
        
        return response
    
    # ═══════════════════════════════════════════════════════════
    # WEBHOOK HANDLER COMPLETO
    # ═══════════════════════════════════════════════════════════
    
    def process_webhook(self, webhook_data: Dict, signature: str = None) -> bool:
        """
        Processa webhook do Mercado Pago
        
        Args:
            webhook_data: Dados recebidos do webhook
            signature: Assinatura para validação
        
        Returns:
            True se processado com sucesso
        """
        
        # Valida assinatura se fornecida
        if signature and not self._verify_signature(webhook_data, signature):
            logger.error("❌ Assinatura do webhook inválida")
            return False
        
        # Identifica tipo de notificação
        notification_type = webhook_data.get('type', webhook_data.get('topic'))
        notification_id = webhook_data.get('id')
        
        logger.info(f"📨 Webhook recebido: {notification_type} - {notification_id}")
        
        if notification_type in ['payment', 'merchant_order']:
            return self._process_payment_notification(webhook_data)
        
        logger.warning(f"⚠️ Tipo de notificação não tratada: {notification_type}")
        return True
    
    def _process_payment_notification(self, webhook_data: Dict) -> bool:
        """Processa notificação de pagamento"""
        
        # Busca dados completos do pagamento
        payment_id = webhook_data.get('data', {}).get('id')
        if not payment_id:
            logger.error("❌ Payment ID não encontrado no webhook")
            return False
        
        # Busca detalhes do pagamento
        payment_details = self.get_payment_details(payment_id)
        
        # Atualiza status no banco
        transaction = self.db.query(models.MercadoPagoTransaction).filter(
            models.MercadoPagoTransaction.payment_id == payment_id
        ).first()
        
        if not transaction:
            logger.warning(f"⚠️ Transação não encontrada para payment_id: {payment_id}")
            return False
        
        # Atualiza status
        old_status = transaction.status
        new_status = payment_details.get('status')
        transaction.status = new_status
        transaction.updated_at = datetime.utcnow()
        
        # Processa mudanças de status
        if new_status == 'approved' and old_status != 'approved':
            self._process_approved_payment(transaction, payment_details)
        elif new_status == 'rejected':
            self._process_rejected_payment(transaction, payment_details)
        elif new_status == 'refunded':
            self._process_refunded_payment(transaction, payment_details)
        
        self.db.commit()
        
        logger.info(f"✅ Payment notification processada: {payment_id} - {old_status} -> {new_status}")
        return True
    
    def _process_approved_payment(self, transaction: models.MercadoPagoTransaction, payment_details: Dict):
        """Processa pagamento aprovado"""
        
        # Atualiza comanda
        command = self.db.query(models.Command).filter(
            models.Command.id == transaction.command_id
        ).first()
        
        if command:
            # Atualiza pedidos da comanda
            for order in command.orders:
                order.payment_status = PaymentStatus.PAID
                order.order_status = OrderStatus.FINALIZED
                order.paid_at = datetime.utcnow()
            
            # Fecha a comanda
            command.status = models.CommandStatus.CLOSED
            
            # Libera a mesa
            if command.table_id:
                table = self.db.query(models.Tables).filter(
                    models.Tables.id == command.table_id
                ).first()
                
                if table:
                    table.status = models.TableStatus.AVAILABLE
                    table.status_color = "#28a745"  # Verde
                    table.current_capacity = 0
                    
                    # Atualiza estatísticas
                    table.total_revenue_today += int(payment_details.get('transaction_amount', 0) * 100)
            
            logger.info(f"✅ Comanda {command.id} marcada como paga")
            
            # Emite evento via WebSocket
            self._emit_payment_approved_event(command, payment_details)
    
    def _process_rejected_payment(self, transaction: models.MercadoPagoTransaction, payment_details: Dict):
        """Processa pagamento rejeitado"""
        
        command_id = transaction.command_id
        logger.warning(f"⚠️ Pagamento rejeitado para comanda {command_id}")
        
        # Emite evento de falha
        self._emit_payment_rejected_event(command_id, payment_details)
    
    def _process_refunded_payment(self, transaction: models.MercadoPagoTransaction, payment_details: Dict):
        """Processa reembolso"""
        
        command = self.db.query(models.Command).filter(
            models.Command.id == transaction.command_id
        ).first()
        
        if command:
            for order in command.orders:
                order.payment_status = PaymentStatus.REFUNDED
            
            logger.info(f"↩️ Reembolso processado para comanda {command.id}")
    
    def _emit_payment_approved_event(self, command: models.Command, payment_details: Dict):
        """Emite evento de pagamento aprovado via WebSocket"""
        
        # Este método seria integrado com Socket.io
        # Por enquanto, apenas loga
        logger.info(f"📡 Emitindo evento: payment_approved - Command {command.id}")
    
    def _emit_payment_rejected_event(self, command_id: int, payment_details: Dict):
        """Emite evento de pagamento rejeitado via WebSocket"""
        
        logger.info(f"📡 Emitindo evento: payment_rejected - Command {command_id}")
    
    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ═══════════════════════════════════════════════════════════
    
    def get_payment_details(self, payment_id: str) -> Dict:
        """Busca detalhes completos de um pagamento"""
        
        return self._make_request("GET", f"/v1/payments/{payment_id}")
    
    def cancel_payment(self, payment_id: str) -> Dict:
        """Cancela um pagamento pendente"""
        
        return self._make_request(
            "PUT",
            f"/v1/payments/{payment_id}",
            {"status": "cancelled"}
        )
    
    def refund_payment(self, payment_id: str, amount: float = None) -> Dict:
        """Processa reembolso total ou parcial"""
        
        payload = {}
        if amount:
            payload["amount"] = amount
        
        return self._make_request(
            "POST",
            f"/v1/payments/{payment_id}/refunds",
            payload if payload else None
        )
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Faz requisição para API do Mercado Pago"""
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro na requisição para Mercado Pago: {e}")
            raise
    
    def _verify_signature(self, data: Dict, signature: str) -> bool:
        """Verifica assinatura do webhook"""
        
        # Implementação da verificação HMAC-SHA256
        data_id = data.get('id', '')
        request_id = data.get('request_id', '')
        
        message = f"id={data_id}&request-id={request_id}"
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)


# Modelo para armazenar transações
class MercadoPagoTransaction(models.Base, models.TimestampMixin):
    """Modelo para armazenar transações do Mercado Pago"""
    __tablename__ = "mercadopago_transactions"
    
    id: models.Mapped[int] = models.mapped_column(primary_key=True)
    command_id: models.Mapped[int] = models.mapped_column(models.ForeignKey("commands.id"))
    payment_id: models.Mapped[str] = models.mapped_column(models.String(100), unique=True)
    status: models.Mapped[str] = models.mapped_column(models.String(50))
    payment_method_id: models.Mapped[str] = models.mapped_column(models.String(50))
    transaction_amount: models.Mapped[float] = models.mapped_column()
    metadata: models.Mapped[dict] = models.mapped_column(models.JSON, nullable=True)
    webhook_data: models.Mapped[dict] = models.mapped_column(models.JSON, nullable=True)
    
    command: models.Mapped["models.Command"] = models.relationship()
