from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from sqlalchemy import func
from decimal import Decimal # Importar Decimal para lidar com precisão monetária

# Importar seus modelos SQLAlchemy
from src.core.models import CashRegister, CashMovement, \
    CashierSession  # Assumindo que CashMovement está no mesmo arquivo ou importável

# Importar seus schemas Pydantic
from src.api.admin.schemas.cash_register import CashRegisterCreate, CashRegisterOut
from src.api.admin.schemas.cash_movement import CashMovementCreate, CashMovementOut # Assumindo que CashMovementOut existe

# Importar suas dependências
from src.core.database import GetDBDep # Dependência para obter a sessão do DB
from src.core.dependencies import GetStoreDep # Dependência para obter a loja (store_id)

# Cria o roteador para as rotas de caixa
router = APIRouter(prefix="/stores/{store_id}/cash-register", tags=["Caixas"])

# --- Rotas para CashRegister ---

# 🔄 Buscar caixa aberto
@router.get("/open", response_model=CashRegisterOut, summary="Obtém o caixa aberto para a loja")
def get_open_cash_register(store: GetStoreDep, db: GetDBDep):
    """
    Retorna o caixa atualmente aberto para a loja especificada.
    Se nenhum caixa estiver aberto, retorna um erro 404.
    Calcula e inclui os totais de entrada e saída de dinheiro.
    """
    cash_register = db.query(CashRegister).filter(
        CashRegister.store_id == store.id,
        CashRegister.closed_at.is_(None)
    ).first()

    if not cash_register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhum caixa aberto para esta loja.")

    # Calcular totais de entrada e saída de CashMovement
    # Usar Decimal para os cálculos para manter a precisão
    total_in_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'in'
    ).scalar() or Decimal('0.00')

    total_out_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'out'
    ).scalar() or Decimal('0.00')

    # Retorna o objeto CashRegisterOut preenchido, incluindo os totais calculados
    # Converte Decimal para float para o Pydantic se CashRegisterOut espera float
    return CashRegisterOut(
        id=cash_register.id,
        store_id=cash_register.store_id,
        opened_at=cash_register.opened_at,
        closed_at=cash_register.closed_at,
        initial_balance=float(cash_register.initial_balance), # Garante float se o schema espera
        current_balance=float(cash_register.current_balance), # Garante float se o schema espera
        is_active=cash_register.is_active,
        created_at=cash_register.created_at,
        updated_at=cash_register.updated_at,
        total_in=float(total_in_query),
        total_out=float(total_out_query),
    )

# 📦 Abrir o caixa
@router.post("/open", response_model=CashRegisterOut, summary="Abre um novo caixa para a loja")
def open_cash_register(data: CashRegisterCreate, store: GetStoreDep, db: GetDBDep):
    """
    Abre um novo caixa para a loja especificada.
    Requer apenas o saldo inicial. O número do caixa será o ID do banco.
    """
    existing_open = db.query(CashRegister).filter(
        CashRegister.store_id == store.id,
        CashRegister.closed_at.is_(None)
    ).first()

    if existing_open:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Já existe um caixa aberto para esta loja.")

    # Cria o objeto CashRegister com os campos essenciais e padrões
    # 'number' será definido após o ID ser gerado pelo banco
    register = CashRegister(
        store_id=store.id,
        opened_at=datetime.utcnow(),
        initial_balance=Decimal(str(data.initial_balance)), # Converte para Decimal para precisão
        current_balance=Decimal(str(data.initial_balance)), # Saldo inicial é igual ao saldo atual
        is_active=True, # Ativo por padrão
    )

    db.add(register)
    db.commit()      # Primeiro commit para gerar o ID do registro
    db.refresh(register) # Refresha para carregar o ID gerado

    # Define o número do caixa como o ID gerado pelo banco e um nome padrão
    # Garanta que seu modelo CashRegister no SQLAlchemy não tem mais as colunas 'number' e 'name'
    # se você não as quer persistidas. Se as tiver, esta parte não seria necessária.
    # Se você removeu as colunas 'number' e 'name' do modelo ORM e schema OUT,
    # esta parte não é necessária e pode ser removida.
    # register.number = register.id # Se 'number' ainda existisse e fosse para ser o ID
    # register.name = "Caixa Principal" # Se 'name' ainda existisse

    # db.add(register) # Re-adiciona para salvar as mudanças de number/name (se aplicável)
    # db.commit()      # Segundo commit para persistir number/name (se aplicável)
    # db.refresh(register) # Segundo refresh para ter o objeto totalmente atualizado (se aplicável)

    # Recalcula totais para a resposta (inicialmente 0)
    total_in_query = Decimal('0.00')
    total_out_query = Decimal('0.00')

    return CashRegisterOut(
        id=register.id,
        store_id=register.store_id,
        opened_at=register.opened_at,
        closed_at=register.closed_at,
        initial_balance=float(register.initial_balance),
        current_balance=float(register.current_balance),
        is_active=register.is_active,
        created_at=register.created_at,
        updated_at=register.updated_at,
        total_in=float(total_in_query),
        total_out=float(total_out_query),
    )

# 🧾 Fechar o caixa
@router.post("/{cash_register_id}/close", response_model=CashRegisterOut, summary="Fecha um caixa existente")
def close_cash_register(cash_register_id: int, store: GetStoreDep, db: GetDBDep):
    """
    Fecha o caixa especificado pelo ID.
    O caixa deve estar aberto e pertencer à loja.
    """
    cash_register = db.query(CashRegister).filter(
        CashRegister.id == cash_register_id,
        CashRegister.store_id == store.id,
        CashRegister.closed_at.is_(None) # Garante que o caixa está aberto
    ).first()

    if not cash_register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caixa não encontrado ou já fechado para esta loja.")

    cash_register.closed_at = datetime.utcnow()
    db.add(cash_register)
    db.commit()
    db.refresh(cash_register)

    # Recalcular totais para a resposta após o fechamento
    total_in_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'in'
    ).scalar() or Decimal('0.00')

    total_out_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'out'
    ).scalar() or Decimal('0.00')

    # 🔢 Totais por meio de pagamento (em transações de sessões desse caixa)
    payment_summary = defaultdict(Decimal)

    sessions = db.query(CashierSession).filter(
        CashierSession.cash_register_id == cash_register.id
    ).all()

    for session in sessions:
        for transaction in session.transactions:
            payment_summary[transaction.payment_method] += Decimal(str(transaction.amount))

    # Converte Decimal para float para retorno via Pydantic
    payment_summary = {k: float(v) for k, v in payment_summary.items()}

    return CashRegisterOut(
        id=cash_register.id,
        store_id=cash_register.store_id,
        opened_at=cash_register.opened_at,
        closed_at=cash_register.closed_at,
        initial_balance=float(cash_register.initial_balance),
        current_balance=float(cash_register.current_balance),
        is_active=cash_register.is_active,
        created_at=cash_register.created_at,
        updated_at=cash_register.updated_at,
        total_in=float(total_in_query),
        total_out=float(total_out_query),
        payment_summary=payment_summary,
    )

# ➕➖ Adicionar movimentação ao caixa
@router.post("/{cash_register_id}/movement", response_model=CashMovementOut, summary="Adiciona uma movimentação (entrada/saída) ao caixa")
def add_cash_movement(
    cash_register_id: int,
    data: CashMovementCreate,
    store: GetStoreDep,
    db: GetDBDep
):
    """
    Registra uma entrada ou saída de dinheiro no caixa especificado.
    Atualiza o saldo atual do caixa.
    """
    cash_register = db.query(CashRegister).filter(
        CashRegister.id == cash_register_id,
        CashRegister.store_id == store.id,
        CashRegister.closed_at.is_(None) # Apenas para caixas abertos
    ).first()

    if not cash_register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caixa não encontrado ou não está aberto.")

    # Converte o float recebido para Decimal ANTES de qualquer operação para manter precisão
    amount_decimal = Decimal(str(data.amount))

    movement = CashMovement(
        register_id=cash_register.id,
        store_id=store.id, # Adicionado store_id ao CashMovement
        amount=amount_decimal,
        type=data.type,
        note=data.note,
        created_at=datetime.utcnow() # created_at é definido no modelo, mas pode ser explicitado
    )

    db.add(movement)

    # Atualiza o saldo atual do caixa
    if data.type == 'in':
        cash_register.current_balance += amount_decimal
    elif data.type == 'out':
        if cash_register.current_balance < amount_decimal:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Saldo insuficiente para esta retirada.")
        cash_register.current_balance -= amount_decimal

    db.add(cash_register) # Adiciona o caixa atualizado
    db.commit()            # Comita as alterações do movimento e do caixa
    db.refresh(movement)   # Refresha o movimento para ter o ID e timestamps
    db.refresh(cash_register) # Refresha o caixa para ter o saldo atualizado

    return movement

# 🔍 Obter um caixa por ID (útil para detalhes ou caixas fechados)
@router.get("/{cash_register_id}", response_model=CashRegisterOut, summary="Obtém detalhes de um caixa por ID")
def get_cash_register_by_id(cash_register_id: int, store: GetStoreDep, db: GetDBDep):
    """
    Retorna os detalhes de um caixa específico pelo seu ID.
    """
    cash_register = db.query(CashRegister).filter(
        CashRegister.id == cash_register_id,
        CashRegister.store_id == store.id
    ).first()

    if not cash_register:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caixa não encontrado para esta loja.")

    # Calcular totais de entrada e saída
    total_in_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'in'
    ).scalar() or Decimal('0.00')

    total_out_query = db.query(func.sum(CashMovement.amount)).filter(
        CashMovement.register_id == cash_register.id,
        CashMovement.type == 'out'
    ).scalar() or Decimal('0.00')

    return CashRegisterOut(
        id=cash_register.id,
        store_id=cash_register.store_id,
        opened_at=cash_register.opened_at,
        closed_at=cash_register.closed_at,
        initial_balance=float(cash_register.initial_balance),
        current_balance=float(cash_register.current_balance),
        is_active=cash_register.is_active,
        created_at=cash_register.created_at,
        updated_at=cash_register.updated_at,
        total_in=float(total_in_query),
        total_out=float(total_out_query),
    )

# 📋 Listar todos os caixas da loja
@router.get("/", response_model=list[CashRegisterOut], summary="Lista todos os caixas da loja")
def list_cash_registers(store: GetStoreDep, db: GetDBDep):
    """
    Retorna uma lista de todos os caixas (abertos e fechados) para a loja especificada.
    Inclui os totais de entrada e saída para cada caixa.
    """
    cash_registers = db.query(CashRegister).filter(
        CashRegister.store_id == store.id
    ).order_by(CashRegister.opened_at.desc()).all()

    response_list = []
    for cash_register in cash_registers:
        total_in_query = db.query(func.sum(CashMovement.amount)).filter(
            CashMovement.register_id == cash_register.id,
            CashMovement.type == 'in'
        ).scalar() or Decimal('0.00')

        total_out_query = db.query(func.sum(CashMovement.amount)).filter(
            CashMovement.register_id == cash_register.id,
            CashMovement.type == 'out'
        ).scalar() or Decimal('0.00')

        response_list.append(CashRegisterOut(
            id=cash_register.id,
            store_id=cash_register.store_id,
            opened_at=cash_register.opened_at,
            closed_at=cash_register.closed_at,
            initial_balance=float(cash_register.initial_balance),
            current_balance=float(cash_register.current_balance),
            is_active=cash_register.is_active,
            created_at=cash_register.created_at,
            updated_at=cash_register.updated_at,
            total_in=float(total_in_query),
            total_out=float(total_out_query),
        ))
    return response_list

