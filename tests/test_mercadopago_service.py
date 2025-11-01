"""
Testes do Serviço Mercado Pago
==============================
Testes unitários e de integração
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import hmac
import hashlib

from src.api.admin.services.mercadopago_extended_service import (
    MercadoPagoExtendedService,
    MercadoPagoTransaction
)
from src.core import models
from src.core.utils.enums import CommandStatus, PaymentStatus, OrderStatus


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock do banco de dados"""
    db = MagicMock()
    return db


@pytest.fixture
def mp_service(mock_db):
    """Cria instância do serviço Mercado Pago"""
    with patch('src.api.admin.services.mercadopago_extended_service.config') as mock_config:
        mock_config.MERCADOPAGO_ACCESS_TOKEN = "TEST-TOKEN"
        mock_config.MERCADOPAGO_PUBLIC_KEY = "TEST-PUBLIC-KEY"
        mock_config.MERCADOPAGO_APP_ID = "TEST-APP-ID"
        mock_config.MERCADOPAGO_API_URL = "https://api.mercadopago.com"
        mock_config.MERCADOPAGO_ENVIRONMENT = "sandbox"
        mock_config.MERCADOPAGO_WEBHOOK_SECRET = "webhook-secret"
        mock_config.MERCADOPAGO_NOTIFICATION_URL = "https://api.example.com/webhook"
        mock_config.FRONTEND_URL = "https://example.com"
        
        service = MercadoPagoExtendedService(mock_db)
        return service


@pytest.fixture
def sample_command():
    """Cria comanda de teste"""
    command = Mock(spec=models.Command)
    command.id = 1
    command.table_id = 10
    command.store_id = 100
    command.customer_name = "João Silva"
    command.customer_contact = "joao@example.com"
    command.status = CommandStatus.ACTIVE
    command.discount_amount = 500  # R$ 5,00 em centavos
    command.service_charge = 1000  # R$ 10,00 em centavos
    command.orders = []
    
    return command


@pytest.fixture
def sample_order():
    """Cria pedido de teste"""
    order = Mock(spec=models.Order)
    order.id = 1
    order.total_price = 10000  # R$ 100,00 em centavos
    order.payment_status = PaymentStatus.PENDING
    order.order_status = OrderStatus.RECEIVED
    order.products = []
    
    # Adiciona produtos
    product1 = Mock()
    product1.quantity = 2
    product1.name = "Pizza Margherita"
    product1.price = 4000  # R$ 40,00
    
    product2 = Mock()
    product2.quantity = 1
    product2.name = "Refrigerante"
    product2.price = 600  # R$ 6,00
    
    order.products = [product1, product2]
    
    return order


# ═══════════════════════════════════════════════════════════
# TESTES DE CRIAÇÃO DE PAGAMENTO
# ═══════════════════════════════════════════════════════════

class TestPaymentCreation:
    """Testes de criação de pagamento"""
    
    @patch('requests.Session.request')
    def test_create_pix_payment(self, mock_request, mp_service, sample_command, sample_order):
        """Testa criação de pagamento PIX"""
        # Setup
        sample_command.orders = [sample_order]
        mp_service.db.query.return_value.filter.return_value.first.return_value = sample_command
        
        # Mock resposta da API
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "12345",
            "status": "pending",
            "payment_method_id": "pix",
            "transaction_amount": 105.00,
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "PIX_CODE_HERE",
                    "qr_code_base64": "BASE64_IMAGE"
                }
            },
            "date_created": "2024-01-01T12:00:00Z",
            "date_of_expiration": "2024-01-01T12:30:00Z"
        }
        mock_request.return_value = mock_response
        
        # Executa
        result = mp_service.create_command_payment(
            command_id=1,
            payment_method_type="pix"
        )
        
        # Validações
        assert result["payment_id"] == "12345"
        assert result["status"] == "pending"
        assert result["payment_method"] == "pix"
        assert result["qr_code"] == "PIX_CODE_HERE"
        assert result["qr_code_base64"] == "BASE64_IMAGE"
        
        # Verifica se salvou no banco
        mp_service.db.add.assert_called_once()
        mp_service.db.commit.assert_called_once()
    
    @patch('requests.Session.request')
    def test_create_credit_payment_link(self, mock_request, mp_service, sample_command, sample_order):
        """Testa criação de link de pagamento para cartão"""
        # Setup
        sample_command.orders = [sample_order]
        mp_service.db.query.return_value.filter.return_value.first.return_value = sample_command
        
        # Mock resposta
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "preference-123",
            "init_point": "https://checkout.mercadopago.com/v1/checkout?pref_id=123",
            "sandbox_init_point": "https://sandbox.checkout.mercadopago.com/v1/checkout?pref_id=123"
        }
        mock_request.return_value = mock_response
        
        # Executa
        result = mp_service.create_command_payment(
            command_id=1,
            payment_method_type="credit"
        )
        
        # Validações
        assert result["payment_id"] == "preference-123"
        assert "checkout.mercadopago.com" in result["payment_url"]
        assert "sandbox" in result["sandbox_url"]
    
    def test_payment_calculation_with_discounts(self, mp_service, sample_command, sample_order):
        """Testa cálculo correto do valor com descontos e taxas"""
        # Setup: R$ 100 - R$ 5 (desconto) + R$ 10 (taxa) = R$ 105
        sample_command.orders = [sample_order]
        sample_command.discount_amount = 500  # R$ 5,00
        sample_command.service_charge = 1000  # R$ 10,00
        
        mp_service.db.query.return_value.filter.return_value.first.return_value = sample_command
        
        with patch.object(mp_service, '_create_pix_payment') as mock_create:
            mock_create.return_value = {"id": "test"}
            
            mp_service.create_command_payment(1, "pix")
            
            # Verifica se o valor calculado está correto
            call_args = mock_create.call_args[1]
            assert call_args["amount"] == 105.0  # R$ 105,00


# ═══════════════════════════════════════════════════════════
# TESTES DE WEBHOOK
# ═══════════════════════════════════════════════════════════

class TestWebhook:
    """Testes de processamento de webhook"""
    
    def test_verify_webhook_signature_valid(self, mp_service):
        """Testa verificação de assinatura válida do webhook"""
        data = {
            "id": "12345",
            "request_id": "req-67890"
        }
        
        # Gera assinatura correta
        message = f"id={data['id']}&request-id={data['request_id']}"
        correct_signature = hmac.new(
            b"webhook-secret",
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Verifica
        is_valid = mp_service._verify_signature(data, correct_signature)
        assert is_valid is True
    
    def test_verify_webhook_signature_invalid(self, mp_service):
        """Testa rejeição de assinatura inválida"""
        data = {
            "id": "12345",
            "request_id": "req-67890"
        }
        
        # Assinatura incorreta
        wrong_signature = "invalid-signature"
        
        is_valid = mp_service._verify_signature(data, wrong_signature)
        assert is_valid is False
    
    @patch('requests.Session.request')
    def test_process_payment_approved_webhook(self, mock_request, mp_service):
        """Testa processamento de webhook de pagamento aprovado"""
        # Mock da transação existente
        transaction = Mock(spec=MercadoPagoTransaction)
        transaction.command_id = 1
        transaction.status = "pending"
        
        mp_service.db.query.return_value.filter.return_value.first.return_value = transaction
        
        # Mock dos detalhes do pagamento
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "12345",
            "status": "approved",
            "transaction_amount": 105.00
        }
        mock_request.return_value = mock_response
        
        # Mock da comanda e mesa
        command = Mock()
        command.id = 1
        command.table_id = 10
        command.orders = []
        
        table = Mock()
        table.id = 10
        table.total_revenue_today = 0
        
        # Configura query chain
        mp_service.db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=transaction)))),
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=command)))),
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=table))))
        ]
        
        # Processa webhook
        webhook_data = {
            "type": "payment",
            "data": {"id": "12345"}
        }
        
        success = mp_service.process_webhook(webhook_data)
        
        # Validações
        assert success is True
        assert transaction.status == "approved"
        assert command.status == models.CommandStatus.CLOSED
        mp_service.db.commit.assert_called()
    
    def test_process_payment_rejected_webhook(self, mp_service):
        """Testa processamento de pagamento rejeitado"""
        # Mock da transação
        transaction = Mock()
        transaction.command_id = 1
        transaction.status = "pending"
        
        mp_service.db.query.return_value.filter.return_value.first.return_value = transaction
        
        # Mock dos detalhes do pagamento
        with patch.object(mp_service, 'get_payment_details') as mock_get:
            mock_get.return_value = {
                "id": "12345",
                "status": "rejected",
                "status_detail": "cc_rejected_insufficient_amount"
            }
            
            webhook_data = {
                "type": "payment",
                "data": {"id": "12345"}
            }
            
            success = mp_service.process_webhook(webhook_data)
            
            assert success is True
            assert transaction.status == "rejected"


# ═══════════════════════════════════════════════════════════
# TESTES DE CANCELAMENTO E REEMBOLSO
# ═══════════════════════════════════════════════════════════

class TestCancelAndRefund:
    """Testes de cancelamento e reembolso"""
    
    @patch('requests.Session.request')
    def test_cancel_pending_payment(self, mock_request, mp_service):
        """Testa cancelamento de pagamento pendente"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "12345",
            "status": "cancelled"
        }
        mock_request.return_value = mock_response
        
        result = mp_service.cancel_payment("12345")
        
        assert result["status"] == "cancelled"
        mock_request.assert_called_with(
            method="PUT",
            url="https://api.mercadopago.com/v1/payments/12345",
            json={"status": "cancelled"},
            timeout=30
        )
    
    @patch('requests.Session.request')
    def test_full_refund(self, mock_request, mp_service):
        """Testa reembolso total"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "refund-123",
            "payment_id": "12345",
            "amount": 105.00,
            "status": "approved"
        }
        mock_request.return_value = mock_response
        
        result = mp_service.refund_payment("12345")
        
        assert result["id"] == "refund-123"
        assert result["amount"] == 105.00
        assert result["status"] == "approved"
    
    @patch('requests.Session.request')
    def test_partial_refund(self, mock_request, mp_service):
        """Testa reembolso parcial"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": "refund-456",
            "payment_id": "12345",
            "amount": 50.00,
            "status": "approved"
        }
        mock_request.return_value = mock_response
        
        result = mp_service.refund_payment("12345", amount=50.00)
        
        assert result["amount"] == 50.00
        mock_request.assert_called_with(
            method="POST",
            url="https://api.mercadopago.com/v1/payments/12345/refunds",
            json={"amount": 50.00},
            timeout=30
        )


# ═══════════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO
# ═══════════════════════════════════════════════════════════

@pytest.mark.integration
class TestMercadoPagoIntegration:
    """Testes de integração com Mercado Pago"""
    
    @pytest.mark.skipif(not pytest.config.getoption("--integration"), 
                        reason="Requer flag --integration")
    def test_real_api_connection(self, mp_service):
        """Testa conexão real com API (apenas em ambiente de teste)"""
        # Este teste só roda com credenciais reais de sandbox
        try:
            result = mp_service._make_request("GET", "/users/me")
            assert "id" in result
            assert "email" in result
        except Exception as e:
            pytest.skip(f"API não disponível: {e}")
    
    def test_complete_payment_flow(self, mp_service):
        """Testa fluxo completo de pagamento (mockado)"""
        with patch.object(mp_service, '_make_request') as mock_request:
            # 1. Cria pagamento
            mock_request.return_value = {
                "id": "payment-123",
                "status": "pending",
                "point_of_interaction": {
                    "transaction_data": {
                        "qr_code": "PIX_CODE"
                    }
                }
            }
            
            # Setup comando
            command = Mock()
            command.id = 1
            command.orders = [Mock(total_price=10000)]
            command.table_id = 10
            command.store_id = 100
            command.customer_name = "Test"
            command.customer_contact = "test@example.com"
            command.discount_amount = 0
            command.service_charge = 0
            
            mp_service.db.query.return_value.filter.return_value.first.return_value = command
            
            payment = mp_service.create_command_payment(1, "pix")
            assert payment["payment_id"] == "payment-123"
            
            # 2. Simula webhook de aprovação
            mock_request.return_value = {
                "id": "payment-123",
                "status": "approved"
            }
            
            transaction = Mock()
            transaction.command_id = 1
            transaction.status = "pending"
            
            mp_service.db.query.return_value.filter.return_value.first.return_value = transaction
            
            webhook_data = {
                "type": "payment",
                "data": {"id": "payment-123"}
            }
            
            success = mp_service.process_webhook(webhook_data)
            assert success is True
            assert transaction.status == "approved"
