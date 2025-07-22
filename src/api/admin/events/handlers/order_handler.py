
from urllib.parse import parse_qs

from src.api.shared_schemas.order import OrderStatus
from src.core import models
from src.api.admin.socketio.emitters import (

    admin_emit_order_updated_from_obj, emit_new_order_notification,

)
from src.api.admin.utils.authorize_admin import authorize_admin
from src.core.database import get_db_manager




async def handle_update_order_status(self, sid, data):
    with get_db_manager() as db:
        try:
            if not all(key in data for key in ['order_id', 'new_status']):
                return {'error': 'Dados incompletos'}

            session = db.query(models.StoreSession).filter_by(sid=sid, client_type='admin').first()
            if not session:
                return {'error': 'Sessão não autorizada'}

            query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
            admin_token = query_params.get("admin_token", [None])[0]
            if not admin_token:
                return {"error": "Token de admin não encontrado na sessão."}

            totem_auth_user = await authorize_admin(db, admin_token)
            if not totem_auth_user or not totem_auth_user.id:
                return {"error": "Admin não autorizado."}

            admin_id = totem_auth_user.id

            # Busca todas as lojas às quais o admin tem acesso com a role 'admin'
            all_accessible_store_ids_for_admin = [
                sa.store_id
                for sa in db.query(models.StoreAccess)
                .join(models.Role)
                .filter(
                    models.StoreAccess.user_id == admin_id,
                    models.Role.machine_name == 'admin'
                )
                .all()
            ]

            print(
                f"DEBUG: all_accessible_store_ids para admin {admin_id} (por machine_name): {all_accessible_store_ids_for_admin}")

            # Fallback para adicionar a loja principal do usuário se não estiver nas acessíveis
            if not all_accessible_store_ids_for_admin and totem_auth_user.store_id:
                all_accessible_store_ids_for_admin.append(totem_auth_user.store_id)
                print(
                    f"DEBUG: Adicionada store_id do usuário autenticado como fallback: {totem_auth_user.store_id}")

            order = db.query(models.Order).filter_by(id=data['order_id']).first()

            if not order:
                return {'error': 'Pedido não encontrado.'}

            if order.store_id not in all_accessible_store_ids_for_admin:
                return {'error': 'Acesso negado: Pedido não pertence a uma das suas lojas.'}

            valid_statuses = [  # Usar o Enum diretamente aqui
                OrderStatus.PENDING,
                OrderStatus.PREPARING,
                OrderStatus.READY,
                OrderStatus.ON_ROUTE,
                OrderStatus.DELIVERED,
                OrderStatus.CANCELED,
            ]

            if data['new_status'] not in valid_statuses:
                return {'error': 'Status inválido'}

            old_status = order.order_status  # Salva o status atual antes de mudar

            order.order_status = OrderStatus(data['new_status'])

            # Lógica de baixa de estoque quando o status é 'delivered'
            if data['new_status'] == 'delivered' and old_status != 'delivered':
                for order_product in order.products:
                    product = db.query(models.Product).filter_by(id=order_product.product_id).first()
                    if product and product.control_stock:
                        product.stock_quantity = max(0, product.stock_quantity - order_product.quantity)
                        print(
                            f"Baixado {order_product.quantity} de {product.name}. Novo estoque: {product.stock_quantity}")

            # Lógica de REVERSÃO de estoque, se o pedido for marcado como 'canceled'
            if data['new_status'] == 'canceled' and old_status != 'canceled':
                if old_status in ['ready', 'on_route', 'delivered']:  # Só reverte se já havia sido 'tirado' do estoque
                    for order_product in order.products:
                        product = db.query(models.Product).filter_by(id=order_product.product_id).first()
                        if product and product.control_stock:
                            product.stock_quantity += order_product.quantity
                            print(
                                f"Estoque de {product.name} revertido em {order_product.quantity}. Novo estoque: {product.stock_quantity}")

            db.commit()
            db.refresh(order)


            await admin_emit_order_updated_from_obj(order)


            print(
                f"✅ [Session {sid}] Pedido {order.id} da loja {order.store_id} atualizado para: {data['new_status']}")

            return {'success': True, 'order_id': order.id, 'new_status': order.order_status}

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar pedido: {str(e)}")
            return {'error': 'Falha interna'}