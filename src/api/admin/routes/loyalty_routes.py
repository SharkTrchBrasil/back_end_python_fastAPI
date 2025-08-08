# Em: src/api/admin/routes/loyalty_routes.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

# --- Schemas ---
from src.api.admin.schemas.loyalty_schema import (
    LoyaltyConfigUpdateSchema,
    LoyaltyConfigResponseSchema,
    LoyaltyRewardCreateSchema,
    LoyaltyRewardResponseSchema,
    LoyaltyRewardUpdateSchema  # ✅ Adicionado para a rota de atualização
)

# --- Serviços ---
from src.api.admin.services import loyalty_service

# --- Dependências ---
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

# --- Modelos ---
from src.core import models

# Roteador para organizar todas as rotas de fidelidade
router = APIRouter(
    prefix="/stores/{store_id}/loyalty",
    tags=["Admin Loyalty"]
)


# --- Rota para Configuração do Programa ---
@router.put("/config", response_model=LoyaltyConfigResponseSchema)
def create_or_update_loyalty_config(
    db: GetDBDep, store: GetStoreDep, config_data: LoyaltyConfigUpdateSchema
):
    try:
        return loyalty_service.create_or_update_config(db=db, store_id=store.id, config_data=config_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao salvar a configuração.")


# --- Rotas para Gerenciamento de Prêmios (CRUD Completo) ---
@router.post("/rewards", response_model=LoyaltyRewardResponseSchema, status_code=status.HTTP_201_CREATED)
def create_loyalty_reward(
    db: GetDBDep, store: GetStoreDep, reward_data: LoyaltyRewardCreateSchema
):
    try:
        return loyalty_service.create_reward(db=db, store_id=store.id, reward_data=reward_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao criar o prêmio.")


@router.get("/rewards", response_model=List[LoyaltyRewardResponseSchema])
def list_loyalty_rewards(
    db: GetDBDep, store: GetStoreDep
):
    return loyalty_service.get_rewards_by_store(db=db, store_id=store.id)


# ✅ --- NOVA ROTA DE ATUALIZAÇÃO ---
@router.put("/rewards/{reward_id}", response_model=LoyaltyRewardResponseSchema)
def update_loyalty_reward(
    reward_id: int,
    db: GetDBDep,
    store: GetStoreDep,
    reward_data: LoyaltyRewardUpdateSchema
):
    try:
        return loyalty_service.update_reward(
            db=db,
            store_id=store.id,
            reward_id=reward_id,
            reward_data=reward_data
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao atualizar o prêmio.")


# ✅ --- NOVA ROTA DE DELEÇÃO ---
@router.delete("/rewards/{reward_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loyalty_reward(
    reward_id: int,
    db: GetDBDep,
    store: GetStoreDep
):
    try:
        loyalty_service.delete_reward(db=db, store_id=store.id, reward_id=reward_id)
        return
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erro interno ao deletar o prêmio.")