# src/api/admin/routers/performance_router.py

from fastapi import APIRouter, Depends, Query, HTTPException  # Remova HTTPException se não for usado diretamente aqui
from sqlalchemy.orm import Session
from datetime import date

from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep
from src.api.schemas.performance import StorePerformanceSchema
from src.api.admin.services.performance_service import get_store_performance_for_date


router = APIRouter(prefix="/stores/{store_id}/performance", tags=["Performance Analytics"])


@router.get(
    "/", # ✅ MUDANÇA 2: O caminho agora é a raiz do prefixo.
    response_model=StorePerformanceSchema,
    summary="Obtém dados de desempenho para uma loja em uma data específica"
)
def get_performance_data(
    # ✅ MUDANÇA 3: Remova 'store_id: int', pois a dependência 'GetStoreDep' já cuida disso.
    db: GetDBDep,
    store: GetStoreDep,
    target_date: date = Query(..., description="A data para a análise no formato YYYY-MM-DD."),
):
    """
    Endpoint para a página de desempenho do Flutter.
    ...
    """
    try:
        # O 'store' já vem validado e carregado pela dependência GetStoreDep.
        performance_data = get_store_performance_for_date(db, store.id, target_date)
        return performance_data
    except Exception as e:
        print(f"❌ Erro ao calcular desempenho para loja {store.id}: {e}")
        # Retornar um erro 500 genérico é mais seguro em produção.
        # A exceção específica pode ser logada no seu servidor.
        raise HTTPException(status_code=500, detail="Ocorreu um erro ao processar os dados de desempenho.")