# src/api/app/services/connection_token_service.py
import secrets
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from src.core import models

class ConnectionTokenService:
    """
    Gerencia a criação e validação de tokens de conexão de uso único (nonces).
    Estes tokens são usados para a transição segura da autenticação HTTP para a conexão WebSocket.
    """
    _TOKEN_VALIDITY_SECONDS = 30  # O token é válido por apenas 30 segundos

    @staticmethod
    def generate_token(db: Session, totem_auth_id: int) -> str:
        """
        Gera um novo token de conexão de uso único para uma autorização de totem.
        """
        # Gera um token criptograficamente seguro
        token_value = secrets.token_urlsafe(32)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ConnectionTokenService._TOKEN_VALIDITY_SECONDS)

        # Cria a entrada no banco de dados
        conn_token = models.ConnectionToken(
            token=token_value,
            totem_authorization_id=totem_auth_id,
            expires_at=expires_at
        )
        db.add(conn_token)
        db.commit()
        db.refresh(conn_token)

        return token_value

    @staticmethod
    def validate_and_consume_token(db: Session, token: str) -> models.TotemAuthorization | None:
        """
        Valida um token de conexão de forma atômica. Se válido, consome-o e retorna a autorização associada.
        Esta operação é segura contra "race conditions".
        """
        if not token:
            return None

        # --- ✅ MELHORIA DE ROBUSTEZ ---
        # `with_for_update()` instrui o banco de dados a bloquear a linha do token
        # assim que ela é lida. Nenhuma outra transação pode ler ou modificar esta
        # linha até que a transação atual seja concluída (com `db.commit()`).
        # Isso garante que o token não possa ser validado duas vezes simultaneamente.
        conn_token = db.query(models.ConnectionToken).filter(
            models.ConnectionToken.token == token
        ).with_for_update().first()

        # 1. Verifica se o token existe
        if not conn_token:
            return None  # Token não encontrado

        # 2. Verifica se o token já foi usado
        if conn_token.is_used:
            return None  # Token já consumido

        # 3. Verifica se o token expirou
        if conn_token.expires_at < datetime.now(timezone.utc):
            return None  # Token expirado

        # 4. Verifica se a autorização do totem associada ainda é válida
        totem_auth = conn_token.totem_authorization
        if not totem_auth or not totem_auth.granted:
            return None  # Autorização do totem foi revogada

        # Se tudo estiver OK, marca o token como usado (consumido)
        conn_token.is_used = True
        db.commit() # O commit libera o bloqueio da linha

        # Retorna a autorização principal para o handler de conexão
        return totem_auth