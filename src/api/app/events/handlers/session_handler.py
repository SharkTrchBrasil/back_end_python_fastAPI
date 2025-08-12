# Em: app/events/handlers/session_handler.py (ou totem_namespace.py)

from src.core import models
from src.core.database import get_db_manager
from src.socketio_instance import sio


@sio.event
async def link_customer_to_session(sid, data):
    """
    Associa um ID de cliente (Customer) a uma CustomerSession existente.
    Este evento é a "ponte" entre o login via API REST e a sessão em tempo real.
    """
    print(f"🔗 [SESSÃO] Recebido pedido para vincular cliente à sessão {sid}. Dados: {data}")
    with get_db_manager() as db:
        try:
            # 1. Valida os dados recebidos do Flutter
            customer_id = data.get('customer_id')
            if not customer_id:
                return {'error': 'customer_id ausente.'}

            # 2. Encontra a sessão do cliente no banco de dados pelo SID
            session = db.query(models.CustomerSession).filter_by(sid=sid).first()
            if not session:
                return {'error': 'Sessão em tempo real inválida ou expirada.'}

            # 3. Valida se o cliente realmente existe
            customer = db.query(models.Customer).filter_by(id=customer_id).first()
            if not customer:
                return {'error': 'Cliente com o ID fornecido não encontrado.'}

            # 4. ✅ A MÁGICA: Atualiza o campo `customer_id` na sessão.
            #    A sessão deixa de ser anônima e agora pertence a este cliente.
            session.customer_id = customer.id
            db.commit()

            print(f"✅ [SESSÃO] Sessão {sid} agora está vinculada ao cliente ID {customer.id}")
            return {"success": True}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro em link_customer_to_session: {e}")
            return {"error": "Erro interno ao associar cliente à sessão."}