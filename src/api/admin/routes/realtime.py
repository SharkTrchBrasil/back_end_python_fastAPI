# Seu arquivo: src/socketio_instance.py
from src.api.admin.schemas.order import Order
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.rating import get_store_ratings_summary
from src.core import models # Certifique-se de importar seus modelos
from src.core.database import get_db_manager # Supondo que você tem um get_db_manager



from sqlalchemy.orm import joinedload
from urllib.parse import parse_qs

from src.socketio_instance import sio


# Assumindo que refresh_product_list está definida em algum lugar
async def refresh_product_list(db, store_id, sid):
    # Sua lógica existente para buscar e emitir produtos
    pass # Placeholder, substitua pela sua implementação real

# Funções auxiliares (authorize_totem, update_sid, enter_store_room)
# Certifique-se que elas estão definidas no mesmo arquivo ou importadas corretamente
async def authorize_totem(db, token: str):
    totem = db.query(models.TotemAuthorization).filter(
        models.TotemAuthorization.totem_token == token,
        models.TotemAuthorization.granted.is_(True),
    ).first()
    # Adicione mais depuração aqui dentro da função
    if totem:
        print(f"DEBUG: authorize_totem - Totem encontrado (ID: {totem.id}, StoreID: {totem.store_id})")
        if not totem.store:
            print(f"DEBUG: authorize_totem - Totem encontrado, mas SEM loja associada ou loja não existe!")
            return None
        print(f"DEBUG: authorize_totem - Totem e Loja OK. Loja ID: {totem.store.id}")
        return totem
    else:
        print(f"DEBUG: authorize_totem - Nenhum Totem encontrado para o token: {token} ou granted=False.")
        return None

async def update_sid(db, totem, sid: str):
    print(f"DEBUG: update_sid - Atualizando SID para totem {totem.id} de {totem.sid} para {sid}")
    totem.sid = sid
    db.commit()
    print(f"DEBUG: update_sid - SID atualizado com sucesso.")

async def enter_store_room(sid: str, store_id: int):
    room_name = f"store_{store_id}"
    print(f"DEBUG: enter_store_room - Entrando SID {sid} na sala {room_name}")
    await sio.enter_room(sid, room_name)
    print(f"DEBUG: enter_store_room - SID {sid} entrou na sala {room_name}.")
    return room_name

# O seu evento de conexão Socket.IO
@sio.event(namespace="/admin")
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]
    print(f"🔥 ADMIN socket connect: SID={sid}, Query={environ.get('QUERY_STRING')}")

    if not token:
        print("ERROR: connect - Missing totem_token in query string.")
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        try:
            totem = await authorize_totem(db, token)
            if not totem:
                print(f"ERROR: connect - Authorization failed for token: {token}. Totem not found or not granted, or no associated store.")
                raise ConnectionRefusedError("Invalid or unauthorized token")

            # Se chegamos aqui, o totem foi autorizado com sucesso
            await update_sid(db, totem, sid) # Atualiza o SID no banco
            room_name = await enter_store_room(sid, totem.store_id)
            print(f"DEBUG: Totem {totem.id} conectado e na sala {room_name}.")

            # Carrega dados completos da loja com seus relacionamentos
            # Use o totem.store que já veio carregado, ou carregue novamente se lazy="select"
            # Se relationship("Store", lazy="joined") no TotemAuthorization, totem.store já deve estar preenchido
            store = db.query(models.Store).options(
                joinedload(models.Store.payment_methods),
                joinedload(models.Store.delivery_config),
                joinedload(models.Store.hours),
                joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
            ).filter_by(id=totem.store_id).first() # Use totem.store_id para garantir a loja correta

            if store:
                print(f"DEBUG: Enviando dados da loja {store.id}...")
                try:
                    store_schema = StoreDetails.model_validate(store)

                    store_payload = store_schema.model_dump()
                    await sio.emit("store_updated", store_payload, to=sid)
                    print("DEBUG: store_updated enviado.")
                except Exception as e:
                    print(f"ERROR: Erro ao validar/enviar Store para loja {store.id}: {e}")
                    # Não lance ConnectionRefusedError aqui, o totem já se conectou.
                    # Mas isso pode ser um problema de dados, logue e siga.

                # Envia tema
                theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
                if theme:
                    from src.api.shared_schemas.store_theme import StoreThemeOut # Verifique o caminho correto
                    await sio.emit(
                        "theme_updated",
                        StoreThemeOut.model_validate(theme).model_dump(),
                        to=sid,
                    )
                    print("DEBUG: theme_updated enviado.")

                # Envia lista de produtos
                print("DEBUG: Chamando refresh_product_list...")
                await refresh_product_list(db, totem.store_id, sid)
                print("DEBUG: refresh_product_list concluído.")

                # Envia os banners da loja
                banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
                if banners:
                    from src.api.shared_schemas.banner import BannerOut
                    banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                    await sio.emit("banners_updated", banner_payload, to=sid)
                    print("DEBUG: banners_updated enviado.")
                else:
                    print("DEBUG: Nenhuns banners encontrados para esta loja.")

                # Envia orders_initial
                orders = db.query(models.Order).filter_by(store_id=totem.store_id).order_by(models.Order.created_at.desc()).limit(20).all()
                if orders:
                    # Certifique-se que Order é o schema Pydantic correto para Orders
                    order_payload = [Order.model_validate(o).model_dump() for o in orders]
                    await sio.emit("orders_initial", order_payload, to=sid)
                    print(f"DEBUG: orders_initial enviado com {len(orders)} pedidos.")
                else:
                    print("DEBUG: Nenhum pedido encontrado para esta loja.")
            else:
                print(f"ERROR: Loja {totem.store_id} não encontrada para o totem {totem.id} após autorização.")

        except ConnectionRefusedError as cre:
            print(f"Connection refused during connect handler: {cre}")
            # Esta exceção será capturada pelo python-socketio e resultará em "Unable to connect"
            raise # Re-lança para que o socketio a pegue
        except Exception as e:
            print(f"FATAL ERROR in /admin connect handler for SID {sid}: {e}", exc_info=True)
            # Logue outras exceções inesperadas para depuração
            # Não é recomendado levantar ConnectionRefusedError para erros que não sejam de autenticação inicial
            # Mas para um erro fatal que impeça o funcionamento, pode-se forçar a desconexão
            raise ConnectionRefusedError(f"Internal server error during connect: {e}")