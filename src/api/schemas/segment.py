# schemas/segment.py

from pydantic import BaseModel, ConfigDict

# --- Schema Base ---
# Contém os campos comuns que são compartilhados entre criação e leitura.
class SegmentBase(BaseModel):
    name: str
    description: str | None = None
    is_active: bool = True

# --- Schema para Criação ---
# Usado no corpo da requisição POST para criar um novo segmento.
class SegmentCreate(SegmentBase):
    pass  # Herda todos os campos do SegmentBase

# --- Schema para Atualização ---
# Usado no corpo da requisição PUT/PATCH. Todos os campos são opcionais.
class SegmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None

# --- Schema para Leitura (Saída) ---
# Define como um segmento será retornado pela API. Inclui o 'id'.
class SegmentSchema(SegmentBase):
    id: int

    # Configuração para permitir que o Pydantic leia os dados
    # diretamente de um objeto SQLAlchemy (ORM).
    model_config = ConfigDict(from_attributes=True)