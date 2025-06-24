
from urllib.parse import parse_qs

import socketio
import sqlalchemy
from pydantic import ValidationError
from sqlalchemy.orm import joinedload

from src.api.admin.services.order_code import generate_unique_public_id, gerar_sequencial_do_dia

from src.api.app.schemas.new_order import NewOrder
from src.api.app.schemas.store_details import StoreDetails
from src.api.app.services.check_variants import validate_order_variants
from src.api.app.services.rating import (
    get_store_ratings_summary,
    get_product_ratings_summary,
)
from src.api.shared_schemas.product import ProductOut
from src.api.shared_schemas.rating import RatingsSummaryOut
from src.api.shared_schemas.store_theme import StoreThemeOut

from src.core import models
from src.core.database import get_db_manager

from src.api.app.schemas.order import Order
from src.socketio_instance import sio


async def refresh_product_list(db, store_id: int, sid: str | None = None):
    products_l = db.query(models.Product).options(
        joinedload(models.Product.variant_links)
        .joinedload(models.ProductVariantProduct.variant)
        .joinedload(models.Variant.options)
    ).filter_by(store_id=store_id, available=True).all()

    # Pega avaliações dos produtos
    product_ratings = {
        product.id: get_product_ratings_summary(db, product_id=product.id)
        for product in products_l
    }

    # Junta dados do produto + avaliações
    payload = [
        {
            **ProductOut.from_orm_obj(product).model_dump(exclude_unset=True),
            "rating": product_ratings.get(product.id),
        }
        for product in products_l
    ]

    target = sid if sid else f"store_{store_id}"
    await sio.emit("products_updated", payload, to=target)


# Evento de conexão do Socket.IO
@sio.event
async def connect(sid, environ):
    query = parse_qs(environ.get("QUERY_STRING", ""))
    token = query.get("totem_token", [None])[0]

    if not token:
        raise ConnectionRefusedError("Missing token")

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(
            models.TotemAuthorization.totem_token == token,
            models.TotemAuthorization.granted.is_(True),
        ).first()

        if not totem or not totem.store:
            raise ConnectionRefusedError("Invalid or unauthorized token")

        # Atualiza o SID do totem
        totem.sid = sid
        db.commit()

        room_name = f"store_{totem.store_id}"
        await sio.enter_room(sid, room_name)

        # Carrega dados completos da loja com seus relacionamentos
        # Loja -> delivery_config
        # Loja -> Cidades -> Bairros
        store = db.query(models.Store).options(
            joinedload(models.Store.payment_methods),
            joinedload(models.Store.delivery_config),  # Carrega a configuração de entrega (sem cidades/bairros aqui)
            joinedload(models.Store.hours),
            # Carrega as cidades da loja e, para cada cidade, seus bairros
          #  joinedload(models.Store.cities).joinedload(models.StoreCity.neighborhoods),
        ).filter_by(id=totem.store_id).first()

        if store:
            # Envia dados da loja com avaliações
            try:
                # Converte o objeto SQLAlchemy 'store' para o Pydantic 'StoreDetails'
                store_schema = StoreDetails.model_validate(store)
            except Exception as e:
                print(f"Erro ao validar Store com Pydantic StoreDetails para loja {store.id}: {e}")
                # Isso pode indicar que StoreDetails ou seus aninhados (StoreCity Pydantic, StoreNeighborhood Pydantic)
                # não estão configurados corretamente com model_config = {"from_attributes": True, "arbitrary_types_allowed": True}
                raise ConnectionRefusedError(f"Erro interno do servidor: Dados da loja malformados: {e}")

            store_schema.ratingsSummary = RatingsSummaryOut(
                **get_store_ratings_summary(db, store_id=store.id)
            )
            # Converte o modelo Pydantic para um dicionário serializável para JSON
            store_payload = store_schema.model_dump()
            await sio.emit("store_updated", store_payload, to=sid)

            # Envia tema
            theme = db.query(models.StoreTheme).filter_by(store_id=totem.store_id).first()
            if theme:
                await sio.emit(
                    "theme_updated",
                    StoreThemeOut.model_validate(theme).model_dump(),
                    to=sid,
                )

            # Envia lista de produtos
            await refresh_product_list(db, totem.store_id, sid)

            # Envia os banners da loja
            banners = db.query(models.Banner).filter_by(store_id=totem.store_id).all()
            if banners:
                from src.api.shared_schemas.banner import BannerOut

                banner_payload = [BannerOut.model_validate(b).model_dump() for b in banners]
                await sio.emit("banners_updated", banner_payload, to=sid)


# Evento de desconexão do Socket.IO
@sio.event
async def disconnect(sid, reason):
    print("disconnect", sid, reason)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter_by(sid=sid).first()
        if totem:
            await sio.leave_room(sid, f"store_{totem.store_id}")
            totem.sid = None
            db.commit()

@sio.event
async def send_order(sid, data):
    print('[SOCKET] Evento send_order recebido')
    print('[SOCKET] sid:', sid)
    print('[SOCKET] data:', data)

    with get_db_manager() as db:
        totem = db.query(models.TotemAuthorization).filter(models.TotemAuthorization.sid == sid).first()
        if not totem:
            print(f"[SOCKET] Erro: Totem não encontrado ou não autorizado para sid: {sid}")
            return {'error': 'Totem não encontrado ou não autorizado'}

        try:
            # Tenta validar os dados de entrada usando o modelo Pydantic NewOrder
            new_order = NewOrder(**data)
        except ValidationError as e:
            print(f"[SOCKET] Erro de validação do pedido: {e.errors()}")
            serializable_errors = []
            for error_detail in e.errors():
                temp_error = error_detail.copy()
                # Verifica se há um 'ctx' e 'error' dentro dele
                if 'ctx' in temp_error and isinstance(temp_error['ctx'], dict) and 'error' in temp_error['ctx']:
                    # Se o 'error' for uma instância de ValueError, converte para string
                    if isinstance(temp_error['ctx']['error'], ValueError):
                        temp_error['ctx']['error'] = str(temp_error['ctx']['error'])
                serializable_errors.append(temp_error)
            return {'error': 'Dados do pedido inválidos', 'details': serializable_errors}
        except Exception as e:
            # Captura outros erros inesperados durante a validação inicial do Pydantic
            print(f"[SOCKET] Erro inesperado na validação inicial do Pydantic: {e}")
            return {"success": False, "error": f"Erro inesperado na validação dos dados: {str(e)}"}


        customer = db.query(models.Customer).filter_by(id=new_order.customer_id).first()
        if not customer:
            print(f"[SOCKET] Erro: Cliente com ID {new_order.customer_id} não encontrado.")
            return {'error': 'Cliente não encontrado'}

        address_id_to_use = None

        if new_order.address and new_order.address.id:
            address_id_to_use = new_order.address.id
        elif new_order.delivery_type == 'delivery' and new_order.address:

            print("[SOCKET] Aviso: Pedido de entrega com novo endereço sem ID. Considere salvar/associar o endereço antes.")



        try:
            db_order = models.Order(
                sequential_id=gerar_sequencial_do_dia(db, totem.store_id),
                public_id=generate_unique_public_id(db, totem.store_id),
                store_id=totem.store_id,
                totem_id=totem.id,
                customer_id=new_order.customer_id,
                customer_address_id=address_id_to_use, # Usando o ID do endereço, se disponível
                order_type='cardapio_digital', # Assumindo que este é o tipo fixo para pedidos de totem
                delivery_type=new_order.delivery_type,
                total_price=new_order.total_price, # Agora o total_price vem do new_order validado
                payment_method_id=new_order.payment_method_id,
                payment_status='pendent', # Status inicial
                order_status='pendent',   # Status inicial
                needs_change=new_order.needs_change,
                change_amount=new_order.change_for, # Usando change_for para change_amount
                observation=new_order.observation,
                delivery_fee=new_order.delivery_fee,
            )

            products_from_db = db.query(models.Product).filter(
                models.Product.store_id == totem.store_id,
                models.Product.id.in_([p.product_id for p in new_order.products])
            ).all()

            # Verificação de produtos encontrados
            if len(products_from_db) != len(new_order.products):
                # Isso significa que alguns produtos enviados não foram encontrados no banco de dados da loja
                # Você pode adicionar uma lógica mais detalhada aqui para identificar quais produtos.
                return {'error': 'Um ou mais produtos no pedido não foram encontrados na loja.'}


            # Buscar variantes e opções diretamente para validação
            all_variant_ids = []
            all_option_ids = []
            for p in new_order.products:
                for v in p.variants:
                    all_variant_ids.append(v.variant_id)
                    for o in v.options:
                        all_option_ids.append(o.variant_option_id)

            variants_from_db = db.query(models.Variant).filter(
                models.Variant.id.in_(all_variant_ids)
            ).all()

            variant_options_from_db = db.query(models.VariantOptions).filter(
                models.VariantOptions.id.in_(all_option_ids)
            ).all()

            # Mapeia IDs para objetos para acesso rápido
            products_map = {p.id: p for p in products_from_db}
            variants_map = {v.id: v for v in variants_from_db}
            options_map = {o.id: o for o in variant_options_from_db}


            total_price_calculated_backend = 0

            for order_product_data in new_order.products:
                product_db = products_map.get(order_product_data.product_id)
                if not product_db:
                    return {'error': f"Produto com ID {order_product_data.product_id} não encontrado."}

                # Valida o preço do produto base
                if product_db.base_price != order_product_data.price:
                    return {'error': f"Preço base inválido para o produto {product_db.name}. Esperado: {product_db.base_price}, Recebido: {order_product_data.price}"}

                db_product_entry = models.OrderProduct(
                    store_id=totem.store_id,
                    product_id=product_db.id,
                    name=product_db.name,
                    price=product_db.base_price, # Use o preço do DB para o produto base
                    quantity=order_product_data.quantity,
                    note=order_product_data.note
                )
                db_order.products.append(db_product_entry)

                current_product_total = product_db.base_price * order_product_data.quantity

                for order_variant_data in order_product_data.variants:
                    variant_db = variants_map.get(order_variant_data.variant_id)
                    if not variant_db:
                        return {'error': f"Variante com ID {order_variant_data.variant_id} do produto {product_db.name} não encontrada."}

                    db_variant_entry = models.OrderVariant(
                        order_product=db_product_entry,
                        store_id=totem.store_id,
                        variant_id=variant_db.id,
                        name=variant_db.name,
                    )
                    db_product_entry.variants.append(db_variant_entry)

                    for order_option_data in order_variant_data.options:
                        option_db = options_map.get(order_option_data.variant_option_id)
                        if not option_db:
                            return {'error': f"Opção com ID {order_option_data.variant_option_id} da variante {variant_db.name} do produto {product_db.name} não encontrada."}

                        # Valida o preço da opção
                        if option_db.price != order_option_data.price:
                            return {'error': f"Preço inválido para a opção {option_db.name}. Esperado: {option_db.price}, Recebido: {order_option_data.price}"}

                        db_option_entry = models.OrderVariantOption(
                            order_variant=db_variant_entry,
                            store_id=totem.store_id,
                            variant_option_id=option_db.id,
                            name=option_db.name,
                            price=option_db.price, # Use o preço do DB para a opção
                            quantity=order_option_data.quantity
                        )
                        db_variant_entry.options.append(db_option_entry)
                        current_product_total += (option_db.price * order_option_data.quantity)

                total_price_calculated_backend += current_product_total

            # Adiciona a taxa de entrega ao total calculado no backend
            if new_order.delivery_fee:
                total_price_calculated_backend += new_order.delivery_fee

            # Compara o total calculado no backend com o total enviado pelo frontend
            if new_order.total_price != total_price_calculated_backend:
                print(f"[SOCKET] Erro: Total incorreto. Esperado (backend): {total_price_calculated_backend}, Recebido (frontend): {new_order.total_price}")
                return {
                    'error': f"Total do pedido incorreto. Por favor, recalcule. "
                             f"Esperado: {total_price_calculated_backend}, Recebido: {new_order.total_price}"
                }

            db_order.total_price = total_price_calculated_backend # Define o total_price no objeto do DB com o valor calculado no backend

            db.add(db_order)
            db.commit()

            # Após o commit, garanta que os produtos e variantes do pedido estão carregados para a serialização
            db.refresh(db_order)

            # Valida e converte o objeto de pedido do DB para o formato de saída (Order schema)
            order_dict = Order.model_validate(db_order).model_dump()
            print('[SOCKET] Pedido processado com sucesso e retornado ao cliente')
            return {"success": True, "order": order_dict}

        except sqlalchemy.exc.IntegrityError as e:
            db.rollback()
            print(f"[SOCKET] Erro de integridade ao processar o pedido (possível dado duplicado ou ausente): {e}")
            return {"success": False, "error": "Erro ao salvar o pedido devido a dados inválidos ou duplicados. Tente novamente."}
        except Exception as e:
            db.rollback()
            print(f"[SOCKET] Erro inesperado ao processar o pedido: {e}")
            return {"success": False, "error": f"Erro interno ao processar o pedido: {str(e)}"}

