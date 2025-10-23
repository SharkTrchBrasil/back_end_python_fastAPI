# src/core/security/domain_validator.py
from src.core.config import config
from src.core.models import Store


class DomainValidator:
    @staticmethod
    def is_allowed_origin(origin: str, store: Store) -> bool:
        """
        Valida se a origem da requisição está autorizada para esta loja
        """
        # Domínios sempre permitidos (oficiais)
        official_domains = [
            f"https://{store.url_slug}.menuhub.com.br",
            "https://app.menuhub.com.br",
            "https://menuhub.com.br",
        ]

        # Domínios customizados da loja (se tiver)
        custom_domains = store.custom_domains or []  # JSON array

        allowed = official_domains + custom_domains

        # Em desenvolvimento, permite localhost
        if config.is_development:
            allowed.extend([
                "http://localhost:3000",
                "http://localhost:57121",
                # ... outras portas
            ])

        return origin in allowed