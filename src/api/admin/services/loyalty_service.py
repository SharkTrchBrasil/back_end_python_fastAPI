# Em: src/api/admin/services/loyalty_service.py
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload
from typing import List

from src.core import models
from src.api.admin.schemas.loyalty_schema import (
    LoyaltyConfigUpdateSchema,
    LoyaltyRewardCreateSchema,
    LoyaltyRewardUpdateSchema, LoyaltyRewardStatusSchema,
    SimpleProductSchema, ClaimedRewardSchema,
    CustomerLoyaltyDashboardSchema  # ✅ Adicionado para a função de atualização
)


# --- Função para Gerenciar a Configuração ---
def create_or_update_config(db: Session, store_id: int, config_data: LoyaltyConfigUpdateSchema) -> models.LoyaltyConfig:
    config = db.query(models.LoyaltyConfig).filter_by(store_id=store_id).first()
    if not config:
        store = db.query(models.Store).filter_by(id=store_id).first()
        if not store:
            raise ValueError(f"Loja com ID {store_id} não encontrada.")
        config = models.LoyaltyConfig(store_id=store_id, **config_data.model_dump())
        db.add(config)
    else:
        config.is_active = config_data.is_active
        config.points_per_real = config_data.points_per_real
    db.commit()
    db.refresh(config)
    return config


# --- Funções para Gerenciar os Prêmios (CRUD Completo) ---
def create_reward(db: Session, store_id: int, reward_data: LoyaltyRewardCreateSchema) -> models.LoyaltyReward:
    product_to_be_reward = db.query(models.Product).filter(
        models.Product.id == reward_data.product_id,
        models.Product.store_id == store_id
    ).first()
    if not product_to_be_reward:
        raise ValueError(f"Produto com ID {reward_data.product_id} não encontrado ou não pertence a esta loja.")
    new_reward = models.LoyaltyReward(store_id=store_id, **reward_data.model_dump())
    db.add(new_reward)
    db.commit()
    db.refresh(new_reward)
    return new_reward


def get_rewards_by_store(db: Session, store_id: int) -> List[models.LoyaltyReward]:
    return db.query(models.LoyaltyReward).filter(
        models.LoyaltyReward.store_id == store_id
    ).options(
        joinedload(models.LoyaltyReward.product)
    ).order_by(
        models.LoyaltyReward.points_threshold
    ).all()


# ✅ --- NOVA FUNÇÃO DE ATUALIZAÇÃO ---
def update_reward(db: Session, store_id: int, reward_id: int,
                  reward_data: LoyaltyRewardUpdateSchema) -> models.LoyaltyReward:
    reward_to_update = db.query(models.LoyaltyReward).filter(
        models.LoyaltyReward.id == reward_id,
        models.LoyaltyReward.store_id == store_id
    ).first()
    if not reward_to_update:
        raise ValueError(f"Prêmio com ID {reward_id} não encontrado ou não pertence a esta loja.")

    update_data = reward_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(reward_to_update, key, value)

    db.commit()
    db.refresh(reward_to_update)
    return reward_to_update


# ✅ --- NOVA FUNÇÃO DE DELEÇÃO ---
def delete_reward(db: Session, store_id: int, reward_id: int) -> None:
    reward_to_delete = db.query(models.LoyaltyReward).filter(
        models.LoyaltyReward.id == reward_id,
        models.LoyaltyReward.store_id == store_id
    ).first()
    if not reward_to_delete:
        raise ValueError(f"Prêmio com ID {reward_id} não encontrado ou não pertence a esta loja.")
    db.delete(reward_to_delete)
    db.commit()
    return


# ✅ --- NOVAS FUNÇÕES (Lógica do Cliente) ---

def award_points_for_order(db: Session, order: models.Order):
    """Calcula e concede pontos de fidelidade para um pedido concluído."""
    config = db.query(models.LoyaltyConfig).filter_by(store_id=order.store_id).first()

    # Se o programa de pontos não existe ou está inativo para a loja, não faz nada.
    if not config or not config.is_active or config.points_per_real <= 0:
        return

    # Calcula os pontos com base no valor final do pedido (em Reais)
    amount_in_reais = Decimal(order.discounted_total_price) / 100
    points_to_award = amount_in_reais * config.points_per_real

    if points_to_award <= 0:
        return

    # Encontra o "saldo" do cliente na loja ou cria um novo
    loyalty_balance = db.query(models.CustomerStoreLoyalty).filter_by(
        customer_id=order.customer_id,
        store_id=order.store_id
    ).first()
    if not loyalty_balance:
        loyalty_balance = models.CustomerStoreLoyalty(
            customer_id=order.customer_id,
            store_id=order.store_id
        )
        db.add(loyalty_balance)

    # Atualiza os saldos (o atual para gastos e o total para o progresso)
    loyalty_balance.points_balance += points_to_award
    loyalty_balance.total_points_earned += points_to_award

    # Cria o registro de transação para auditoria
    transaction = models.LoyaltyTransaction(
        customer_store_loyalty_id=loyalty_balance.id,
        points_amount=points_to_award,
        transaction_type='earn',
        description=f"Pontos ganhos no pedido #{order.public_id}",
        order_id=order.id
    )
    db.add(transaction)

  #  print(f"✅ Concedidos {points_to_award:.2f} pontos ao cliente {order.customer_id} no pedido {order.id}.")
    # O commit será feito pela função que chamou este serviço (handle_update_order_status)


def get_customer_dashboard(db: Session, customer_id: int, store_id: int) -> CustomerLoyaltyDashboardSchema:
    """Monta o dashboard de fidelidade completo para um cliente em uma loja."""
    # 1. Pega o progresso do cliente
    loyalty_progress = db.query(models.CustomerStoreLoyalty).filter_by(customer_id=customer_id,
                                                                       store_id=store_id).first()
    if not loyalty_progress:  # Se o cliente nunca comprou, retorna um dashboard zerado
        return CustomerLoyaltyDashboardSchema(
            store_id=store_id, points_balance=Decimal(0), total_points_earned=Decimal(0),
            rewards_track=[], claimed_rewards_history=[]
        )

    # 2. Pega todos os prêmios ativos da loja
    all_rewards = get_rewards_by_store(db, store_id)

    # 3. Pega os prêmios que o cliente já resgatou
    claimed_rewards = db.query(models.CustomerClaimedReward).filter_by(
        customer_store_loyalty_id=loyalty_progress.id).all()
    claimed_reward_ids = {cr.loyalty_reward_id for cr in claimed_rewards}

    # 4. Monta a "trilha de prêmios"
    rewards_track_list = []
    for reward in all_rewards:
        is_unlocked = loyalty_progress.total_points_earned >= reward.points_threshold
        is_claimed = reward.id in claimed_reward_ids

        rewards_track_list.append(
            LoyaltyRewardStatusSchema(
                id=reward.id,
                name=reward.name,
                description=reward.description,
                points_threshold=reward.points_threshold,
                product=SimpleProductSchema.from_orm(reward.product),
                is_active=reward.is_active,
                is_unlocked=is_unlocked,
                is_claimed=is_claimed
            )
        )

    # 5. Monta o histórico de resgates
    history_list = [ClaimedRewardSchema(
        loyalty_reward_id=cr.loyalty_reward_id,
        reward_name=cr.loyalty_reward.name,  # Assumindo que a relação está carregada ou pode ser acessada
        claimed_at=cr.claimed_at
    ) for cr in claimed_rewards]

    # 6. Monta e retorna o dashboard final
    return CustomerLoyaltyDashboardSchema(
        store_id=store_id,
        points_balance=loyalty_progress.points_balance,
        total_points_earned=loyalty_progress.total_points_earned,
        rewards_track=rewards_track_list,
        claimed_rewards_history=history_list
    )


def claim_reward(db: Session, customer_id: int, store_id: int, reward_id: int) -> models.Coupon:
    """
    Valida e processa o resgate de um prêmio de fidelidade por um cliente.
    """
    # 1. Validações Iniciais
    reward = db.query(models.LoyaltyReward).filter_by(id=reward_id, store_id=store_id, is_active=True).first()
    if not reward:
        raise ValueError("Prêmio não encontrado ou inativo.")

    if not reward.product.is_active:
        raise ValueError("O produto vinculado ao prêmio não está mais disponível.")

    loyalty_progress = db.query(models.CustomerStoreLoyalty).filter_by(customer_id=customer_id,
                                                                       store_id=store_id).first()
    if not loyalty_progress:
        raise ValueError("Você ainda não tem pontos nesta loja.")

    # 2. VALIDAÇÃO DE NEGÓCIO - O cliente já atingiu os pontos necessários?
    if loyalty_progress.total_points_earned < reward.points_threshold:
        raise ValueError("Você ainda não atingiu os pontos necessários para resgatar este prêmio.")

    # 3. VALIDAÇÃO DE SEGURANÇA - O cliente já resgatou este prêmio antes?
    already_claimed = db.query(models.CustomerClaimedReward).filter_by(
        customer_store_loyalty_id=loyalty_progress.id,
        loyalty_reward_id=reward_id
    ).first()
    if already_claimed:
        raise ValueError("Você já resgatou este prêmio anteriormente.")

    # 4. AÇÃO: Se todas as validações passaram, criamos o cupom
    new_coupon = models.Coupon(
        store_id=store_id,
        code=f"PRM-{secrets.token_hex(4).upper()}",  # Gera um código único, ex: PRM-A1B2C3D4
        discount_type='percentage',
        discount_value=100,  # 100% de desconto
        max_uses=1,
        used=0,
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=30),  # Cupom válido por 30 dias
        product_id=reward.product_id  # Cupom válido apenas para o produto do prêmio
    )
    db.add(new_coupon)

    # 5. REGISTRO DE AUDITORIA: Marcamos o prêmio como resgatado
    claimed_record = models.CustomerClaimedReward(
        customer_store_loyalty_id=loyalty_progress.id,
        loyalty_reward_id=reward.id,
        order_id=None  # O order_id será preenchido quando o cupom for usado
    )
    db.add(claimed_record)

    # 6. COMMIT
    db.commit()
    db.refresh(new_coupon)

    return new_coupon