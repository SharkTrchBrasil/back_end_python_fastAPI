# src/api/app/services/totem_authorization_service.py
from sqlalchemy.orm import Session, joinedload
from src.core import models


class TotemAuthorizationService:
    """
    Serviço focado na autorização de totens e na gestão de suas autorizações persistentes.
    """

    @staticmethod
    def authorize_or_create(db: Session, store_url: str, totem_token: str) -> models.TotemAuthorization | None:
        """
        Valida o token persistente de um totem (UUID) e o `store_url`.
        - Se a autorização já existe, a retorna.
        - Se não existe, cria uma nova autorização para este totem na loja especificada.
        - Retorna `None` se a loja não for encontrada.

        Este método é usado pela API REST para verificar se o dispositivo tem permissão
        para solicitar um token de conexão.
        """
        if not totem_token or not store_url:
            return None

        # 1. Busca a loja para garantir que ela existe.
        store = db.query(models.Store).filter(models.Store.url_slug == store_url).first()
        if not store:
            return None  # Loja não encontrada, não há o que autorizar.

        # 2. Busca a autorização do totem pelo token persistente.
        totem_auth = db.query(models.TotemAuthorization).options(
            joinedload(models.TotemAuthorization.store)
        ).filter(
            models.TotemAuthorization.totem_token == totem_token
        ).first()

        if totem_auth:
            # 3a. Se já existe, garante que está ativa e associada à loja correta.
            totem_auth.store_id = store.id
            totem_auth.store_url = store.url_slug
            totem_auth.granted = True
        else:
            # 3b. Se não existe, cria uma nova autorização já concedida.
            totem_auth = models.TotemAuthorization(
                totem_token=totem_token,
                store_id=store.id,
                store_url=store.url_slug,
                granted=True,
                totem_name=f"Totem {store.name}",  # Nome padrão
                public_key=totem_token  # Reutilizando o token como chave pública inicial
            )
            db.add(totem_auth)

        # 4. Comita a criação/atualização e retorna o objeto.
        db.commit()
        db.refresh(totem_auth)

        return totem_auth