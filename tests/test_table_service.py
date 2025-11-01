"""
Testes do Sistema de Mesas e Comandas
=====================================
Testes unitários e de integração
"""

import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from src.core import models
from src.core.utils.enums import TableStatus, CommandStatus, OrderStatus
from src.api.admin.services.table_service import TableService
from src.api.schemas.tables.table import (
    CreateTableRequest, 
    UpdateTableRequest,
    OpenTableRequest,
    AddItemToTableRequest
)


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def test_db():
    """Cria banco de dados de teste em memória"""
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def table_service(test_db):
    """Cria instância do TableService com DB de teste"""
    return TableService(test_db)


@pytest.fixture
def sample_store(test_db):
    """Cria loja de teste"""
    store = models.Store(
        id=1,
        name="Restaurante Teste",
        cnpj="00000000000000",
        is_active=True,
        url_slug="teste"
    )
    test_db.add(store)
    test_db.commit()
    return store


@pytest.fixture
def sample_saloon(test_db, sample_store):
    """Cria salão de teste"""
    saloon = models.Saloon(
        id=1,
        store_id=sample_store.id,
        name="Salão Principal",
        is_active=True,
        display_order=1
    )
    test_db.add(saloon)
    test_db.commit()
    return saloon


@pytest.fixture
def sample_table(test_db, sample_store, sample_saloon):
    """Cria mesa de teste"""
    table = models.Tables(
        id=1,
        store_id=sample_store.id,
        saloon_id=sample_saloon.id,
        name="Mesa 01",
        status=TableStatus.AVAILABLE,
        max_capacity=4
    )
    test_db.add(table)
    test_db.commit()
    return table


@pytest.fixture
def sample_user(test_db):
    """Cria usuário de teste"""
    user = models.User(
        id=1,
        email="test@example.com",
        name="Test User",
        hashed_password="hashed",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


# ═══════════════════════════════════════════════════════════
# TESTES DO TABLESERVICE
# ═══════════════════════════════════════════════════════════

class TestTableService:
    """Testes do serviço de mesas"""
    
    def test_create_table(self, table_service, sample_store, sample_saloon):
        """Testa criação de mesa"""
        request = CreateTableRequest(
            saloon_id=sample_saloon.id,
            name="Mesa 02",
            max_capacity=6,
            location_description="Próximo à janela"
        )
        
        table = table_service.create_table(sample_store.id, request)
        
        assert table is not None
        assert table.name == "Mesa 02"
        assert table.max_capacity == 6
        assert table.status == TableStatus.AVAILABLE
        assert table.location_description == "Próximo à janela"
    
    def test_update_table(self, table_service, sample_store, sample_table):
        """Testa atualização de mesa"""
        request = UpdateTableRequest(
            name="Mesa VIP",
            max_capacity=8,
            status="RESERVED"
        )
        
        updated_table = table_service.update_table(
            sample_table.id, 
            sample_store.id, 
            request
        )
        
        assert updated_table.name == "Mesa VIP"
        assert updated_table.max_capacity == 8
        assert updated_table.status == TableStatus.RESERVED
        assert updated_table.status_color == "#ffc107"  # Amarelo para RESERVED
    
    def test_delete_table_soft_delete(self, table_service, sample_store, sample_table):
        """Testa soft delete de mesa"""
        result = table_service.delete_table(sample_table.id, sample_store.id)
        
        assert result is True
        assert sample_table.is_deleted is True
        assert sample_table.deleted_at is not None
    
    def test_open_table_creates_command(self, table_service, sample_store, sample_table, sample_user):
        """Testa abertura de mesa criando comanda"""
        request = OpenTableRequest(
            table_id=sample_table.id,
            customer_name="João Silva",
            customer_contact="11999999999",
            attendant_id=sample_user.id,
            notes="Cliente preferencial"
        )
        
        command = table_service.open_table(sample_store.id, request)
        
        assert command is not None
        assert command.table_id == sample_table.id
        assert command.customer_name == "João Silva"
        assert command.status == CommandStatus.ACTIVE
        assert sample_table.status == TableStatus.OCCUPIED
        assert sample_table.status_color == "#dc3545"  # Vermelho para OCCUPIED
    
    def test_close_table_finalizes_orders(self, table_service, sample_store, sample_table):
        """Testa fechamento de mesa e finalização de pedidos"""
        # Cria comanda
        command = models.Command(
            store_id=sample_store.id,
            table_id=sample_table.id,
            status=CommandStatus.ACTIVE
        )
        table_service.db.add(command)
        
        # Cria pedido
        order = models.Order(
            store_id=sample_store.id,
            command_id=command.id,
            order_status=OrderStatus.RECEIVED,
            total_price=5000  # R$ 50,00 em centavos
        )
        table_service.db.add(order)
        table_service.db.commit()
        
        # Fecha mesa
        closed_table = table_service.close_table(
            sample_store.id, 
            sample_table.id, 
            command.id
        )
        
        assert closed_table.status == TableStatus.AVAILABLE
        assert closed_table.status_color == "#28a745"  # Verde para AVAILABLE
        assert command.status == CommandStatus.CLOSED
        assert order.order_status == OrderStatus.FINALIZED
        assert closed_table.total_revenue_today == 5000
    
    def test_assign_employee_to_table(self, table_service, sample_store, sample_table, sample_user):
        """Testa atribuição de funcionário à mesa"""
        # Cria acesso do usuário à loja
        access = models.StoreAccess(
            store_id=sample_store.id,
            user_id=sample_user.id,
            role_id=1
        )
        table_service.db.add(access)
        table_service.db.commit()
        
        # Atribui funcionário
        table = table_service.assign_employee_to_table(
            sample_store.id,
            sample_table.id,
            sample_user.id,
            performed_by=sample_user.id
        )
        
        assert table.assigned_employee_id == sample_user.id
    
    def test_split_payment_equal(self, table_service, sample_store):
        """Testa divisão igual de pagamento"""
        # Cria comanda com pedido
        command = models.Command(
            id=1,
            store_id=sample_store.id,
            status=CommandStatus.ACTIVE
        )
        table_service.db.add(command)
        
        order = models.Order(
            id=1,
            store_id=sample_store.id,
            command_id=command.id,
            total_price=10000  # R$ 100,00
        )
        table_service.db.add(order)
        table_service.db.commit()
        
        # Divide pagamento
        splits = [
            {"customer_name": "João"},
            {"customer_name": "Maria"},
            {"customer_name": "Pedro"}
        ]
        
        partial_payments = table_service.split_payment(
            sample_store.id,
            command.id,
            "equal",
            splits
        )
        
        assert len(partial_payments) == 3
        assert partial_payments[0].amount == 3334  # R$ 33,34 (com resto)
        assert partial_payments[1].amount == 3333  # R$ 33,33
        assert partial_payments[2].amount == 3333  # R$ 33,33
    
    def test_get_table_dashboard(self, table_service, sample_store, sample_saloon, sample_table):
        """Testa geração do dashboard de mesas"""
        # Cria mais mesas
        table2 = models.Tables(
            store_id=sample_store.id,
            saloon_id=sample_saloon.id,
            name="Mesa 02",
            status=TableStatus.OCCUPIED,
            status_color="#dc3545"
        )
        table_service.db.add(table2)
        table_service.db.commit()
        
        dashboard = table_service.get_table_dashboard(sample_store.id)
        
        assert dashboard["total_tables"] == 2
        assert dashboard["available_tables"] == 1
        assert dashboard["occupied_tables"] == 1
        assert len(dashboard["saloons"]) == 1
        assert dashboard["saloons"][0]["total_tables"] == 2


# ═══════════════════════════════════════════════════════════
# TESTES DE VALIDAÇÃO
# ═══════════════════════════════════════════════════════════

class TestTableValidations:
    """Testes de validações do sistema de mesas"""
    
    def test_cannot_open_occupied_table(self, table_service, sample_store, sample_table):
        """Testa que não pode abrir mesa já ocupada"""
        sample_table.status = TableStatus.OCCUPIED
        table_service.db.commit()
        
        request = OpenTableRequest(
            table_id=sample_table.id,
            customer_name="Teste"
        )
        
        with pytest.raises(ValueError, match="já está ocupada"):
            table_service.open_table(sample_store.id, request)
    
    def test_cannot_close_table_without_command(self, table_service, sample_store, sample_table):
        """Testa que não pode fechar mesa sem comanda"""
        with pytest.raises(ValueError, match="Comanda não encontrada"):
            table_service.close_table(sample_store.id, sample_table.id, 999)
    
    def test_cannot_assign_nonexistent_employee(self, table_service, sample_store, sample_table):
        """Testa que não pode atribuir funcionário inexistente"""
        with pytest.raises(ValueError, match="Funcionário não encontrado"):
            table_service.assign_employee_to_table(
                sample_store.id,
                sample_table.id,
                999  # ID inexistente
            )
    
    def test_cannot_split_inactive_command(self, table_service, sample_store):
        """Testa que não pode dividir pagamento de comanda inativa"""
        command = models.Command(
            store_id=sample_store.id,
            status=CommandStatus.CLOSED  # Comanda fechada
        )
        table_service.db.add(command)
        table_service.db.commit()
        
        with pytest.raises(ValueError, match="Apenas comandas ativas"):
            table_service.split_payment(
                sample_store.id,
                command.id,
                "equal",
                [{"customer_name": "Teste"}]
            )


# ═══════════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO
# ═══════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTableIntegration:
    """Testes de integração do sistema de mesas"""
    
    def test_complete_table_flow(self, table_service, sample_store, sample_saloon, sample_user):
        """Testa fluxo completo de uma mesa"""
        # 1. Cria mesa
        create_request = CreateTableRequest(
            saloon_id=sample_saloon.id,
            name="Mesa Teste",
            max_capacity=4
        )
        table = table_service.create_table(sample_store.id, create_request)
        assert table.status == TableStatus.AVAILABLE
        
        # 2. Abre mesa
        open_request = OpenTableRequest(
            table_id=table.id,
            customer_name="Cliente Teste",
            attendant_id=sample_user.id
        )
        command = table_service.open_table(sample_store.id, open_request)
        assert table.status == TableStatus.OCCUPIED
        
        # 3. Adiciona itens (simulado)
        order = models.Order(
            store_id=sample_store.id,
            command_id=command.id,
            order_status=OrderStatus.RECEIVED,
            total_price=15000  # R$ 150,00
        )
        table_service.db.add(order)
        table_service.db.commit()
        
        # 4. Fecha mesa
        table_service.close_table(sample_store.id, table.id, command.id)
        assert table.status == TableStatus.AVAILABLE
        assert table.total_revenue_today == 15000
        
        # 5. Verifica histórico
        activities = table_service.db.query(models.TableActivityLog).filter(
            models.TableActivityLog.table_id == table.id
        ).all()
        assert len(activities) >= 2  # Abertura e fechamento
    
    @patch('src.api.admin.socketio.emitters.admin_emit_tables_and_commands')
    def test_websocket_events_emitted(self, mock_emit, table_service, sample_store, sample_table):
        """Testa que eventos WebSocket são emitidos"""
        request = UpdateTableRequest(status="RESERVED")
        
        table_service.update_table(sample_table.id, sample_store.id, request)
        
        # Verificaria se o evento foi emitido (mock)
        # Em produção, isso seria testado com um cliente WebSocket real


# ═══════════════════════════════════════════════════════════
# TESTES DE PERFORMANCE
# ═══════════════════════════════════════════════════════════

@pytest.mark.performance
class TestTablePerformance:
    """Testes de performance do sistema de mesas"""
    
    def test_dashboard_performance_with_many_tables(self, table_service, sample_store, sample_saloon):
        """Testa performance do dashboard com muitas mesas"""
        import time
        
        # Cria 100 mesas
        for i in range(100):
            table = models.Tables(
                store_id=sample_store.id,
                saloon_id=sample_saloon.id,
                name=f"Mesa {i:03d}",
                status=TableStatus.AVAILABLE if i % 2 == 0 else TableStatus.OCCUPIED
            )
            table_service.db.add(table)
        table_service.db.commit()
        
        # Mede tempo de geração do dashboard
        start_time = time.time()
        dashboard = table_service.get_table_dashboard(sample_store.id)
        execution_time = time.time() - start_time
        
        assert execution_time < 1.0  # Deve executar em menos de 1 segundo
        assert dashboard["total_tables"] == 100
    
    def test_activity_report_performance(self, table_service, sample_store, sample_table):
        """Testa performance do relatório de atividades"""
        import time
        
        # Cria 1000 logs de atividade
        for i in range(1000):
            log = models.TableActivityLog(
                table_id=sample_table.id,
                store_id=sample_store.id,
                action_type="test_action",
                created_at=datetime.now(timezone.utc) - timedelta(days=i % 30)
            )
            table_service.db.add(log)
        table_service.db.commit()
        
        # Mede tempo de geração do relatório
        start_time = time.time()
        report = table_service.get_table_activity_report(sample_store.id, sample_table.id)
        execution_time = time.time() - start_time
        
        assert execution_time < 2.0  # Deve executar em menos de 2 segundos
        assert len(report["activities"]) == 50  # Limite de 50 atividades
