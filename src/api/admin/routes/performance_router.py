# src/api/admin/routers/performance_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date

from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep


from src.api.schemas.performance import StorePerformanceSchema
from src.api.admin.services.performance_service import get_store_performance_for_date

router = APIRouter(prefix="/performance", tags=["Performance Analytics"])


@router.get(
    "/{store_id}",
    response_model=StorePerformanceSchema,
    summary="Obtém dados de desempenho para uma loja em uma data específica"
)
def get_performance_data(
        store_id: int,
        db: GetDBDep,
        store: GetStoreDep,
        target_date: date = Query(..., description="A data para a análise no formato YYYY-MM-DD."),


):
    """
    Endpoint para a página de desempenho do Flutter.

    Retorna um agregado de métricas de vendas, produtos, clientes e pagamentos
    para a loja e data especificadas.
    """
    # Adicionar verificação de acesso do usuário à loja aqui, se necessário.
    # Ex: if not user_has_access_to_store(db, current_user.id, store_id):
    #         raise HTTPException(status_code=403, detail="Acesso negado a esta loja.")

    try:
        performance_data = get_store_performance_for_date(db, store.id, target_date)
        return performance_data
    except Exception as e:
        # Log do erro no servidor é uma boa prática
        print(f"❌ Erro ao calcular desempenho para loja {store_id}: {e}")
        raise HTTPException(status_code=500, detail="Ocorreu um erro ao processar os dados de desempenho.")