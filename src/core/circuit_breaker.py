"""
Circuit Breaker Pattern Implementation
======================================
Implementa o padrão Circuit Breaker para proteger chamadas a APIs externas.

Estados:
- CLOSED: Normal, requisições passam
- OPEN: Falhas detectadas, requisições são bloqueadas
- HALF_OPEN: Testando se o serviço se recuperou

Uso:
    @circuit_breaker_decorator(failure_threshold=5, timeout=60)
    async def call_external_api():
        ...
"""

import logging
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, Tuple

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    RetryError
)

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "CLOSED"           # Normal
    OPEN = "OPEN"               # Falhas detectadas
    HALF_OPEN = "HALF_OPEN"     # Testando recuperação


class CircuitBreakerException(Exception):
    """Exceção levantada quando o Circuit Breaker está OPEN"""
    pass


class CircuitBreaker:
    """
    Circuit Breaker para proteger chamadas a APIs externas.
    
    Atributos:
        name: Nome do circuit breaker (para logs)
        failure_threshold: Número de falhas antes de abrir
        recovery_timeout: Segundos antes de tentar recuperar (HALF_OPEN)
        expected_exception: Exceção esperada a monitorar
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Tuple[type, ...] = (Exception,)
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

        logger.info(f"✅ Circuit Breaker '{name}' inicializado")
        logger.info(f"   ├─ Threshold: {failure_threshold} falhas")
        logger.info(f"   ├─ Timeout: {recovery_timeout}s")
        logger.info(f"   └─ Estado: {self.state}")

    def is_circuit_open(self) -> bool:
        """Verifica se o circuit breaker está aberto"""
        if self.state == CircuitBreakerState.CLOSED:
            return False

        if self.state == CircuitBreakerState.OPEN:
            # Verifica se é hora de tentar recuperar
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.warning(
                    f"🟡 Circuit Breaker '{self.name}' passando para HALF_OPEN "
                    f"(testando recuperação)"
                )
                self.state = CircuitBreakerState.HALF_OPEN
                return False
            return True

        # HALF_OPEN - permite uma requisição para testar
        return False

    def record_failure(self):
        """Registra uma falha"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        logger.error(
            f"❌ Circuit Breaker '{self.name}' registrou falha "
            f"({self.failure_count}/{self.failure_threshold})"
        )

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.error(
                f"🔴 Circuit Breaker '{self.name}' ABERTO! "
                f"Bloqueando requisições por {self.recovery_timeout}s"
            )

    def record_success(self):
        """Registra um sucesso"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.info(
                f"✅ Circuit Breaker '{self.name}' RECUPERADO! "
                f"Voltando para CLOSED"
            )
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset na próxima falha se houver períodos sem falhas
            if time.time() - (self.last_failure_time or 0) > self.recovery_timeout * 2:
                self.failure_count = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Executa a função protegida pelo circuit breaker
        
        Levanta CircuitBreakerException se o circuit está OPEN
        """
        if self.is_circuit_open():
            raise CircuitBreakerException(
                f"Circuit Breaker '{self.name}' está ABERTO. "
                f"Serviço indisponível. Tente novamente em {self.recovery_timeout}s"
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure()
            raise


# Instâncias globais de Circuit Breakers para serviços específicos
circuit_breakers = {
    "mercadopago": CircuitBreaker(
        name="MercadoPago",
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=(Exception,)
    ),
    "aws_s3": CircuitBreaker(
        name="AWS_S3",
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=(Exception,)
    ),
    "geocoding": CircuitBreaker(
        name="Geocoding",
        failure_threshold=10,
        recovery_timeout=30,
        expected_exception=(Exception,)
    ),
    "chatbot_api": CircuitBreaker(
        name="ChatBot_API",
        failure_threshold=5,
        recovery_timeout=60,
        expected_exception=(Exception,)
    ),
    "email": CircuitBreaker(
        name="Email",
        failure_threshold=3,
        recovery_timeout=120,
        expected_exception=(Exception,)
    ),
}


def circuit_breaker_decorator(
    service_name: str = "default",
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    max_retries: int = 3,
    backoff_factor: float = 1.0
):
    """
    Decorator para aplicar Circuit Breaker com retry automático.
    
    Uso:
        @circuit_breaker_decorator("mercadopago", failure_threshold=5)
        async def create_payment(...):
            ...
    
    Args:
        service_name: Nome do serviço para identificar no log
        failure_threshold: Falhas antes de abrir
        recovery_timeout: Segundos para tentar recuperar
        max_retries: Tentativas com backoff exponencial
        backoff_factor: Multiplicador para backoff (1.0 = 2^x * 1.0)
    """
    def decorator(func: Callable) -> Callable:
        # Pega ou cria o circuit breaker
        if service_name not in circuit_breakers:
            circuit_breakers[service_name] = CircuitBreaker(
                name=service_name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )

        breaker = circuit_breakers[service_name]

        # Aplica retry + circuit breaker
        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=backoff_factor, min=1, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                # Verifica circuit breaker
                if breaker.is_circuit_open():
                    raise CircuitBreakerException(
                        f"Circuit Breaker '{service_name}' está ABERTO"
                    )

                result = await func(*args, **kwargs)
                breaker.record_success()
                return result

            except CircuitBreakerException:
                raise
            except Exception as e:
                breaker.record_failure()
                logger.error(f"Erro em {service_name}: {e}")
                raise

        @retry(
            stop=stop_after_attempt(max_retries),
            wait=wait_exponential(multiplier=backoff_factor, min=1, max=10),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                # Verifica circuit breaker
                if breaker.is_circuit_open():
                    raise CircuitBreakerException(
                        f"Circuit Breaker '{service_name}' está ABERTO"
                    )

                result = func(*args, **kwargs)
                breaker.record_success()
                return result

            except CircuitBreakerException:
                raise
            except Exception as e:
                breaker.record_failure()
                logger.error(f"Erro em {service_name}: {e}")
                raise

        # Detecta se é async ou sync
        import asyncio
        import inspect
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Obtém um circuit breaker existente"""
    return circuit_breakers.get(service_name)


def get_all_circuit_breakers_status() -> dict:
    """Retorna o status de todos os circuit breakers"""
    return {
        name: {
            "state": breaker.state,
            "failure_count": breaker.failure_count,
            "failure_threshold": breaker.failure_threshold,
            "last_failure_time": breaker.last_failure_time,
            "recovery_timeout": breaker.recovery_timeout
        }
        for name, breaker in circuit_breakers.items()
    }
