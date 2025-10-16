"""
Serviço de integração com Pagar.me
===================================
Gerencia tokenização de cartões, criação de clientes e cobranças
"""

import logging
import base64
from typing import Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.core.config import config

logger = logging.getLogger(__name__)


class PagarmeService:
    def __init__(self):
        logger.info("═" * 60)
        logger.info("🔧 [PagarmeService] Inicializando...")

        self.secret_key = config.PAGARME_SECRET_KEY
        self.public_key = config.PAGARME_PUBLIC_KEY
        self.base_url = config.PAGARME_API_URL
        self.environment = config.PAGARME_ENVIRONMENT

        self.is_test_mode = self.environment.lower() in ["test", "testing", "development", "dev"]

        logger.info(f"📋 [Config] Secret Key: {self.secret_key[:10]}...{self.secret_key[-4:]} (tamanho: {len(self.secret_key)})")
        logger.info(f"📋 [Config] Public Key: {self.public_key}")
        logger.info(f"📋 [Config] Base URL: {self.base_url}")
        logger.info(f"🔧 [Config] Ambiente: {self.environment.upper()}")
        logger.info(f"🔧 [Config] Modo Teste: {self.is_test_mode}")

        if not self.secret_key:
            logger.error("❌ PAGARME_SECRET_KEY não está configurada!")
            raise ValueError("PAGARME_SECRET_KEY não está configurada!")

        if not self.secret_key.startswith('sk_'):
            logger.error(f"❌ Secret Key inválida! Deve começar com 'sk_'")
            raise ValueError("PAGARME_SECRET_KEY inválida! Deve começar com 'sk_'")

        credentials = f"{self.secret_key}:"
        logger.info(f"🔐 [Auth] Credentials (antes do base64): {credentials[:15]}...")

        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        logger.info(f"🔐 [Auth] Credentials (depois do base64): {encoded_credentials[:30]}...")

        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.session.headers.update({
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        logger.info(f"📤 [Headers] Authorization: Basic {encoded_credentials[:30]}...")
        logger.info(f"📤 [Headers] Content-Type: application/json")
        logger.info("✅ [PagarmeService] Inicializado com sucesso!")
        logger.info("═" * 60)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        idempotency_key: Optional[str] = None
    ) -> Dict:
        """Faz requisição HTTP para a API do Pagar.me"""

        url = f"{self.base_url}{endpoint}"
        headers = {}

        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        logger.info("─" * 60)
        logger.info(f"📤 [Request] {method} {url}")

        if data:
            safe_data = self._mask_sensitive_data(data)
            logger.info(f"📦 [Payload] {safe_data}")

        if headers:
            logger.info(f"📋 [Headers Extras] {headers}")

        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                headers=headers,
                timeout=30
            )

            logger.info(f"📥 [Response] Status: {response.status_code}")
            logger.info(f"📥 [Response] Headers: {dict(response.headers)}")

            response_text = response.text[:500]
            logger.info(f"📥 [Response] Body: {response_text}...")

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
                    logger.error(f"Secret Key usada: {self.secret_key[:10]}...{self.secret_key[-4:]}")
                    logger.error(f"Ambiente configurado: {self.environment}")
                    logger.error(f"Authorization header: {self.session.headers.get('Authorization')[:50]}...")
                    logger.error(f"Endpoint tentado: {url}")
                    logger.error(f"Resposta completa: {response.text}")
                    logger.error("═" * 60)
                    logger.error("🔍 VERIFICAÇÕES:")
                    logger.error("   1. A Secret Key está correta no dashboard Pagar.me?")
                    logger.error("   2. O ambiente (test/production) está correto?")
                    logger.error("   3. A conta Pagar.me está ativa?")
                    logger.error("   4. As variáveis de ambiente foram atualizadas?")
                    logger.error("═" * 60)

                    raise PagarmeError(
                        "Credenciais do Pagar.me inválidas. "
                        "Verifique a Secret Key e o ambiente no dashboard e nas variáveis de ambiente."
                    )

                logger.error(f"❌ Erro {response.status_code}: {error_message}")
                logger.error(f"❌ Detalhes completos: {error_data}")

                raise PagarmeError(error_message)

            logger.info("✅ Requisição bem-sucedida!")
            logger.info("─" * 60)

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("═" * 60)
            logger.error(f"❌ ERRO DE CONEXÃO!")
            logger.error(f"   Tipo: {type(e).__name__}")
            logger.error(f"   Mensagem: {e}")
            logger.error(f"   URL tentada: {url}")
            logger.error("═" * 60)
            raise PagarmeError(f"Erro de conexão com Pagar.me: {e}")

    def _mask_sensitive_data(self, data: Dict) -> Dict:
        """Mascara dados sensíveis nos logs"""
        if not isinstance(data, dict):
            return data

        masked = data.copy()
        sensitive_keys = ['cvv', 'number', 'password', 'token']

        for key in masked:
            if any(sk in key.lower() for sk in sensitive_keys):
                if isinstance(masked[key], str):
                    masked[key] = f"{masked[key][:4]}...{masked[key][-4:]}" if len(masked[key]) > 8 else "****"
            elif isinstance(masked[key], dict):
                masked[key] = self._mask_sensitive_data(masked[key])

        return masked

    def create_customer(
        self,
        email: str,
        name: str,
        document: str,
        phone: str,
        store_id: int
    ) -> Dict:
        """
        Cria um cliente no Pagar.me.

        Args:
            email: Email do cliente
            name: Nome do cliente
            document: CPF ou CNPJ (com ou sem formatação)
            phone: Telefone (com ou sem formatação)
            store_id: ID da loja para metadata

        Returns:
            Resposta da API do Pagar.me com dados do customer criado

        Raises:
            PagarmeError: Se houver erro na criação
        """

        logger.info("🆕 [Create Customer] Iniciando...")
        logger.info(f"   Email: {email}")
        logger.info(f"   Nome: {name}")
        logger.info(f"   Documento: {document[:3]}...{document[-2:]}")
        logger.info(f"   Store ID: {store_id}")

        clean_document = "".join(filter(str.isdigit, document))

        if len(clean_document) not in [11, 14]:
            raise PagarmeError(
                f"Documento inválido: deve ter 11 (CPF) ou 14 (CNPJ) dígitos. "
                f"Recebido: {len(clean_document)} dígitos"
            )

        clean_phone = "".join(filter(str.isdigit, phone))

        if clean_phone.startswith('55') and len(clean_phone) > 11:
            clean_phone = clean_phone[2:]

        if len(clean_phone) < 10:
            raise PagarmeError(
                f"Telefone inválido: deve ter no mínimo 10 dígitos. "
                f"Recebido: {phone} ({len(clean_phone)} dígitos)"
            )

        area_code = clean_phone[:2]
        number = clean_phone[2:]

        logger.info(f"   Telefone processado: ({area_code}) {number}")

        payload = {
            "name": name[:100],
            "email": email[:100],
            "document": clean_document,
            "type": "individual" if len(clean_document) == 11 else "company",
            "phones": {
                "mobile_phone": {
                    "country_code": "55",
                    "area_code": area_code,
                    "number": number
                }
            },
            "metadata": {
                "store_id": str(store_id)
            }
        }

        idempotency_key = f"customer-{clean_document}-{store_id}"

        return self._make_request(
            "POST",
            "/customers",
            data=payload,
            idempotency_key=idempotency_key
        )



    def create_card(
            self,
            customer_id: str,
            card_token: str,
            billing_address: Optional[Dict] = None,
            verify_card: Optional[bool] = None
    ) -> Dict:
        """
        Adiciona um cartão ao cliente no Pagar.me.
        """

        logger.info("💳 [Create Card] Iniciando...")
        logger.info(f"   Customer ID: {customer_id}")
        logger.info(f"   Token: {card_token[:20]}...")

        if verify_card is None:
            verify_card = not self.is_test_mode

        logger.info(f"   Ambiente: {self.environment.upper()}")
        logger.info(f"   Modo Teste: {self.is_test_mode}")
        logger.info(f"   Verificar cartão: {verify_card}")

        if not billing_address:
            billing_address = {
                "line_1": "Rua Exemplo, 100",
                "zip_code": "01310100",
                "city": "São Paulo",
                "state": "SP",
                "country": "BR"
            }

        billing_address = {k: v for k, v in billing_address.items() if v is not None}

        logger.info(f"   Endereço: {billing_address.get('line_1')}")
        logger.info(f"   Cidade/Estado: {billing_address.get('city')}/{billing_address.get('state')}")

        payload = {
            "token": card_token,
            "billing_address": billing_address,
            "options": {
                "verify_card": verify_card
            }
        }

        # ✅ FAZ A REQUISIÇÃO
        response = self._make_request(
            "POST",
            f"/customers/{customer_id}/cards",
            data=payload
        )

        # ✅ ADICIONE ESTES LOGS EXTRAS
        logger.info("═" * 60)
        logger.info("✅ [Create Card] RESPOSTA COMPLETA DO PAGAR.ME:")
        logger.info("═" * 60)
        logger.info(f"   Tipo: {type(response)}")
        logger.info(f"   Chaves: {list(response.keys())}")
        logger.info(f"   ID do Cartão: {response.get('id')}")
        logger.info(f"   Status: {response.get('status')}")
        logger.info(f"   Last 4 Digits: {response.get('last_four_digits')}")
        logger.info(f"   Brand: {response.get('brand')}")
        logger.info(f"   Resposta Completa: {response}")
        logger.info("═" * 60)

        return response







    def get_card(
        self,
        customer_id: str,
        card_id: str
    ) -> Dict:
        """
        Busca informações de um cartão específico.

        Args:
            customer_id: ID do customer no Pagar.me
            card_id: ID do cartão

        Returns:
            Dados do cartão (mascarados pela API)

        Raises:
            PagarmeError: Se houver erro na busca
        """

        logger.info("💳 [Get Card] Iniciando...")
        logger.info(f"   Customer ID: {customer_id}")
        logger.info(f"   Card ID: {card_id}")

        return self._make_request(
            "GET",
            f"/customers/{customer_id}/cards/{card_id}"
        )

    def create_charge(
        self,
        customer_id: str,
        card_id: str,
        amount_in_cents: int,
        description: str,
        store_id: int,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Cria uma cobrança"""

        logger.info("💰 [Create Charge] Iniciando...")
        logger.info(f"   Customer ID: {customer_id}")
        logger.info(f"   Card ID: {card_id}")
        logger.info(f"   Valor: R$ {amount_in_cents/100:.2f}")
        logger.info(f"   Descrição: {description}")

        payload = {
            "amount": amount_in_cents,
            "description": description,
            "payment_method": "credit_card",
            "credit_card": {
                "card_id": card_id,
                "statement_descriptor": "MENUHUB"
            },
            "customer": {
                "id": customer_id
            },
            "metadata": {
                "store_id": str(store_id),
                **(metadata or {})
            }
        }

        return self._make_request(
            "POST",
            "/charges",
            data=payload
        )


class PagarmeError(Exception):
    """Exceção customizada para erros do Pagar.me"""
    pass


# Singleton
pagarme_service = PagarmeService()