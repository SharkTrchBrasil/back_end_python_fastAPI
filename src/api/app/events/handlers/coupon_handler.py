# Em: app/events/handlers/coupon_handler.py

from datetime import datetime, timezone
from operator import or_
from pydantic import ValidationError

# --- Importações do Projeto ---
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.schemas.cart import ApplyCouponInput  # Schema de entrada que já criamos
from src.api.schemas.coupon import CouponOut

# ✅ 1. REUTILIZAÇÃO DE CÓDIGO: Importamos as funções auxiliares do cart_handler.
#    Isso evita código duplicado e mantém a lógica centralizada.
from .cart_handler import _get_full_cart_query, _build_cart_schema


@sio.event
async def list_coupons(sid):
    """
    Lista todos os cupons válidos e disponíveis para o usuário.
    (Esta função permanece a mesma, pois já estava correta).
    """
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.store_id:
                return {'error': 'Sessão não autorizada'}

            now = datetime.utcnow()
            # Usamos a propriedade .is_valid que criamos no modelo para simplificar a query
            coupons = db.query(models.Coupon).filter(
                models.Coupon.store_id == session.store_id,
                models.Coupon.is_valid == True  # Filtra usando nossa propriedade inteligente
            ).all()

            return {
                'coupons': [CouponOut.model_validate(c).model_dump(mode="json") for c in coupons]
            }
        except Exception as e:
            print(f"❌ Erro ao listar cupons: {str(e)}")
            return {'error': 'Erro interno ao listar cupons'}


@sio.event
async def apply_coupon_to_cart(sid, data):
    """
    Ação principal: Valida um cupom e o aplica ao carrinho ativo do usuário.
    Substitui a necessidade do antigo 'check_coupon'.
    """
    print(f"[COUPON] Evento apply_coupon_to_cart recebido: {data}")
    with get_db_manager() as db:
        try:
            input_data = ApplyCouponInput.model_validate(data)
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.customer_id:
                return {'error': 'Usuário não autenticado'}

            # 1. Valida o cupom usando a propriedade .is_valid
            coupon = db.query(models.Coupon).filter(
                models.Coupon.code == input_data.coupon_code.upper(),
                models.Coupon.store_id == session.store_id
            ).first()

            if not coupon or not coupon.is_valid:
                return {'error': 'Cupom inválido, expirado ou esgotado.'}

            # 2. Pega o carrinho ativo do usuário (reutilizando nossa função)
            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            if not cart:
                return {'error': 'Carrinho não encontrado para aplicar o cupom.'}

            # 3. Aplica o cupom ao carrinho no banco de dados
            cart.coupon = coupon
            db.commit()

            # 4. Retorna o estado completo e atualizado do carrinho
            updated_cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            final_schema = _build_cart_schema(updated_cart)
            return {"success": True, "cart": final_schema.model_dump(mode="json")}

        except ValidationError as e:
            return {'error': 'Código do cupom inválido', 'details': e.errors()}
        except Exception as e:
            db.rollback()
            print(f"❌ Erro em apply_coupon_to_cart: {e}")
            return {"error": "Erro interno ao aplicar cupom."}


@sio.event
async def remove_coupon_from_cart(sid, data=None):
    """
    Remove qualquer cupom aplicado ao carrinho ativo do usuário.
    """
    print(f"[COUPON] Evento remove_coupon_from_cart recebido")
    with get_db_manager() as db:
        try:
            session = db.query(models.StoreSession).filter_by(sid=sid).first()
            if not session or not session.customer_id:
                return {'error': 'Usuário não autenticado'}

            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            if cart:
                cart.coupon_id = None
                cart.coupon_code = None
                db.commit()

            updated_cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            final_schema = _build_cart_schema(updated_cart)
            return {"success": True, "cart": final_schema.model_dump(mode="json")}
        except Exception as e:
            db.rollback()
            print(f"❌ Erro em remove_coupon_from_cart: {e}")
            return {"error": "Erro interno ao remover cupom."}

# O evento 'check_coupon' não é mais necessário, pois 'apply_coupon_to_cart'
# já faz a validação e a aplicação em um único passo. Você pode removê-lo.
# @sio.event
# async def check_coupon(sid, data):
#     ...