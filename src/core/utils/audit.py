from typing import Optional, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import Request

from src.core import models
from src.core.utils.enums import AuditAction, AuditEntityType


class AuditLogger:
    """
    Classe auxiliar para criar logs de auditoria de forma padronizada.

    Uso:
        audit = AuditLogger(db, request, current_user, store)
        audit.log(
            action=AuditAction.CREATE_PRODUCT,
            entity_type=AuditEntityType.PRODUCT,
            entity_id=new_product.id,
            changes=payload.model_dump(),
            description="Novo produto criado via wizard"
        )
    """

    def __init__(
            self,
            db: Session,
            request: Request,
            current_user: models.User,
            store: Optional[models.Store] = None
    ):
        self.db = db
        self.request = request
        self.current_user = current_user
        self.store = store

    def log(
            self,
            action: AuditAction,
            entity_type: AuditEntityType,
            entity_id: Optional[int] = None,
            changes: Optional[dict] = None,
            description: Optional[str] = None,
            additional_data: Optional[dict] = None
    ) -> models.AuditLog:
        """
        Cria um registro de auditoria.

        Args:
            action: Tipo de ação realizada (use AuditAction enum)
            entity_type: Tipo de entidade afetada (use AuditEntityType enum)
            entity_id: ID da entidade (opcional para ações bulk)
            changes: Dicionário com as mudanças realizadas
            description: Descrição legível da ação
            additional_data: Dados extras para contexto

        Returns:
            O objeto AuditLog criado
        """

        # Mescla changes com additional_data se ambos existirem
        final_changes = {}
        if changes:
            final_changes.update(changes)
        if additional_data:
            final_changes.update({"_metadata": additional_data})

        audit_log = models.AuditLog(
            user_id=self.current_user.id,
            store_id=self.store.id if self.store else None,
            action=action.value,
            entity_type=entity_type.value,
            entity_id=entity_id,
            changes=final_changes if final_changes else None,
            ip_address=self.request.client.host if self.request.client else None,
            user_agent=self.request.headers.get("user-agent"),
            description=description
        )

        self.db.add(audit_log)
        # NÃO fazemos commit aqui, deixamos a rota fazer
        return audit_log

    def log_bulk(
            self,
            action: AuditAction,
            entity_type: AuditEntityType,
            entity_ids: list[int],
            changes: Optional[dict] = None,
            description: Optional[str] = None
    ) -> models.AuditLog:
        """
        Versão especializada para ações em massa.
        Registra múltiplos IDs em um único log.
        """
        bulk_changes = {
            "affected_ids": entity_ids,
            "count": len(entity_ids)
        }

        if changes:
            bulk_changes.update(changes)

        return self.log(
            action=action,
            entity_type=entity_type,
            entity_id=None,  # Bulk não tem um ID único
            changes=bulk_changes,
            description=description or f"Ação em massa em {len(entity_ids)} itens"
        )

    def log_failed_action(
            self,
            action: AuditAction,
            entity_type: AuditEntityType,
            error: str,
            entity_id: Optional[int] = None
    ) -> models.AuditLog:
        """
        Registra uma tentativa de ação que falhou.
        Útil para auditoria de segurança.
        """
        return self.log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            changes={"error": error, "success": False},
            description=f"Falha ao executar {action.value}: {error}"
        )