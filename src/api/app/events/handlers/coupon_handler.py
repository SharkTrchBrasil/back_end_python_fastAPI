# Em: app/events/handlers/coupon_handler.py

from datetime import datetime
from pydantic import ValidationError
from sqlalchemy.orm import selectinload

from src.api.admin.utils.coupon_validator import CouponValidator
# --- Importações do Projeto ---
from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio
from src.api.schemas.orders.cart import ApplyCouponInput  # Schema de entrada que já criamos
from src.api.schemas.financial.coupon import CouponOut

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
    print(f"[COUPON] Evento apply_coupon_to_cart recebido: {data}")
    with get_db_manager() as db:
        try:
            input_data = ApplyCouponInput.model_validate(data)
            session = db.query(models.CustomerSession).filter_by(sid=sid).first() # Mudei para CustomerSession
            if not session or not session.customer_id:
                return {'error': 'Usuário não autenticado'}

            # 1. Busca os dados necessários
            coupon = db.query(models.Coupon).options(selectinload(models.Coupon.rules)).filter(
                models.Coupon.code == input_data.coupon_code.upper(),
                models.Coupon.store_id == session.store_id
            ).first()

            if not coupon:
                return {'error': 'Cupom inválido.'}

            cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            customer = db.query(models.Customer).filter_by(id=session.customer_id).first()

            if not cart or not customer:
                return {'error': 'Carrinho ou cliente não encontrado.'}

            # 2. Usa o novo "Motor de Validação"
            validator = CouponValidator(db=db, coupon=coupon, cart=cart, customer=customer)
            if not validator.validate():
                # Retorna a mensagem de erro específica gerada pelo validador
                return {'error': validator.error_message or 'Este cupom não é válido para sua compra.'}

            # 3. Se passou, aplica o cupom ao carrinho
            cart.coupon_id = coupon.id
            cart.coupon_code = coupon.code # Guardar o código facilita a exibição na UI
            db.commit()

            # 4. Retorna o estado completo e atualizado do carrinho
            updated_cart = _get_full_cart_query(db, session.customer_id, session.store_id)
            final_schema = _build_cart_schema(updated_cart) # Você precisará ajustar _build_cart_schema para aplicar o desconto
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