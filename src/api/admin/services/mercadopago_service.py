"""
Serviço de integração com Mercado Pago
======================================
Gerencia pagamentos, PIX, webhooks e marketplace
"""

import logging
import hmac
import hashlib
from typing import Dict, Optional, List
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.config import config
from src.core.circuit_breaker import circuit_breaker_decorator

logger = logging.getLogger(__name__)


class MercadoPagoService:
    """Serviço para integração com Mercado Pago
    
    Nota: As credenciais do Mercado Pago são por loja (store).
    Este serviço funciona sem credenciais globais, usando sempre
    o token da loja específica em cada operação.
    """

    def __init__(self):
        logger.info("═" * 60)
        logger.info("🔧 [MercadoPagoService] Inicializando...")

        # ✅ Credenciais são opcionais - sistema usa credenciais por loja
        # Tenta obter do config se existir (para compatibilidade), mas não é obrigatório
        # Usa getattr com valor padrão para evitar erros do Pydantic quando campos não existem
        try:
            # Tenta acessar usando getattr com fallback seguro
            self.app_id = getattr(config, 'MERCADOPAGO_APP_ID', None)
        except (AttributeError, KeyError):
            self.app_id = None
            
        try:
            self.access_token = getattr(config, 'MERCADOPAGO_ACCESS_TOKEN', None)
        except (AttributeError, KeyError):
            self.access_token = None
            
        try:
            self.public_key = getattr(config, 'MERCADOPAGO_PUBLIC_KEY', None)
        except (AttributeError, KeyError):
            self.public_key = None
            
        try:
            self.base_url = getattr(config, 'MERCADOPAGO_API_URL', 'https://api.mercadopago.com')
        except (AttributeError, KeyError):
            self.base_url = 'https://api.mercadopago.com'
            
        try:
            self.environment = getattr(config, 'MERCADOPAGO_ENVIRONMENT', 'production')
        except (AttributeError, KeyError):
            self.environment = 'production'
            
        try:
            self.webhook_secret = getattr(config, 'MERCADOPAGO_WEBHOOK_SECRET', None)
        except (AttributeError, KeyError):
            self.webhook_secret = None

        self.is_test_mode = self.environment.lower() in ["sandbox", "test", "testing"]

        logger.info(f"📋 [Config] Base URL: {self.base_url}")
        logger.info(f"🔧 [Config] Ambiente: {self.environment.upper()}")
        logger.info(f"🔧 [Config] Modo Teste: {self.is_test_mode}")
        
        # ✅ Não requer credenciais globais - cada loja tem suas próprias
        if self.access_token:
            logger.info(f"📋 [Config] Access Token global configurado: {self.access_token[:15]}...")
        else:
            logger.info("ℹ️  [Config] Sistema usa credenciais por loja (sem token global)")

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

        # ✅ Headers padrão (sem token - será fornecido por loja)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        logger.info("✅ [MercadoPagoService] Inicializado com sucesso!")
        logger.info("   ⚠️  Nota: Use sempre store_access_token nas operações")
        logger.info("═" * 60)

    @circuit_breaker_decorator(
        service_name="mercadopago",
        failure_threshold=5,
        recovery_timeout=60,
        max_retries=3
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        access_token: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict:
        """Faz requisição HTTP para a API do Mercado Pago com Circuit Breaker"""

        url = f"{self.base_url}{endpoint}"
        headers = {}

        # Permite usar token de outra loja
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            headers["Authorization"] = f"Bearer {self.access_token}"

        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        logger.info("─" * 60)
        logger.info(f"📤 [Request] {method} {url}")

        if data:
            safe_data = self._mask_sensitive_data(data)
            logger.info(f"📦 [Payload] {safe_data}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=30
            )

            logger.info(f"📥 [Response] Status: {response.status_code}")

            if response.status_code >= 400:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {"message": response.text}

                error_message = error_data.get("message", "Erro desconhecido")

                if response.status_code == 401:
                    logger.error("═" * 60)
                    logger.error("❌ ERRO 401: CREDENCIAIS INVÁLIDAS!")
                    logger.error("═" * 60)
                    logger.error(f"Token usado: {access_token or self.access_token}")
                    logger.error(f"Ambiente: {self.environment}")
                    logger.error(f"Endpoint: {url}")
                    logger.error(f"Resposta: {response.text}")
                    logger.error("═" * 60)

                logger.error(f"❌ Erro {response.status_code}: {error_message}")
                raise MercadoPagoError(error_message)

            logger.info("✅ Requisição bem-sucedida!")
            logger.info("─" * 60)

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Erro de conexão com Mercado Pago: {e}")
            raise MercadoPagoError(f"Erro de conexão: {e}")

    def _mask_sensitive_data(self, data: Dict) -> Dict:
        """Mascara dados sensíveis nos logs"""
        if not isinstance(data, dict):
            return data

        masked = data.copy()
        sensitive_keys = ['access_token', 'secret_key', 'public_key', 'security_code', 'card_number']

        for key in masked:
            if any(sk in key.lower() for sk in sensitive_keys):
                if isinstance(masked[key], str):
                    masked[key] = f"{masked[key][:4]}...{masked[key][-4:]}" if len(masked[key]) > 8 else "****"
            elif isinstance(masked[key], dict):
                masked[key] = self._mask_sensitive_data(masked[key])

        return masked

    # ═══════════════════════════════════════════════════════════
    # PAGAMENTOS
    # ═══════════════════════════════════════════════════════════

    def create_payment(
        self,
        amount: float,
        description: str,
        payer_email: str,
        store_access_token: Optional[str] = None,
        payment_method_id: Optional[str] = "pix",  # pix, credit_card, etc
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Cria um pagamento no Mercado Pago

        Args:
            amount: Valor em R$ (será convertido para centavos)
            description: Descrição do pagamento
            payer_email: Email do pagador
            store_access_token: Token do lojista (se marketplace)
            payment_method_id: Método de pagamento (pix, credit_card, etc)
            metadata: Metadados adicionais

        Returns:
            Dados do pagamento criado
        """

        logger.info("💰 [Create Payment] Iniciando...")
        logger.info(f"   Valor: R$ {amount:.2f}")
        logger.info(f"   Método: {payment_method_id}")
        logger.info(f"   Descrição: {description}")

        payload = {
            "transaction_amount": float(f"{amount:.2f}"),
            "description": description,
            "payment_method_id": payment_method_id,
            "payer": {
                "email": payer_email
            },
            "metadata": metadata or {}
        }

        # Para PIX
        if payment_method_id == "pix":
            payload["point_of_interaction"] = {
                "type": "PIX"
            }

        return self._make_request(
            "POST",
            "/v1/payments",
            data=payload,
            access_token=store_access_token
        )

    def get_payment(self, payment_id: str, store_access_token: Optional[str] = None) -> Dict:
        """
        Busca informações de um pagamento

        Args:
            payment_id: ID do pagamento
            store_access_token: Token do lojista

        Returns:
            Dados do pagamento
        """

        logger.info(f"🔍 [Get Payment] ID: {payment_id}")

        return self._make_request(
            "GET",
            f"/v1/payments/{payment_id}",
            access_token=store_access_token
        )

    def cancel_payment(
        self,
        payment_id: str,
        store_access_token: Optional[str] = None
    ) -> Dict:
        """
        Cancela um pagamento pendente

        Args:
            payment_id: ID do pagamento
            store_access_token: Token do lojista

        Returns:
            Dados atualizados do pagamento
        """

        logger.info(f"❌ [Cancel Payment] ID: {payment_id}")

        return self._make_request(
            "PUT",
            f"/v1/payments/{payment_id}",
            data={"status": "cancelled"},
            access_token=store_access_token
        )

    def refund_payment(
        self,
        payment_id: str,
        amount: Optional[float] = None,
        store_access_token: Optional[str] = None
    ) -> Dict:
        """
        Reembolsa um pagamento aprovado

        Args:
            payment_id: ID do pagamento
            amount: Valor a reembolsar (None = reembolso total)
            store_access_token: Token do lojista

        Returns:
            Dados do reembolso
        """

        logger.info(f"↩️ [Refund Payment] ID: {payment_id}")
        if amount:
            logger.info(f"   Valor: R$ {amount:.2f}")

        payload = {}
        if amount:
            payload["amount"] = float(f"{amount:.2f}")

        return self._make_request(
            "POST",
            f"/v1/payments/{payment_id}/refunds",
            data=payload if payload else None,
            access_token=store_access_token
        )

    # ═══════════════════════════════════════════════════════════
    # PIX
    # ═══════════════════════════════════════════════════════════

    def create_pix_payment(
        self,
        amount: float,
        description: str,
        payer_email: str,
        payer_first_name: str,
        payer_last_name: str,
        payer_document_type: str,  # CPF ou CNPJ
        payer_document_number: str,
        store_access_token: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Cria um pagamento PIX

        Args:
            amount: Valor em R$
            description: Descrição
            payer_email: Email do pagador
            payer_first_name: Nome do pagador
            payer_last_name: Sobrenome do pagador
            payer_document_type: CPF ou CNPJ
            payer_document_number: Documento sem formatação
            store_access_token: Token do lojista
            metadata: Metadados

        Returns:
            Dados do pagamento PIX
        """

        logger.info("💚 [Create PIX Payment] Iniciando...")

        # Limpa documento
        clean_document = ''.join(filter(str.isdigit, payer_document_number))

        payload = {
            "transaction_amount": float(f"{amount:.2f}"),
            "description": description,
            "payment_method_id": "pix",
            "payer": {
                "email": payer_email,
                "first_name": payer_first_name,
                "last_name": payer_last_name,
                "identification": {
                    "type": payer_document_type.lower(),
                    "number": clean_document
                }
            },
            "point_of_interaction": {
                "type": "PIX",
                "transaction_data": {}
            },
            "metadata": metadata or {}
        }

        return self._make_request(
            "POST",
            "/v1/payments",
            data=payload,
            access_token=store_access_token
        )

    # ═══════════════════════════════════════════════════════════
    # WEBHOOK
    # ═══════════════════════════════════════════════════════════

    def verify_webhook_signature(
        self,
        data_id: str,
        request_id: str,
        signature: str
    ) -> bool:
        """
        Verifica a assinatura do webhook do Mercado Pago

        Args:
            data_id: ID do webhook
            request_id: Request ID
            signature: Assinatura recebida

        Returns:
            True se a assinatura for válida
        """

        # Mercado Pago usa HMAC SHA-256
        message = f"id={data_id}&request-id={request_id}"
        expected_signature = hmac.new(
            self.webhook_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    # ═══════════════════════════════════════════════════════════
    # TOKEN E CONECTIVIDADE
    # ═══════════════════════════════════════════════════════════

    def get_credentials(self) -> Dict[str, str]:
        """
        Retorna as credenciais públicas para uso no frontend

        Returns:
            Credenciais públicas
        """

        return {
            "public_key": self.public_key,
            "app_id": self.app_id,
            "environment": self.environment
        }

    def test_connection(self, store_access_token: Optional[str] = None) -> bool:
        """
        Testa a conexão com a API do Mercado Pago

        Args:
            store_access_token: Token da loja para testar

        Returns:
            True se a conexão está OK
        """

        try:
            response = self._make_request(
                "GET",
                "/users/me",
                access_token=store_access_token
            )
            logger.info(f"✅ Conexão OK! User ID: {response.get('id')}")
            return True
        except Exception as e:
            logger.error(f"❌ Falha no teste de conexão: {e}")
            return False


class MercadoPagoError(Exception):
    """Exceção customizada para erros do Mercado Pago"""
    pass


# ✅ Singleton lazy - só instancia quando necessário
# Não requer credenciais globais para funcionar
mercadopago_service = None

def get_mercadopago_service() -> MercadoPagoService:
    """Retorna instância do serviço (lazy initialization)"""
    global mercadopago_service
    if mercadopago_service is None:
        mercadopago_service = MercadoPagoService()
    return mercadopago_service



