# Em src/api/shared_schemas/store.py

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, computed_field, ConfigDict
from typing import List, Optional

from src.api.admin.schemas.store_subscription import StoreSubscriptionSchema
from src.core.aws import get_presigned_url
from src.core.models import StoreVerificationStatus


class Roles(Enum):
    OWNER = 'owner'
    MANAGER = 'manager'
    ADMIN = 'admin'


# --- Schema Base ---
# Contém todos os campos que podem ser EDITADOS pelo usuário.
# Usado como base para o schema de leitura e de atualização.
class Store(BaseModel):
    # --- Identificação Básica ---
    name: str = Field(min_length=3, max_length=100)
    url_slug: str
    description: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    cnpj: Optional[str] = None
    segment_id: Optional[int] = None

    # --- Endereço e Logística ---
    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_radius_km: Optional[float] = None

    # --- Operacional ---
    average_preparation_time: Optional[int] = None  # Em minutos

    # --- Responsável Operacional ---
    responsible_name: Optional[str] = None
    responsible_phone: Optional[str] = None

    # --- Marketing e SEO ---
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    # --- Mídia ---
    file_key: Optional[str] = None
    banner_file_key: Optional[str] = None


# --- Schema para Criação Inicial (POST /stores) ---
# Apenas os campos mínimos necessários para criar a loja. O resto vem do wizard.
class StoreCreate(BaseModel):
    name: str
    phone: str
    store_url: str  # Frontend envia a URL gerada


# --- Schema para Atualização (PATCH /stores/{id}) ---
# Contém TODOS os campos editáveis, mas todos são opcionais.
class StoreUpdate(Store):
    # Herda todos os campos do StoreBase, mas os torna opcionais
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    url_slug: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)

    # Flag para indicar a conclusão do wizard
    is_setup_complete: Optional[bool] = None


# --- Schema para Leitura (Saída da API) ---
# A representação completa de uma loja que a API retorna.
class StoreSchema(Store):
    id: int

    # --- Campos de Gerenciamento da Plataforma ---
    is_active: bool
    is_setup_complete: bool
    is_featured: bool
    verification_status: StoreVerificationStatus

    # --- Campos Agregados ---
    rating_average: float = 0.0
    rating_count: int = 0

    # --- Relacionamentos ---
    active_subscription: Optional[StoreSubscriptionSchema] = None

    # --- Campos Computados para URLs de Imagem ---
    @computed_field
    @property
    def image_path(self) -> str:
        return get_presigned_url(self.file_key) if self.file_key else ""

    @computed_field
    @property
    def banner_path(self) -> str:
        return get_presigned_url(self.banner_file_key) if self.banner_file_key else ""

    # Configuração Pydantic v2
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# --- Schemas para Acesso ---
class RoleSchema(BaseModel):
    machine_name: str
    model_config = ConfigDict(from_attributes=True)


class StoreWithRole(BaseModel):
    store: StoreSchema
    role: RoleSchema
    model_config = ConfigDict(from_attributes=True)