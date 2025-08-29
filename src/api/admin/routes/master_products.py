from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

# Importe seus modelos e schemas
from src.core import models
from src.core.database import get_db, GetDBDep  # Sua função para obter a sessão do DB
from src.api.schemas.master_product import MasterProductOut, MasterCategoryOut

router = APIRouter(prefix="/master-products", tags=["Master Products (Catalog)"])


@router.get("/search", response_model=List[MasterProductOut])
def search_master_products(
        db: GetDBDep,
        q: str = Query(
            ...,
            min_length=3,
            title="Termo de Busca",
            description="Pesquise produtos no catálogo por nome ou código de barras (EAN)."
        ),
        category_id: Optional[int] = Query(
            None,
            title="ID da Categoria",
            description="Filtre os resultados por uma categoria específica do catálogo mestre."
        )
):
    """
    Busca produtos no catálogo mestre global.

    Esta rota permite que o painel admin pesquise por produtos industrializados
    para importá-los para o cardápio de uma loja. A busca é case-insensitive
    para nomes e exata para códigos EAN.
    """
    try:
        # Inicia a construção da query base
        query = db.query(models.MasterProduct).options(
            selectinload(models.MasterProduct.category)  # Pré-carrega a categoria para evitar N+1 queries
        )

        # --- Aplica o filtro de categoria se ele for fornecido ---
        if category_id is not None:
            query = query.filter(models.MasterProduct.category_id == category_id)

        # --- Aplica o filtro de busca por nome ou EAN ---
        search_term = f"%{q.lower()}%"
        query = query.filter(
            or_(
                models.MasterProduct.name.ilike(search_term),  # `ilike` é case-insensitive no PostgreSQL
                models.MasterProduct.ean == q
            )
        )

        # Limita o número de resultados e executa a query
        results = query.limit(20).all()

        return results

    except Exception as e:
        # Log do erro no servidor para depuração
        print(f"Erro ao buscar no catálogo de produtos mestre: {e}")
        # Retorna um erro genérico para o cliente
        raise HTTPException(
            status_code=500,
            detail="Ocorreu um erro interno ao processar a busca no catálogo."
        )


@router.get("/categories", response_model=List[MasterCategoryOut])
def get_master_categories(db):
    """
    Retorna uma lista de todas as categorias do catálogo mestre.

    Útil para popular o dropdown de filtro na tela de busca do wizard.
    """
    try:
        return db.query(models.MasterCategory).order_by(models.MasterCategory.name).all()
    except Exception as e:
        print(f"Erro ao buscar categorias mestre: {e}")
        raise HTTPException(status_code=500, detail="Não foi possível carregar as categorias do catálogo.")