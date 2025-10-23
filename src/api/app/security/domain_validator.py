# src/core/security/domain_validator.py
from src.core.config import config
from src.core.models import Store


class DomainValidator:
    """
    Validador de domínios para segurança de CORS

    DESENVOLVIMENTO: Permite localhost e qualquer origem (para facilitar testes)
    PRODUÇÃO: Valida rigorosamente contra domínios autorizados
    """

    @staticmethod
    def is_allowed_origin(origin: str, store: Store) -> bool:
        """
        Valida se a origem da requisição está autorizada para esta loja

        Args:
            origin: URL de origem da requisição (ex: http://localhost:3000)
            store: Loja sendo acessada

        Returns:
            True se permitido, False caso contrário
        """

        # ═══════════════════════════════════════════════════════════
        # 🟢 MODO DESENVOLVIMENTO: Permite TUDO (facilita testes)
        # ═══════════════════════════════════════════════════════════
        if config.is_development:
            print(f"🟢 [DEV MODE] Permitindo origem: {origin}")
            return True

        # ═══════════════════════════════════════════════════════════
        # 🔴 MODO PRODUÇÃO: Validação rigorosa
        # ═══════════════════════════════════════════════════════════

        # 1️⃣ Domínios oficiais do MenuHub (sempre permitidos)
        official_domains = [
            f"https://{store.url_slug}.menuhub.com.br",  # Subdomínio da loja
            "https://app.menuhub.com.br",  # App principal
            "https://www.menuhub.com.br",  # Site institucional
            "https://menuhub.com.br",  # Site sem www
        ]

        if origin in official_domains:
            print(f"✅ [PROD] Origem oficial permitida: {origin}")
            return True

        # 2️⃣ Domínios customizados da loja (se configurado)
        if store.custom_domains:
            if origin in store.custom_domains:
                print(f"✅ [PROD] Domínio customizado permitido: {origin}")
                return True

        # 3️⃣ Se chegou aqui, origem NÃO autorizada
        print(f"❌ [PROD] Origem BLOQUEADA: {origin} para loja: {store.url_slug}")
        return False

    @staticmethod
    def get_allowed_origins_for_store(store: Store) -> list[str]:
        """
        Retorna lista completa de origens permitidas para CORS

        Args:
            store: Loja

        Returns:
            Lista de URLs permitidas
        """

        # ═══════════════════════════════════════════════════════════
        # 🟢 MODO DESENVOLVIMENTO: Permite todos os localhosts
        # ═══════════════════════════════════════════════════════════
        if config.is_development:
            return [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                f"https://{store.url_slug}.menuhub.com.br",
                "*"  # Permite tudo em dev
            ]

        # ═══════════════════════════════════════════════════════════
        # 🔴 MODO PRODUÇÃO: Apenas origens autorizadas
        # ═══════════════════════════════════════════════════════════

        allowed_origins = [
            # Domínios oficiais do MenuHub
            f"https://{store.url_slug}.menuhub.com.br",
            "https://app.menuhub.com.br",
            "https://www.menuhub.com.br",
            "https://menuhub.com.br",
        ]

        # Adiciona domínios customizados (se tiver)
        if store.custom_domains:
            allowed_origins.extend(store.custom_domains)

        return allowed_origins

    @staticmethod
    def validate_security_config(store: Store) -> dict:
        """
        Valida e retorna configuração de segurança da loja

        Args:
            store: Loja

        Returns:
            Configuração de segurança processada
        """

        # Configuração padrão
        default_config = {
            "rate_limit_per_minute": 100,
            "allowed_ips": [],
            "blocked_ips": [],
            "require_https": not config.is_development,  # HTTPS obrigatório em prod
        }

        # Se loja tiver configuração customizada, mescla com a padrão
        if store.menu_security_config:
            default_config.update(store.menu_security_config)

        return default_config