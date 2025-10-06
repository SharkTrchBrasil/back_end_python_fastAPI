import asyncio

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import selectinload  # ✅ Adicionado selectinload

from src.api.admin.socketio.emitters import admin_emit_store_updated
from src.api.app.socketio.socketio_emitters import emit_store_updated
from src.api.schemas.financial.coupon import CouponCreate, CouponUpdate, CouponOut
from src.core import models
from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep

router = APIRouter(tags=["Coupons"], prefix="/stores/{store_id}/coupons")


# ===================================================================
# 1. CRIANDO CUPONS (com regras aninhadas)
# ===================================================================


@router.post("", response_model=CouponOut, status_code=201)
async def create_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon_data: CouponCreate,
):
    existing_coupon = db.query(models.Coupon).filter(
        models.Coupon.code == coupon_data.code.upper(),
        models.Coupon.store_id == store.id,
    ).first()

    if existing_coupon:
        # ✅ Melhoria: Retorna um JSON mais detalhado para o frontend poder tratar o erro
        raise HTTPException(status_code=400, detail={"message": "Um cupom com este código já existe para esta loja.",
                                                     "code": "CODE_ALREADY_EXISTS"})

    # --- INÍCIO DA LÓGICA CORRIGIDA ---

    # 1. Cria o objeto PAI (Coupon) em memória.
    db_coupon = models.Coupon(
        **coupon_data.model_dump(exclude={'rules'}),
        store_id=store.id,
    )

    # 2. Anexa os objetos FILHOS (CouponRule) à lista de relacionamento do PAI.
    #    É esta etapa que garante que o `cascade` funcione.
    for rule_schema in coupon_data.rules:
        new_rule = models.CouponRule(
            rule_type=rule_schema.rule_type,
            value=rule_schema.value
        )
        db_coupon.rules.append(new_rule)

    # 3. Adiciona APENAS o objeto PAI à sessão.
    #    O SQLAlchemy irá automaticamente adicionar os filhos em cascata.
    db.add(db_coupon)

    # 4. Faz o commit da transação. Agora, tanto o cupom quanto suas regras serão salvos.
    db.commit()

    # 5. Atualiza o objeto `db_coupon` com os dados do banco (incluindo os novos IDs).
    db.refresh(db_coupon)

    # --- FIM DA LÓGICA CORRIGIDA ---

    # Emite os eventos de atualização para os clientes conectados
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    # Retorna o objeto `db_coupon` completo, que agora contém as `rules` com seus IDs.
    return db_coupon

# ===================================================================
# 2. BUSCANDO CUPONS (carregando as regras)
# ===================================================================
@router.get("", response_model=list[CouponOut])
def get_coupons(
        db: GetDBDep,
        store: GetStoreDep,
):
    coupons = db.query(models.Coupon).filter(
        models.Coupon.store_id == store.id,
    ).options(
        selectinload(models.Coupon.rules)  # ✅ Carrega a relação de regras
    ).order_by(models.Coupon.id.desc()).all()
    return coupons


@router.get("/{coupon_id}", response_model=CouponOut)
def get_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon_id: int
):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).options(
        selectinload(models.Coupon.rules)  # ✅ Carrega a relação de regras
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


# ===================================================================
# 3. ATUALIZANDO CUPONS (com regras aninhadas)
# ===================================================================
@router.patch("/{coupon_id}", response_model=CouponOut)
async def patch_coupon(
        db: GetDBDep,
        store: GetStoreDep,
        coupon_id: int,
        coupon_update: CouponUpdate,
):
    coupon = db.query(models.Coupon).options(selectinload(models.Coupon.rules)).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id,
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    # ✅ Lógica de atualização aprimorada
    update_data = coupon_update.model_dump(exclude_unset=True)

    # 1. Atualiza os campos simples (code, description, etc.)
    for field, value in update_data.items():
        if field != 'rules':  # Ignora o campo 'rules' por enquanto
            setattr(coupon, field, value)

    # 2. Se a atualização incluiu uma nova lista de regras, substitui as antigas
    if 'rules' in update_data:
        # Remove as regras antigas
        for old_rule in coupon.rules:
            db.delete(old_rule)
        db.flush()  # Aplica a remoção antes de adicionar as novas

        # Adiciona as novas regras
        for rule_schema in coupon_update.rules:
            new_rule = models.CouponRule(
                rule_type=rule_schema.rule_type,
                value=rule_schema.value,
                coupon_id=coupon.id
            )
            db.add(new_rule)

    db.commit()
    db.refresh(coupon)

    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return coupon


# ✅ Rota para deletar um cupom (boa prática ter)
@router.delete("/{coupon_id}", status_code=204)
async def delete_coupon(db: GetDBDep, store: GetStoreDep, coupon_id: int):
    coupon = db.query(models.Coupon).filter(
        models.Coupon.id == coupon_id,
        models.Coupon.store_id == store.id
    ).first()

    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    # Aqui você pode adicionar uma regra de negócio, ex: não deletar se já foi usado
    # if coupon.usages:
    #     raise HTTPException(status_code=400, detail="Cannot delete a coupon that has been used.")

    db.delete(coupon)
    db.commit()
    db.refresh(coupon)
    await asyncio.create_task(emit_store_updated(db, store.id))
    await admin_emit_store_updated(db, store.id)

    return None