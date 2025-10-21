from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from src.core.utils.enums import AuditAction, AuditEntityType


# ===================================================================
# SCHEMAS BASE
# ===================================================================

class AuditLogBase(BaseModel):
    """Schema base com campos comuns"""
    action: AuditAction = Field(..., description="Tipo de ação realizada")
    entity_type: AuditEntityType = Field(..., description="Tipo de entidade afetada")
    entity_id: Optional[int] = Field(None, description="ID da entidade (None para ações bulk)")
    changes: Optional[dict[str, Any]] = Field(None, description="Detalhes das alterações em JSON")
    description: Optional[str] = Field(None, max_length=500, description="Descrição legível da ação")


class AuditLogCreate(AuditLogBase):
    """Schema para criar um log de auditoria (uso interno)"""
    user_id: int
    store_id: Optional[int] = None
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = None


# ===================================================================
# SCHEMAS DE RESPOSTA
# ===================================================================

class UserBasicInfo(BaseModel):
    """Informações básicas do usuário para auditoria"""
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class StoreBasicInfo(BaseModel):
    """Informações básicas da loja para auditoria"""
    id: int
    name: str
    url_slug: str

    model_config = ConfigDict(from_attributes=True)


class AuditLogOut(AuditLogBase):
    """Schema completo de resposta com relacionamentos"""
    id: int
    user_id: Optional[int] = None
    store_id: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime

    # Relacionamentos (carregados via joinedload)
    user: Optional[UserBasicInfo] = None
    store: Optional[StoreBasicInfo] = None

    model_config = ConfigDict(from_attributes=True)


class AuditLogSummary(BaseModel):
    """Versão resumida para listagens"""
    id: int
    action: AuditAction
    entity_type: AuditEntityType
    entity_id: Optional[int]
    description: Optional[str]
    user_name: Optional[str] = Field(None, description="Nome do usuário que fez a ação")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ===================================================================
# SCHEMAS DE FILTRO
# ===================================================================

class AuditLogFilters(BaseModel):
    """Filtros para consulta de logs"""
    entity_type: Optional[AuditEntityType] = None
    entity_id: Optional[int] = None
    action: Optional[AuditAction] = None
    user_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    search: Optional[str] = Field(None, max_length=100, description="Busca na descrição")


# ===================================================================
# SCHEMAS DE ESTATÍSTICAS
# ===================================================================

class AuditActionCount(BaseModel):
    """Contagem de ações por tipo"""
    action: str
    count: int
    last_occurrence: datetime


class AuditUserActivity(BaseModel):
    """Atividade de um usuário"""
    user_id: int
    user_name: str
    total_actions: int
    most_common_action: str
    last_action_at: datetime


class AuditDailyActivity(BaseModel):
    """Atividade diária"""
    date: str  # YYYY-MM-DD
    total_actions: int
    unique_users: int
    most_common_action: str


class AuditStatistics(BaseModel):
    """Estatísticas gerais de auditoria"""
    total_logs: int
    date_range_days: int
    most_active_user: Optional[AuditUserActivity] = None
    top_actions: list[AuditActionCount] = []
    daily_activity: list[AuditDailyActivity] = []


# ===================================================================
# SCHEMAS DE COMPARAÇÃO (PARA HISTÓRICO DE MUDANÇAS)
# ===================================================================

class FieldChange(BaseModel):
    """Representa a mudança de um campo específico"""
    field: str
    old_value: Any
    new_value: Any


class EntityChangeHistory(BaseModel):
    """Histórico de mudanças de uma entidade específica"""
    entity_type: AuditEntityType
    entity_id: int
    changes: list[AuditLogOut]
    total_changes: int


# ===================================================================
# RESPONSE MODELS PARA ENDPOINTS
# ===================================================================

class AuditLogListResponse(BaseModel):
    """Resposta paginada de logs de auditoria"""
    items: list[AuditLogOut]
    total: int
    page: int
    size: int
    pages: int


class AuditLogDetailResponse(AuditLogOut):
    """Resposta detalhada com contexto adicional"""
    related_changes: Optional[list[AuditLogSummary]] = Field(
        None,
        description="Outras alterações relacionadas (mesma entidade)"
    )