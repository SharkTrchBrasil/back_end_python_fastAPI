# Em um arquivo como: src/api/admin/schemas/loyalty_schema.py

from pydantic import BaseModel, Field
from decimal import Decimal
from typing import Optional, List
from datetime import datetime



class LoyaltyConfigUpdateSchema(BaseModel):
    """Schema para o lojista ATUALIZAR as configurações."""
    is_active: bool
    points_per_real: Decimal = Field(..., ge=0, decimal_places=4)

class LoyaltyConfigResponseSchema(BaseModel):
    """Schema para EXIBIR as configurações atuais para o lojista."""
    id: int
    store_id: int
    is_active: bool
    points_per_real: Decimal

    class Config:
        from_attributes = True



class LoyaltyRewardBaseSchema(BaseModel):
    """Campos comuns para criação e atualização de prêmios."""
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    points_threshold: int = Field(..., gt=0) # Pontos devem ser maiores que zero
    product_id: int
    is_active: bool = True

class LoyaltyRewardCreateSchema(LoyaltyRewardBaseSchema):
    """Schema para o lojista CRIAR um novo prêmio."""
    pass

class LoyaltyRewardUpdateSchema(LoyaltyRewardBaseSchema):
    """Schema para o lojista ATUALIZAR um prêmio. Todos os campos são opcionais."""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    points_threshold: Optional[int] = Field(None, gt=0)
    product_id: Optional[int] = None
    is_active: Optional[bool] = None

class SimpleProductSchema(BaseModel):
    """Schema auxiliar para não expor todos os dados do produto."""
    id: int
    name: str

    class Config:
        from_attributes = True

class LoyaltyRewardResponseSchema(LoyaltyRewardBaseSchema):
    """Schema completo para EXIBIR um prêmio, incluindo o ID e nome do produto."""
    id: int
    product: SimpleProductSchema # Aninha as informações do produto

    class Config:
        from_attributes = True




class ClaimedRewardSchema(BaseModel):
    """Schema para mostrar um prêmio que já foi resgatado."""
    loyalty_reward_id: int
    reward_name: str
    claimed_at: datetime

    class Config:
        from_attributes = True


class LoyaltyRewardStatusSchema(LoyaltyRewardResponseSchema):
    """
    Mostra o status de um prêmio da trilha: se já está desbloqueado e/ou
    se já foi resgatado pelo cliente.
    """
    is_unlocked: bool
    is_claimed: bool


class CustomerLoyaltyDashboardSchema(BaseModel):
    """
    O schema principal que monta o dashboard completo de fidelidade
    para um cliente em uma loja específica.
    """
    store_id: int
    points_balance: Decimal
    total_points_earned: Decimal

    # A lista de todos os prêmios da loja, com o status para este cliente
    rewards_track: List[LoyaltyRewardStatusSchema]

    # O histórico de prêmios que este cliente já resgatou
    claimed_rewards_history: List[ClaimedRewardSchema]