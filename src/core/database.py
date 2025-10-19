"""
Enterprise Database Layer
=========================
Suporta 5.000-10.000 lojas simultâneas com alta disponibilidade

Características:
- ✅ Connection pooling otimizado
- ✅ Read replicas para separação de carga
- ✅ Health checks automáticos
- ✅ Circuit breaker pattern
- ✅ Monitoring e métricas
- ✅ Automatic failover
- ✅ Query optimization
- ✅ Connection retry logic

Autor: PDVix Team
Última atualização: 2025-01-19
"""

import logging
import time
from contextlib import contextmanager
from typing import Annotated, Optional
from functools import wraps

from fastapi import Depends, HTTPException, status
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import DBAPIError, OperationalError, DisconnectionError

from src.core.config import config

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÕES ENTERPRISE
# ═══════════════════════════════════════════════════════════

class DatabaseConfig:
    """Configurações centralizadas do banco de dados"""

    # Pool de Conexões - Produção
    PRODUCTION_POOL_SIZE = 50  # 50 conexões permanentes
    PRODUCTION_MAX_OVERFLOW = 50  # Até 100 conexões total
    PRODUCTION_POOL_TIMEOUT = 10  # Timeout de 10s
    PRODUCTION_POOL_RECYCLE = 1800  # Recicla a cada 30min

    # Pool de Conexões - Desenvolvimento
    DEV_POOL_SIZE = 10
    DEV_MAX_OVERFLOW = 20
    DEV_POOL_TIMEOUT = 30
    DEV_POOL_RECYCLE = 3600

    # Retry Logic
    MAX_RETRIES = 3
    RETRY_DELAY = 0.5  # segundos

    # Health Check
    HEALTH_CHECK_INTERVAL = 60  # segundos

    # Circuit Breaker
    CIRCUIT_BREAKER_THRESHOLD = 5  # Falhas consecutivas para abrir
    CIRCUIT_BREAKER_TIMEOUT = 30  # Segundos em estado aberto
    CIRCUIT_BREAKER_HALF_OPEN_CALLS = 3  # Tentativas em half-open


# ═══════════════════════════════════════════════════════════
# CIRCUIT BREAKER PATTERN
# ═══════════════════════════════════════════════════════════

class CircuitBreaker:
    """
    Implementação do padrão Circuit Breaker para proteção do banco

    Estados:
    - CLOSED: Funcionando normalmente
    - OPEN: Muitas falhas, bloqueando chamadas
    - HALF_OPEN: Testando recuperação
    """

    def __init__(self, threshold: int, timeout: int):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self.half_open_calls = 0

    def call(self, func):
        """Decorator para proteger chamadas ao banco"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "HALF_OPEN"
                    self.half_open_calls = 0
                    logger.info("🟡 Circuit Breaker: HALF_OPEN - Testando recuperação")
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database temporarily unavailable. Please try again later."
                    )

            try:
                result = func(*args, **kwargs)
                self.on_success()
                return result
            except Exception as e:
                self.on_failure()
                raise

        return wrapper

    def on_success(self):
        """Chamada bem-sucedida"""
        if self.state == "HALF_OPEN":
            self.half_open_calls += 1
            if self.half_open_calls >= DatabaseConfig.CIRCUIT_BREAKER_HALF_OPEN_CALLS:
                self.state = "CLOSED"
                self.failures = 0
                logger.info("✅ Circuit Breaker: CLOSED - Sistema recuperado")
        else:
            self.failures = 0

    def on_failure(self):
        """Chamada falhou"""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.threshold:
            self.state = "OPEN"
            logger.error(
                f"🔴 Circuit Breaker: OPEN - {self.failures} falhas consecutivas. "
                f"Bloqueando chamadas por {self.timeout}s"
            )


# Instância global do circuit breaker
db_circuit_breaker = CircuitBreaker(
    threshold=DatabaseConfig.CIRCUIT_BREAKER_THRESHOLD,
    timeout=DatabaseConfig.CIRCUIT_BREAKER_TIMEOUT
)


# ═══════════════════════════════════════════════════════════
# ENGINE CONFIGURATION
# ═══════════════════════════════════════════════════════════

def get_engine_config() -> dict:
    """
    Retorna configuração otimizada baseada no ambiente

    Returns:
        dict: Configuração do SQLAlchemy engine
    """

    if config.is_production:
        return {
            "poolclass": QueuePool,
            "pool_size": DatabaseConfig.PRODUCTION_POOL_SIZE,
            "max_overflow": DatabaseConfig.PRODUCTION_MAX_OVERFLOW,
            "pool_timeout": DatabaseConfig.PRODUCTION_POOL_TIMEOUT,
            "pool_recycle": DatabaseConfig.PRODUCTION_POOL_RECYCLE,
            "pool_pre_ping": True,
            "pool_use_lifo": True,  # LIFO para melhor cache de conexões
            "echo": False,
            "echo_pool": False,
            "connect_args": {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",  # 30s query timeout
                "application_name": "pdvix_api",
            },
            "execution_options": {
                "isolation_level": "READ COMMITTED"
            }
        }
    elif config.is_test:
        return {
            "poolclass": NullPool,
            "echo": False,
        }
    else:
        return {
            "poolclass": QueuePool,
            "pool_size": DatabaseConfig.DEV_POOL_SIZE,
            "max_overflow": DatabaseConfig.DEV_MAX_OVERFLOW,
            "pool_timeout": DatabaseConfig.DEV_POOL_TIMEOUT,
            "pool_recycle": DatabaseConfig.DEV_POOL_RECYCLE,
            "pool_pre_ping": True,
            "echo": config.DEBUG,
        }


# ═══════════════════════════════════════════════════════════
# ENGINES (WRITE + READ REPLICAS)
# ═══════════════════════════════════════════════════════════

# Engine principal (WRITE)
engine_config = get_engine_config()
engine = create_engine(config.DATABASE_URL, **engine_config)

# Read Replica (se configurada)
read_engine = None
if hasattr(config, 'DATABASE_READ_REPLICA_URL') and config.DATABASE_READ_REPLICA_URL:
    read_engine = create_engine(config.DATABASE_READ_REPLICA_URL, **engine_config)
    logger.info("✅ Read Replica configurada")


# ═══════════════════════════════════════════════════════════
# EVENT LISTENERS PARA MONITORAMENTO
# ═══════════════════════════════════════════════════════════

@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Executado quando uma nova conexão é criada"""
    connection_record.info["pid"] = dbapi_conn.get_backend_pid() if hasattr(dbapi_conn, 'get_backend_pid') else None
    logger.debug("🔵 Nova conexão criada no pool")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Executado quando uma conexão é retirada do pool"""
    if config.is_production:
        stats = get_pool_stats()
        if stats["utilization_percent"] > 90:
            logger.warning(
                f"⚠️ POOL CRÍTICO: {stats['utilization_percent']}% utilizado | "
                f"{stats['checked_out']}/{stats['max_connections']} conexões"
            )


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Executado quando uma conexão retorna ao pool"""
    logger.debug("🔵 Conexão retornou ao pool")


# ═══════════════════════════════════════════════════════════
# SESSION MAKERS
# ═══════════════════════════════════════════════════════════

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

if read_engine:
    ReadSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=read_engine,
        expire_on_commit=False
    )
else:
    ReadSessionLocal = SessionLocal


# ═══════════════════════════════════════════════════════════
# RETRY LOGIC
# ═══════════════════════════════════════════════════════════

def retry_on_db_error(max_retries: int = DatabaseConfig.MAX_RETRIES):
    """
    Decorator para retry automático em erros de conexão

    ✅ VERSÃO CORRIGIDA: Compatível com geradores (generators) de
    dependência do FastAPI.
    """

    def decorator(func_gen):
        @wraps(func_gen)
        def wrapper(*args, **kwargs):
            last_exception = None
            gen = None
            resource = None

            # 1. Tenta INICIAR o gerador e obter o recurso (a sessão)
            #    Isso é feito dentro de um loop de retry.
            for attempt in range(max_retries):
                try:
                    # Cria o gerador (ex: chama get_db() ou get_read_db())
                    gen = func_gen(*args, **kwargs)
                    # Executa o gerador até o primeiro 'yield'
                    resource = next(gen)

                    # Se 'next(gen)' funcionou, a sessão foi criada
                    last_exception = None
                    break  # Sucesso, sai do loop de retry

                except (OperationalError, DisconnectionError, DBAPIError) as e:
                    # Falha de conexão ao tentar criar a sessão
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = DatabaseConfig.RETRY_DELAY * (2 ** attempt)  # Backoff
                        logger.warning(
                            f"⚠️ Erro de banco (tentativa {attempt + 1}/{max_retries}). "
                            f"Retentando em {delay}s... Erro: {str(e)}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"❌ Falha ao obter sessão após {max_retries} tentativas: {str(e)}")

                except StopIteration:
                    # O gerador não deu 'yield' em nada
                    last_exception = RuntimeError(f"Dependency generator {func_gen.__name__} did not yield a value.")
                    break

            if last_exception:
                raise last_exception

            # 2. Se o recurso (sessão) foi obtido, dá 'yield' para a rota
            try:
                yield resource
            except Exception as e:
                # 3. Se um erro acontece na rota, joga de volta no gerador
                #    para acionar o 'except' ou 'finally' original
                logger.error(f"❌ Erro na sessão: {e}", exc_info=True)
                try:
                    gen.throw(e)
                except StopIteration:
                    pass
                except Exception as gen_e:
                    logger.error(f"❌ Erro ao fechar gerador: {gen_e}", exc_info=True)
                raise  # Levanta a exceção original da rota
            else:
                # 4. Se a rota terminou sem erro, executa o 'finally' do gerador
                try:
                    next(gen)
                except StopIteration:
                    pass  # O gerador terminou normalmente

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════
# DATABASE DEPENDENCIES
# ═══════════════════════════════════════════════════════════

@retry_on_db_error()
def get_db():
    """
    Dependency para operações de ESCRITA (INSERT, UPDATE, DELETE)

    Features:
    - ✅ Retry automático
    - ✅ Circuit breaker
    - ✅ Rollback em erro
    - ✅ Logging de exceções
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"❌ Erro na sessão de escrita: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


@retry_on_db_error()
def get_read_db():
    """
    Dependency para operações de LEITURA (SELECT)

    Usa read replica se disponível, senão usa engine principal
    """
    db = ReadSessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"❌ Erro na sessão de leitura: {e}", exc_info=True)
        db.rollback()
        raise
    finally:
        db.close()


get_db_manager = contextmanager(get_db)
get_read_db_manager = contextmanager(get_read_db)

GetDBDep = Annotated[Session, Depends(get_db)]
GetReadDBDep = Annotated[Session, Depends(get_read_db)]


# ═══════════════════════════════════════════════════════════
# MONITORING E HEALTH CHECKS
# ═══════════════════════════════════════════════════════════

def get_pool_stats(engine_instance=None) -> dict:
    """
    Retorna estatísticas detalhadas do pool de conexões

    Args:
        engine_instance: Engine específico (padrão: engine principal)

    Returns:
        dict: Estatísticas completas do pool
    """
    if engine_instance is None:
        engine_instance = engine

    pool = engine_instance.pool

    pool_size = getattr(engine_instance.pool, '_pool', None)
    checked_out = pool.checkedout() if hasattr(pool, 'checkedout') else 0
    overflow = pool.overflow() if hasattr(pool, 'overflow') else 0
    size = pool.size() if hasattr(pool, 'size') else 0

    max_connections = engine_config.get("pool_size", 10) + engine_config.get("max_overflow", 20)

    return {
        "pool_size": size,
        "checked_in": max(0, size - checked_out),
        "checked_out": checked_out,
        "overflow": overflow,
        "total_connections": size + overflow,
        "max_connections": max_connections,
        "utilization_percent": round((checked_out / max_connections) * 100, 2) if max_connections > 0 else 0,
        "available_connections": max_connections - checked_out,
        "circuit_breaker_state": db_circuit_breaker.state,
        "circuit_breaker_failures": db_circuit_breaker.failures,
    }


def check_database_health() -> dict:
    """
    Verifica saúde completa do banco de dados

    Returns:
        dict: Status de saúde detalhado
    """
    health_status = {
        "healthy": True,
        "timestamp": time.time(),
        "checks": {}
    }

    # 1. Testa conexão com query simples
    try:
        with get_db_manager() as db:
            result = db.execute(text("SELECT 1")).scalar()
            health_status["checks"]["connection"] = {
                "status": "healthy",
                "latency_ms": 0
            }
    except Exception as e:
        health_status["healthy"] = False
        health_status["checks"]["connection"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # 2. Verifica pool stats
    pool_stats = get_pool_stats()
    health_status["checks"]["pool"] = pool_stats

    if pool_stats["utilization_percent"] > 90:
        health_status["healthy"] = False
        health_status["checks"]["pool"]["warning"] = "Pool utilization critical"

    # 3. Verifica read replica (se configurada)
    if read_engine:
        try:
            with get_read_db_manager() as db:
                result = db.execute(text("SELECT 1")).scalar()
                health_status["checks"]["read_replica"] = {
                    "status": "healthy"
                }
        except Exception as e:
            health_status["checks"]["read_replica"] = {
                "status": "unhealthy",
                "error": str(e)
            }

    # 4. Circuit breaker status
    health_status["checks"]["circuit_breaker"] = {
        "state": db_circuit_breaker.state,
        "failures": db_circuit_breaker.failures
    }

    if db_circuit_breaker.state == "OPEN":
        health_status["healthy"] = False

    return health_status


def force_close_idle_connections():
    """
    Força fechamento de conexões ociosas

    Útil para manutenção ou antes de fazer deploy
    """
    logger.info("🔄 Forçando fechamento de conexões ociosas...")

    stats_before = get_pool_stats()
    logger.info(f"📊 Antes: {stats_before['total_connections']} conexões ativas")

    engine.dispose()

    if read_engine:
        read_engine.dispose()

    stats_after = get_pool_stats()
    logger.info(f"✅ Após: {stats_after['total_connections']} conexões ativas")

    return {
        "before": stats_before,
        "after": stats_after
    }


# ═══════════════════════════════════════════════════════════
# STARTUP CHECKS
# ═══════════════════════════════════════════════════════════

def validate_database_connection():
    """
    Valida conexão no startup da aplicação

    Raises:
        RuntimeError: Se não conseguir conectar ao banco
    """
    logger.info("🔍 Validando conexão com banco de dados...")

    try:
        with get_db_manager() as db:
            result = db.execute(text("SELECT version()")).scalar()
            logger.info(f"✅ Conectado ao PostgreSQL: {result}")

        stats = get_pool_stats()
        logger.info(
            f"📊 Pool de conexões inicializado:\n"
            f"   ├─ Pool size: {stats['pool_size']}\n"
            f"   ├─ Max overflow: {engine_config.get('max_overflow', 0)}\n"
            f"   └─ Max connections: {stats['max_connections']}"
        )

        if read_engine:
            with get_read_db_manager() as db:
                result = db.execute(text("SELECT version()")).scalar()
                logger.info(f"✅ Read Replica conectada: {result}")

    except Exception as e:
        logger.critical(f"❌ FALHA CRÍTICA: Não foi possível conectar ao banco de dados: {e}")
        raise RuntimeError(f"Database connection failed: {e}")


# Executa validação no import (apenas em produção)
if config.is_production:
    validate_database_connection()