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
                # Se totem for None aqui, esta linha será printada e a exceção ConnectionRefusedError será lançada
                print(f"ERROR: connect - Authorization failed for token: {token}. Totem not found or not granted, or no associated store.")
                raise ConnectionRefusedError("Invalid or unauthorized token")

            # SE ESTIVERMOS CHEGANDO AQUI, A AUTORIZAÇÃO BÁSICA FUNCIONOU!
            print(f"DEBUG: Totem {totem.id} autorizado com sucesso. Store ID: {totem.store_id}") # <-- Nova linha de depuração crucial

            await update_sid(db, totem, sid)
            room_name = await enter_store_room(sid, totem.store_id)
            print(f"DEBUG: Totem {totem.id} conectado e na sala {room_name}.")

            # ... Resto da lógica de carregamento de dados e emissão ...
            # Verifique se alguma destas seções pode estar lançando uma exceção inesperada
            # que não está sendo capturada ou que está sendo relançada como ConnectionRefusedError.
            # ...
            print("DEBUG: Final do handler connect. Nenhum ConnectionRefusedError lançado.") # <-- Outra linha de depuração
        except ConnectionRefusedError as cre:
            print(f"Connection refused during connect handler: {cre}")
            raise # Re-lança para que o socketio a pegue
        except Exception as e:
            # Esta é a sua "rede de segurança" para outras exceções inesperadas.
            # Se uma exceção ocorrer e não for uma ConnectionRefusedError, ela será capturada aqui.
            print(f"FATAL ERROR in /admin connect handler for SID {sid}: {e}", exc_info=True)
            # A linha abaixo é importante: se você quer que qualquer erro fatal feche a conexão,
            # então re-lança como ConnectionRefusedError. Se não, apenas logue.
            raise ConnectionRefusedError(f"Internal server error during connect: {e}")
