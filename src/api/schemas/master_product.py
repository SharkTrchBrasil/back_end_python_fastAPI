# src/api/schemas/master_product.py

from pydantic import BaseModel, ConfigDict


# ✅ NOVO SCHEMA PARA A CATEGORIA
class MasterCategoryOut(BaseModel):
    """
    Schema de resposta para uma categoria do catálogo mestre.
    Contém apenas os campos necessários para o frontend (ex: um dropdown de filtro).
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# Schema do produto mestre que você já tinha
class MasterProductOut(BaseModel):
    """
    Schema de resposta para um produto do catálogo mestre.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    ean: str | None
    brand: str | None
    image_path: str | None

    # ✅ RELACIONAMENTO: Inclui os dados da categoria no produto retornado
    category: MasterCategoryOut | None