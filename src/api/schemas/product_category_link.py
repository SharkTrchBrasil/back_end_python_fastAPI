# src/api/schemas/product_category_link.py

from typing import Optional
from pydantic import BaseModel, ConfigDict

# Importa o schema da categoria para poder aninhá-lo
from .category import CategoryOut


class AppBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProductCategoryLinkOut(AppBaseModel):
    """
    Schema de resposta da API para o vínculo entre um Produto e uma Categoria.

    Ele mostra a qual categoria o produto está vinculado e se há alguma
    regra especial (como preço diferente) apenas para essa categoria.
    """

    # Em vez de mostrar apenas o ID da categoria, mostramos o objeto completo.
    # Isso é mais útil para o frontend.
    category: CategoryOut

    # Campos de override (podem ser nulos se nenhuma regra especial for aplicada)
    price_override: Optional[int] = None
    pos_code_override: Optional[str] = None
    available_override: Optional[bool] = None