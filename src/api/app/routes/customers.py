from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
import base64

from src.api.schemas.customer.customer_totem import (
    CustomerCreate,
    CustomerOut,
    AddressCreate,
    AddressOut, CustomerUpdate,
)
from src.core.database import GetDBDep
from src.core.models import Customer, Address

router = APIRouter(tags=["Customers Info"], prefix="/customer")


@router.post("/google", response_model=CustomerOut)
def customer_login_google(customer_in: CustomerCreate, db: GetDBDep):
    # ✅ CORREÇÃO: Modificamos a consulta para carregar os endereços
    query = select(Customer).options(
        selectinload(Customer.customer_addresses)  # <-- Pede para carregar os endereços junto
    ).filter(Customer.email == customer_in.email)

    result = db.execute(query)
    customer = result.scalars().first()

    if customer:
        customer.name = customer_in.name
       # customer.phone = customer_in.phone
        customer.photo = customer_in.photo
        db.commit()
        db.refresh(customer)
        return customer

    customer = Customer(
        name=customer_in.name,
        email=customer_in.email,
       # phone=customer_in.phone,
        photo=customer_in.photo,
        customer_addresses=[Address(**addr.model_dump()) for addr in customer_in.addresses],
    )
    db.add(customer)
    try:
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email já cadastrado")


@router.post("/{customer_id}/addresses", response_model=AddressOut)
def add_address(customer_id: int, address_in: AddressCreate, db: GetDBDep):
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    address = Address(**address_in.model_dump(), customer_id=customer_id)
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.get("/{customer_id}/addresses", response_model=list[AddressOut])
def get_customer_addresses(customer_id: int, db: GetDBDep):
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    addresses = db.scalars(
        select(Address).where(Address.customer_id == customer_id)
    ).all()

    return addresses



@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
def delete_address(customer_id: int, address_id: int, db: GetDBDep):
    result = db.execute(
        select(Address).where(
            and_(
                Address.id == address_id,
                Address.customer_id == customer_id,
            )
        )
    )
    address = result.scalars().first()

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")

    db.delete(address)
    db.commit()
    return None


@router.patch("/{customer_id}", response_model=CustomerOut)
def update_customer_info(
    customer_id: int,
    customer_update: CustomerUpdate,
    db: GetDBDep
):
    # ✅ CORREÇÃO: Também adicionamos o selectinload aqui
    query = select(Customer).options(
        selectinload(Customer.customer_addresses)
    ).where(Customer.id == customer_id)

    result = db.execute(query)
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    customer.name = customer_update.name
    customer.phone = customer_update.phone
    db.commit()
    db.refresh(customer)

    return customer



@router.put("/{customer_id}/addresses/{address_id}", response_model=AddressOut)
def update_address(
    customer_id: int,
    address_id: int,
    address_in: AddressCreate, # Recebe os dados atualizados do endereço
    db: GetDBDep,
):
    # 1. Verifica se o cliente existe
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    # 2. Busca o endereço específico para o cliente
    # Usamos 'and_' para garantir que o endereço pertence ao cliente certo
    address = db.scalar(
        select(Address).where(
            and_(
                Address.id == address_id,
                Address.customer_id == customer_id,
            )
        )
    )

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado ou não pertence a este cliente")

    # 3. Atualiza os campos do endereço com os dados recebidos
    # Itera sobre os campos do address_in e atualiza o objeto 'address'
    # Use address_in.model_dump() para obter um dicionário dos novos dados
    for field, value in address_in.model_dump(exclude_unset=True).items():
        setattr(address, field, value)

    # O 'exclude_unset=True' é útil se você for usar PATCH,
    # para PUT, você pode remover, pois espera todos os campos.
    # Se AddressCreate representa o estado COMPLETO do endereço,
    # você pode fazer uma atribuição direta para cada campo:
    # address.street = address_in.street
    # address.number = address_in.number
    # address.city = address_in.city
    # address.complement = address_in.complement
    # address.neighborhood_id = address_in.neighborhood_id
    # address.neighborhood = address_in.neighborhood
    # ... e assim por diante para todos os campos relevantes.


    db.add(address) # Adiciona a sessão para marcar como modificada
    db.commit()    # Comita as mudanças no banco de dados
    db.refresh(address) # Atualiza o objeto 'address' com os dados do banco após o commit

    return address




@router.get("/{customer_id}/addresses/{address_id}", response_model=AddressOut)
def get_customer_address(customer_id: int, address_id: int, db: GetDBDep):
    address = db.scalar(
        select(Address).where(
            and_(
                Address.id == address_id,
                Address.customer_id == customer_id
            )
        )
    )
    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")
    return address


@router.get("/{customer_id}/orders", response_model=list)
def get_customer_orders(customer_id: int, db: GetDBDep):
    """Retorna o histórico de pedidos do cliente"""
    from src.core.models import Order, OrderProduct
    from sqlalchemy.orm import selectinload
    
    orders = db.scalars(
        select(Order)
        .options(
            selectinload(Order.products),
            selectinload(Order.store)
        )
        .where(Order.customer_id == customer_id)
        .order_by(Order.created_at.desc())
    ).all()
    
    return [
        {
            "id": order.id,
            "sequential_id": order.sequential_id,
            "public_id": order.public_id,
            "store_id": order.store_id,
            "order_type": order.order_type,
            "delivery_type": order.delivery_type,
            "payment_status": order.payment_status.value if hasattr(order.payment_status, 'value') else str(order.payment_status),
            "order_status": order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status),
            "total_price": order.total_price,
            "subtotal_price": order.subtotal_price,
            "delivery_fee": order.delivery_fee,
            "discount_amount": order.discount_amount,
            "needs_change": order.needs_change,
            "change_amount": order.change_amount,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "charge": None,  # Charge não está disponível no histórico
            "totem_id": order.totem_id,
            "products": [
                {
                    "id": op.id,
                    "name": op.product_name,
                    "quantity": op.quantity,
                    "price": op.total_price,
                    "variants": [],  # Simplificado por enquanto
                }
                for op in order.products
            ],
            "street": order.street,
            "number": order.number,
            "neighborhood": order.neighborhood,
            "city": order.city,
            "complement": order.complement,
            "observation": order.observation,
        }
        for order in orders
    ]


@router.post("/{customer_id}/photo", response_model=CustomerOut)
async def upload_customer_photo(
    customer_id: int,
    db: GetDBDep,
    photo: UploadFile = File(...),
):
    """Endpoint para upload de foto do cliente"""
    query = select(Customer).options(
        selectinload(Customer.customer_addresses)
    ).where(Customer.id == customer_id)

    result = db.execute(query)
    customer = result.scalars().first()

    if not customer:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    
    # Lê o arquivo
    photo_bytes = await photo.read()
    
    # Por enquanto, salva como base64 (temporário)
    # TODO: Em produção, fazer upload para S3/Cloudinary e salvar URL
    photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
    customer.photo = f"data:image/jpeg;base64,{photo_base64}"
    
    db.commit()
    db.refresh(customer)
    return customer
