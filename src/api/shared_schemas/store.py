
from pydantic import BaseModel, Field, computed_field, ConfigDict
from typing import List, Optional

from src.api.admin.schemas.store_subscription import StoreSubscriptionSchema
from src.core.utils.enums import StoreVerificationStatus
from src.core.aws import get_presigned_url




# --- Schemas aninhados para a criação (Estão perfeitos!) ---
class AddressCreate(BaseModel):
    cep: str
    street: str
    number: str
    complement: Optional[str] = None
    neighborhood: str
    city: str
    uf: str

class ResponsibleCreate(BaseModel):
    name: str
    phone: str


class Store(BaseModel):
    # --- Identificação Básica ---
    name: str = Field(min_length=3, max_length=100)
    url_slug: str
    description: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    cnpj: Optional[str] = None
    segment_id: Optional[int] = None

    # --- Endereço (Corrigido para ser plano) ---
    zip_code: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None # Corrigido de uf para state, para bater com o banco

    # --- Responsável (Corrigido para ser plano) ---
    responsible_name: Optional[str] = None


    latitude: Optional[float] = None
    longitude: Optional[float] = None
    delivery_radius_km: Optional[float] = None

    # --- Operacional ---
    average_preparation_time: Optional[int] = None  # Em minutos


    # --- Marketing e SEO ---
    tags: Optional[List[str]] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None

    # --- Mídia ---
    file_key: Optional[str] = None
    banner_file_key: Optional[str] = None


# --- ✅ Schema para Criação via Wizard (Corrigido e Completo) ---
class StoreCreate(BaseModel):
    # Dados da Loja
    name: str
    store_url: str
    description: Optional[str] = None
    phone: str

    # Dados Fiscais e de Especialidade
    cnpj: Optional[str] = None
    segment_id: int
    plan_id: int

    # Objetos Aninhados
    address: AddressCreate
    responsible: ResponsibleCreate




class StoreUpdate(Store):

    name: Optional[str] = Field(None, min_length=3, max_length=100)
    url_slug: Optional[str] = None
    phone: Optional[str] = Field(None, min_length=10, max_length=15)


    is_setup_complete: Optional[bool] = None



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