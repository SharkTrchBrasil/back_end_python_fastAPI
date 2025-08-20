from sqlalchemy import select, delete, func
from urllib.parse import parse_qs

from sqlalchemy.orm import selectinload


from src.api.admin.services.store_access_service import StoreAccessService
from src.api.admin.services.store_session_service import SessionService
from src.api.admin.utils.authorize_admin import authorize_admin_by_jwt
from src.api.schemas.store_operation_config import StoreOperationConfigBase
from src.core import models
from src.api.admin.socketio.emitters import (
    admin_emit_store_full_updated,
)
from src.core.database import get_db_manager


async def handle_set_consolidated_stores(self, sid, data):
    """
    Atualiza as PREFERÊNCIAS de lojas consolidadas de um admin no banco de dados.
    """
    try:
        selected_store_ids = set(data.get("store_ids", []))
        if not isinstance(data.get("store_ids"), list):
            return {"error": "'store_ids' deve ser uma lista"}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid)

            if not session or not session.user_id:
                return {"error": "Sessão não autorizada"}

            admin_id = session.user_id

            db.execute(
                delete(models.AdminConsolidatedStoreSelection).where(
                    models.AdminConsolidatedStoreSelection.admin_id == admin_id
                )
            )

            for store_id in selected_store_ids:
                new_selection = models.AdminConsolidatedStoreSelection(
                    admin_id=admin_id, store_id=store_id
                )
                db.add(new_selection)

            db.commit()

            print(f"✅ Preferências de consolidação do admin {admin_id} atualizadas para: {selected_store_ids}")

            await self.emit(
                "consolidated_stores_updated",
                {"store_ids": list(selected_store_ids)},
                to=sid,
            )

            return {"success": True, "selected_stores": list(selected_store_ids)}

    except Exception as e:
        if 'db' in locals() and db.is_active:
            db.rollback()
        print(f"❌ Erro em on_set_consolidated_stores: {str(e)}")
        return {"error": f"Falha interna: {str(e)}"}


async def handle_update_operation_config(self, sid, data):
    with get_db_manager() as db:
        session = SessionService.get_session(db, sid, client_type="admin")

        if not session:
            return {'error': 'Sessão não encontrada ou não autorizada'}

        requested_store_id = data.get("store_id")
        if not requested_store_id:
            return {'error': 'ID da loja é obrigatório para atualizar configurações.'}

        query_params = parse_qs(self.environ[sid].get("QUERY_STRING", ""))
        admin_token = query_params.get("admin_token", [None])[0]
        if not admin_token:
            return {"error": "Token de admin não encontrado na sessão."}

        # ✅ CORREÇÃO 1: Renomeado para clareza.
        admin_user = await authorize_admin_by_jwt(db, admin_token)
        if not admin_user or not admin_user.id:
            return {"error": "Admin não autorizado."}

        # A fonte de verdade para as lojas acessíveis.
        all_accessible_store_ids_for_admin = StoreAccessService.get_accessible_store_ids_with_fallback(db,
                                                                                                       admin_user)

        if requested_store_id not in all_accessible_store_ids_for_admin:
            return {'error': 'Acesso negado: Você não tem permissão para gerenciar esta loja.'}

        store = db.query(models.Store).filter_by(id=requested_store_id).first()
        if not store:
            return {"error": "Loja não encontrada."}

        # --- ✅ 2. LÓGICA ATUALIZADA PARA USAR 'StoreOperationConfig' ---
        config = db.query(models.StoreOperationConfig).filter_by(store_id=store.id).first()

        # Se não houver configuração, cria uma padrão em vez de retornar erro
        if not config:
            config = models.StoreOperationConfig(store_id=store.id)
            db.add(config)

        try:
            # ✅ CORREÇÃO: Lista explícita de campos atualizáveis.
            # Isso evita o erro no editor e torna a intenção do código mais clara.
            updatable_fields = [
                "is_store_open", "auto_accept_orders", "auto_print_orders",
                "main_printer_destination", "kitchen_printer_destination", "bar_printer_destination",
                "delivery_enabled", "delivery_estimated_min", "delivery_estimated_max",
                "delivery_fee", "delivery_min_order", "delivery_scope",
                "pickup_enabled", "pickup_estimated_min", "pickup_estimated_max",
                "pickup_instructions",
                "table_enabled", "table_estimated_min", "table_estimated_max",
                "table_instructions"
            ]

            for field in updatable_fields:
                if field in data:
                    setattr(config, field, data[field])

            db.commit()
            db.refresh(config)
            db.refresh(store)

            await admin_emit_store_full_updated(db, store.id)

            return StoreOperationConfigBase.model_validate(config).model_dump(mode='json')

        except Exception as e:
            db.rollback()
            print(f"❌ Erro ao atualizar configuração de operação da loja: {str(e)}")
            return {"error": str(e)}


async def handle_join_store_room(self, sid, data):
    """
    Inscreve um admin na sala de uma loja específica para receber dados detalhados.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            if session.store_id and session.store_id != store_id:
                old_room = f"admin_store_{session.store_id}"
                await self.leave_room(sid, old_room)
                print(f"🚪 [join_store_room] Admin {sid} saiu da sala antiga: {old_room}")

            new_room = f"admin_store_{store_id}"
            await self.enter_room(sid, new_room)
            print(f"✅ [join_store_room] Admin {sid} entrou na sala dinâmica: {new_room}")

            SessionService.update_session_store(db, sid=sid, store_id=store_id)

            await self._emit_initial_data(db, store_id, sid)

            return {'status': 'success', 'joined_room': new_room}

    except Exception as e:
        print(f"❌ [join_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}


async def handle_leave_store_room(self, sid, data):
    """
    Remove um admin da sala de uma loja específica.
    """
    try:
        store_id = data.get("store_id")
        if not store_id:
            return {'status': 'error', 'message': 'store_id é obrigatório'}

        with get_db_manager() as db:
            session = SessionService.get_session(db, sid, client_type="admin")

            if not session:
                return {'status': 'error', 'message': 'Sessão inválida.'}

            if session.store_id == store_id:
                room = f"admin_store_{store_id}"
                await self.leave_room(sid, room)
                print(f"🚪 [leave_store_room] Admin {sid} saiu da sala: {room}")
                return {'status': 'success', 'left_room': room}
            else:
                print(f"⚠️ [leave_store_room] Admin {sid} tentou sair da loja {store_id}, mas a loja ativa era {session.store_id}.")
                return {'status': 'error', 'message': 'Inconsistência de estado da loja.'}

    except Exception as e:
        print(f"❌ [leave_store_room] Erro ao processar para a loja {data.get('store_id')}: {e}")
        return {'status': 'error', 'message': 'Erro interno do servidor.'}


# ✅ HANDLER CORRIGIDO E ALINHADO COM SEUS MODELOS
async def handle_register_device(self, sid, data):
    """
    Handler para quando um dispositivo cliente tenta se registrar via socket.
    Valida se a conexão é permitida com base no limite de dispositivos do plano ativo da loja.
    """
    print(f"Recebida tentativa de registro do dispositivo para dados: {data}")

    try:
        store_id = data.get('storeId')
        device_id = data.get('deviceId')

        if not store_id or not device_id:
            print(f"[{sid}] Erro: storeId ou deviceId ausente no payload.")
            await self.emit('registration_failed', {'error': 'Dados inválidos.'}, to=sid)
            return {"error": "Dados inválidos."}

        with get_db_manager() as db:
            # --- 1. Obter a loja e sua assinatura ativa de forma otimizada ---
            # Usamos selectinload para carregar os relacionamentos necessários em uma única consulta
            # e evitar o problema N+1.
            stmt = (
                select(models.Store)
                .options(
                    selectinload(models.Store.subscriptions)
                    .selectinload(models.StoreSubscription.plan)
                )
                .where(models.Store.id == store_id)
            )
            store = db.execute(stmt).scalar_one_or_none()

            if not store:
                print(f"[{sid}] Erro: Loja não encontrada para o store_id: {store_id}.")
                await self.emit('registration_failed', {'error': 'Loja não encontrada.'}, to=sid)
                return {"error": "Loja não encontrada."}

            # --- 2. Obter o limite de dispositivos usando sua hybrid_property ---
            active_sub = store.active_subscription

            if not active_sub or not active_sub.plan:
                print(f"[{sid}] Erro: Assinatura ativa ou plano não encontrado para a loja {store_id}.")
                await self.emit('registration_failed', {'error': 'Assinatura inválida.'}, to=sid)
                return {"error": "Assinatura inválida."}

            # Usamos o nome do campo do seu modelo `Plans`: max_active_devices
            # Usamos 'or 1' como um fallback seguro caso o valor seja None.
            device_limit = active_sub.plan.max_active_devices or 1

            # --- 3. Contar os dispositivos atualmente ativos para a loja ---
            active_devices_count = db.query(func.count(models.ActiveSession.id)).filter(
                models.ActiveSession.store_id == store_id
            ).scalar()

            # --- 4. Aplicar a lógica de validação ---
            this_device_session = db.query(models.ActiveSession).filter_by(
                store_id=store_id, device_id=device_id
            ).first()

            is_new_device_session = this_device_session is None

            if is_new_device_session and active_devices_count >= device_limit:
                print(
                    f"[{sid}] ACESSO NEGADO para device_id {device_id}. Limite de {device_limit} dispositivos atingido.")
                await self.emit('device_limit_reached', {
                    'message': f'O plano atual suporta apenas {device_limit} dispositivo(s) conectado(s).'}, to=sid
                                )
                return {"error": "Limite de dispositivos atingido."}

            # --- 5. Acesso Permitido: Atualizar a sessão com o socket_id ---
            if not this_device_session:
                # Idealmente, a sessão HTTP já deveria ter sido criada no login.
                # Se este log aparecer com frequência, revise o fluxo de login do app.
                print(
                    f"[{sid}] Aviso: Sessão não encontrada para device_id {device_id}. Verifique o fluxo de login HTTP.")
                return {"error": "Sessão de dispositivo não iniciada. Faça login primeiro."}

            this_device_session.socket_id = sid
            db.commit()

            print(f"[{sid}] ACESSO PERMITIDO para device_id {device_id}. Sessão atualizada com socket_id.")

            # --- 6. Emitir evento de sucesso ---
            await self.emit('registration_successful', {'message': 'Dispositivo conectado e autenticado.'}, to=sid)
            return {"success": True}

    except Exception as e:
        print(f"❌ Erro em handle_register_device: {str(e)}")
        await self.emit('registration_failed', {'error': 'Erro interno no servidor.'}, to=sid)
        return {"error": f"Falha interna: {str(e)}"}


async def check_and_update_setup_status(store_id: int):
    """
    Verifica se a loja completou as tarefas essenciais de configuração.
    Esta função gerencia sua própria sessão de banco de dados.
    """
    # ✅ Usa o mesmo padrão de gerenciamento de sessão das outras funções
    with get_db_manager() as db:
        try:
            # Busca a loja para verificar o status atual e o endereço
            store = db.query(models.Store).filter(models.Store.id == store_id).first()
            if not store:
                print(f"❌ Loja {store_id} não encontrada em check_and_update_setup_status.")
                return

            # Se o setup já foi completado, não faz mais nada
            if store.is_setup_complete:
                return

            # ✅ REGRAS DE VERIFICAÇÃO OTIMIZADAS (Consultas mais leves)

            # 1. Verifica se há pelo menos um horário de funcionamento.
            has_configured_hours = db.query(models.StoreHour).filter(
                models.StoreHour.store_id == store_id).first() is not None

            # 2. Verifica se pelo menos um método de pagamento foi ativado.
            has_activated_payment = db.query(models.StorePaymentMethodActivation).filter(
                models.StorePaymentMethodActivation.store_id == store_id,
                models.StorePaymentMethodActivation.is_active == True
            ).first() is not None

            # 3. Verifica se pelo menos um produto foi adicionado.
            has_added_product = db.query(models.Product).filter(models.Product.store_id == store_id).first() is not None

            # 4. Verifica se o endereço principal da loja foi preenchido.
            has_set_address = store.street is not None and store.neighborhood is not None

            # 5. Verifica se pelo menos uma área de entrega foi configurada.
            # Para esta checagem aninhada, carregar o relacionamento ainda é a forma mais limpa.
            store_with_cities = db.query(models.Store).options(
                selectinload(models.Store.cities).selectinload(models.StoreCity.neighborhoods)
            ).filter(models.Store.id == store_id).first()
            has_configured_delivery_area = len(store_with_cities.cities) > 0 and any(
                len(city.neighborhoods) > 0 for city in store_with_cities.cities)

            # Verifica se TODAS as condições são verdadeiras
            if all([has_configured_hours, has_activated_payment, has_added_product, has_set_address,
                    has_configured_delivery_area]):
                print(f"🎉 Loja {store.id} completou todas as tarefas de setup! Liberando o painel completo.")
                store.is_setup_complete = True
                db.commit()

                # Emite o evento para notificar o frontend que o status da loja mudou
                await admin_emit_store_full_updated(db, store.id)

        except Exception as e:
            # O 'with get_db_manager()' já cuida do rollback em caso de erro.
            print(f"❌ Erro em check_and_update_setup_status para a loja {store_id}: {e}")