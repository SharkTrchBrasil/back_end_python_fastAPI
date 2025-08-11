# Correto - Importe datetime corretamente
from datetime import datetime, timezone


from operator import or_


from fastapi.encoders import jsonable_encoder


from src.api.schemas.coupon import CouponOut


from src.core import models

from src.core.database import get_db_manager




from src.socketio_instance import sio



def apply_coupon(coupon, price: float) -> float:
    if coupon.discount_type == 'percentage':
        return round(price * (1 - coupon.discount_value / 100), 2)
    elif coupon.discount_type == 'fixed':
        return max(0, price - coupon.discount_value)
    return price



@sio.event
async def check_coupon(sid, data):
    with get_db_manager() as db:
        try:
            # 1. Verifica a sessão ativa
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            # 2. Validação básica do input
            if not data or not isinstance(data, str):
                return {'error': 'Código do cupom inválido'}

            # 3. Busca o cupom vinculado à LOJA da sessão
            coupon = db.query(models.Coupon).filter(
                models.Coupon.code == data.strip(),
                models.Coupon.store_id == session.store_id
            ).first()

            # 4. Validações do cupom
            if not coupon:
                return {'error': 'Cupom não encontrado'}

            now = datetime.now(timezone.utc)

            if coupon.used >= coupon.max_uses:
                return {'error': 'Cupom já utilizado'}

            if coupon.start_date and now < coupon.start_date:
                return {'error': 'Cupom ainda não disponível'}

            if coupon.end_date and now > coupon.end_date:
                return {'error': 'Cupom expirado'}

            # 5. Retorna o cupom válido
            return jsonable_encoder(CouponOut.model_validate(coupon))

        except Exception as e:
            print(f"❌ Erro ao verificar cupom: {str(e)}")
            return {'error': 'Erro interno ao processar cupom'}


@sio.event
async def list_coupons(sid):
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            now = datetime.utcnow()

            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == session.store_id,
                models.Coupon.used < models.Coupon.max_uses,
                or_(
                    models.Coupon.start_date == None,
                    models.Coupon.start_date <= now
                ),
                or_(
                    models.Coupon.end_date == None,
                    models.Coupon.end_date >= now
                )
            ).all()

            return {
                'coupons': [
                    CouponOut.model_validate(c).model_dump(mode="json")
                    for c in coupons
                ]
            }

        except Exception as e:
            print(f"❌ Erro ao listar cupons: {str(e)}")
            return {'error': 'Erro interno ao listar cupons'}
