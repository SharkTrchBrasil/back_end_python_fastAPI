"""
Testes do Sistema de Segurança
==============================
Testes de JWT, PIN, rate limiting e validações
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
import jwt
import hashlib
import time

from fastapi import HTTPException
from src.core.security.security_service import SecurityService
from src.core import models


# ═══════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock do banco de dados"""
    return MagicMock()


@pytest.fixture
def security_service(mock_db):
    """Cria instância do SecurityService"""
    with patch('src.core.security.security_service.config') as mock_config:
        mock_config.JWT_SECRET_KEY = "test-secret-key"
        mock_config.JWT_ALGORITHM = "HS256"
        mock_config.ACCESS_TOKEN_EXPIRE_MINUTES = 30
        mock_config.REFRESH_TOKEN_EXPIRE_DAYS = 7
        mock_config.REDIS_HOST = "localhost"
        mock_config.REDIS_PORT = 6379
        
        # Mock Redis
        with patch('src.core.security.security_service.redis_client'):
            service = SecurityService(mock_db)
            return service


@pytest.fixture
def sample_user():
    """Usuário de teste"""
    user = Mock(spec=models.User)
    user.id = 1
    user.email = "test@example.com"
    user.name = "Test User"
    user.hashed_password = "$2b$12$KIXxPfGGLI.QoGqGQheoFu.DlJLPdOFU2H6gMqGhFZjqTkLmZqGGe"  # "password"
    user.is_active = True
    user.pin_code = None
    user.pin_attempts = 0
    user.pin_locked_until = None
    return user


# ═══════════════════════════════════════════════════════════
# TESTES DE HASH DE SENHA
# ═══════════════════════════════════════════════════════════

class TestPasswordHashing:
    """Testes de hash e verificação de senha"""
    
    def test_hash_password(self, security_service):
        """Testa criação de hash de senha"""
        password = "MySecurePassword123!"
        hashed = security_service.hash_password(password)
        
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt
        assert len(hashed) > 50
    
    def test_verify_password_correct(self, security_service):
        """Testa verificação de senha correta"""
        password = "MySecurePassword123!"
        hashed = security_service.hash_password(password)
        
        is_valid = security_service.verify_password(password, hashed)
        assert is_valid is True
    
    def test_verify_password_incorrect(self, security_service):
        """Testa rejeição de senha incorreta"""
        password = "MySecurePassword123!"
        hashed = security_service.hash_password(password)
        
        is_valid = security_service.verify_password("WrongPassword", hashed)
        assert is_valid is False
    
    def test_hash_different_each_time(self, security_service):
        """Testa que o hash é diferente a cada vez (salt)"""
        password = "SamePassword"
        hash1 = security_service.hash_password(password)
        hash2 = security_service.hash_password(password)
        
        assert hash1 != hash2  # Diferentes devido ao salt
        assert security_service.verify_password(password, hash1)
        assert security_service.verify_password(password, hash2)


# ═══════════════════════════════════════════════════════════
# TESTES DE JWT
# ═══════════════════════════════════════════════════════════

class TestJWT:
    """Testes de tokens JWT"""
    
    def test_create_access_token(self, security_service):
        """Testa criação de access token"""
        token = security_service.create_access_token(
            user_id=1,
            store_id=100,
            role="admin"
        )
        
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT tem 3 partes
        
        # Decodifica para verificar payload
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == "1"
        assert payload["store_id"] == 100
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
    
    def test_create_refresh_token(self, security_service):
        """Testa criação de refresh token"""
        token = security_service.create_refresh_token(user_id=1)
        
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"
        assert "jti" in payload  # JWT ID único
    
    def test_verify_valid_token(self, security_service):
        """Testa verificação de token válido"""
        token = security_service.create_access_token(user_id=1)
        
        payload = security_service.verify_token(token, token_type="access")
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
    
    def test_verify_expired_token(self, security_service):
        """Testa rejeição de token expirado"""
        # Cria token já expirado
        expires = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "1",
            "exp": expires,
            "type": "access",
            "jti": "test-jti"
        }
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.verify_token(token)
        
        assert exc_info.value.status_code == 401
        assert "expirado" in exc_info.value.detail
    
    def test_verify_wrong_token_type(self, security_service):
        """Testa rejeição de token com tipo incorreto"""
        refresh_token = security_service.create_refresh_token(user_id=1)
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.verify_token(refresh_token, token_type="access")
        
        assert exc_info.value.status_code == 401
        assert "Tipo de token inválido" in exc_info.value.detail
    
    @patch('src.core.security.security_service.redis_client')
    def test_refresh_access_token(self, mock_redis, security_service, sample_user):
        """Testa renovação de access token"""
        mock_redis.exists.return_value = 0  # Token não revogado
        
        # Setup usuário no banco
        security_service.db.query.return_value.filter.return_value.first.return_value = sample_user
        
        refresh_token = security_service.create_refresh_token(user_id=1)
        
        result = security_service.refresh_access_token(refresh_token)
        
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
    
    @patch('src.core.security.security_service.redis_client')
    def test_revoke_token(self, mock_redis, security_service):
        """Testa revogação de token"""
        jti = "unique-token-id"
        
        security_service.revoke_token(jti)
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert f"revoked_token:{jti}" in call_args[0]


# ═══════════════════════════════════════════════════════════
# TESTES DE LOGIN COM PIN
# ═══════════════════════════════════════════════════════════

class TestPINLogin:
    """Testes de autenticação com PIN"""
    
    def test_create_pin(self, security_service, sample_user):
        """Testa criação de PIN"""
        security_service.db.query.return_value.filter.return_value.first.return_value = sample_user
        
        pin = security_service.create_pin(user_id=1)
        
        assert len(pin) == 6
        assert pin.isdigit()
        assert sample_user.pin_code == hashlib.sha256(pin.encode()).hexdigest()
        assert sample_user.pin_attempts == 0
        security_service.db.commit.assert_called_once()
    
    def test_verify_pin_correct(self, security_service, sample_user):
        """Testa verificação de PIN correto"""
        pin = "123456"
        sample_user.pin_code = hashlib.sha256(pin.encode()).hexdigest()
        
        # Mock do acesso à loja
        security_service.db.query.return_value.join.return_value.filter.return_value.first.return_value = sample_user
        
        result = security_service.verify_pin(pin, store_id=100)
        
        assert result == sample_user
        assert sample_user.pin_attempts == 0
    
    def test_verify_pin_incorrect(self, security_service):
        """Testa rejeição de PIN incorreto"""
        security_service.db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        
        result = security_service.verify_pin("999999", store_id=100)
        
        assert result is None
    
    def test_verify_pin_locked(self, security_service, sample_user):
        """Testa bloqueio após tentativas falhas"""
        sample_user.pin_locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
        
        security_service.db.query.return_value.join.return_value.filter.return_value.first.return_value = sample_user
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.verify_pin("123456", store_id=100)
        
        assert exc_info.value.status_code == 429
        assert "bloqueado" in exc_info.value.detail
    
    def test_register_failed_attempts(self, security_service, sample_user):
        """Testa registro de tentativas falhas"""
        pin = "123456"
        sample_user.pin_code = hashlib.sha256(pin.encode()).hexdigest()
        sample_user.pin_attempts = 2  # Já teve 2 tentativas
        
        security_service.db.query.return_value.filter.return_value.first.return_value = sample_user
        
        security_service.register_failed_pin_attempt(pin)
        
        assert sample_user.pin_attempts == 3
        assert sample_user.pin_locked_until is not None
        security_service.db.commit.assert_called_once()


# ═══════════════════════════════════════════════════════════
# TESTES DE RATE LIMITING
# ═══════════════════════════════════════════════════════════

class TestRateLimiting:
    """Testes de rate limiting"""
    
    @patch('src.core.security.security_service.redis_client')
    def test_check_rate_limit_within_limit(self, mock_redis, security_service):
        """Testa rate limit dentro do limite"""
        mock_redis.pipeline.return_value.execute.return_value = [None, 5, None, None]
        
        is_allowed = security_service.check_rate_limit("test_key", max_requests=10)
        
        assert is_allowed is True
    
    @patch('src.core.security.security_service.redis_client')
    def test_check_rate_limit_exceeded(self, mock_redis, security_service):
        """Testa rate limit excedido"""
        mock_redis.pipeline.return_value.execute.return_value = [None, 15, None, None]
        
        is_allowed = security_service.check_rate_limit("test_key", max_requests=10)
        
        assert is_allowed is False
    
    @patch('src.core.security.security_service.redis_client')
    def test_apply_rate_limit_login_endpoint(self, mock_redis, security_service):
        """Testa rate limit específico para login"""
        mock_redis.pipeline.return_value.execute.return_value = [None, 6, None, None]
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.apply_rate_limit("192.168.1.1", "login")
        
        assert exc_info.value.status_code == 429
        assert "5 requisições em 300 segundos" in exc_info.value.detail


# ═══════════════════════════════════════════════════════════
# TESTES DE VALIDAÇÃO DE DADOS
# ═══════════════════════════════════════════════════════════

class TestDataValidation:
    """Testes de validação de dados"""
    
    def test_validate_cpf_valid(self, security_service):
        """Testa validação de CPF válido"""
        # CPF válido: 111.444.777-35
        is_valid = security_service.validate_cpf("11144477735")
        assert is_valid is True
        
        # Com formatação
        is_valid = security_service.validate_cpf("111.444.777-35")
        assert is_valid is True
    
    def test_validate_cpf_invalid(self, security_service):
        """Testa rejeição de CPF inválido"""
        # Todos dígitos iguais
        is_valid = security_service.validate_cpf("11111111111")
        assert is_valid is False
        
        # Dígito verificador incorreto
        is_valid = security_service.validate_cpf("11144477799")
        assert is_valid is False
        
        # Tamanho incorreto
        is_valid = security_service.validate_cpf("123")
        assert is_valid is False
    
    def test_validate_cnpj_valid(self, security_service):
        """Testa validação de CNPJ válido"""
        # CNPJ válido: 11.444.777/0001-61
        is_valid = security_service.validate_cnpj("11444777000161")
        assert is_valid is True
        
        # Com formatação
        is_valid = security_service.validate_cnpj("11.444.777/0001-61")
        assert is_valid is True
    
    def test_validate_cnpj_invalid(self, security_service):
        """Testa rejeição de CNPJ inválido"""
        # Todos dígitos iguais
        is_valid = security_service.validate_cnpj("11111111111111")
        assert is_valid is False
        
        # Dígito verificador incorreto
        is_valid = security_service.validate_cnpj("11444777000199")
        assert is_valid is False
    
    def test_sanitize_input(self, security_service):
        """Testa sanitização de input"""
        # Remove caracteres de controle
        sanitized = security_service.sanitize_input("Hello\x00World\x01")
        assert sanitized == "Hello World"
        
        # Remove espaços extras
        sanitized = security_service.sanitize_input("  Multiple   spaces   ")
        assert sanitized == "Multiple spaces"
        
        # Limita tamanho
        long_text = "x" * 1000
        sanitized = security_service.sanitize_input(long_text, max_length=100)
        assert len(sanitized) == 100
        
        # Mantém quebras de linha
        sanitized = security_service.sanitize_input("Line1\nLine2")
        assert "Line1\nLine2" in sanitized or "Line1 Line2" in sanitized


# ═══════════════════════════════════════════════════════════
# TESTES DE VALIDAÇÃO DE TENANT
# ═══════════════════════════════════════════════════════════

class TestTenantValidation:
    """Testes de validação multi-tenant"""
    
    def test_validate_tenant_access_allowed(self, security_service):
        """Testa acesso permitido ao tenant"""
        access = Mock(spec=models.StoreAccess)
        access.user_id = 1
        access.store_id = 100
        access.role_id = 1
        
        security_service.db.query.return_value.filter.return_value.first.return_value = access
        
        is_valid = security_service.validate_tenant_access(
            user_id=1,
            store_id=100
        )
        
        assert is_valid is True
    
    def test_validate_tenant_access_denied(self, security_service):
        """Testa acesso negado ao tenant"""
        security_service.db.query.return_value.filter.return_value.first.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.validate_tenant_access(
                user_id=1,
                store_id=999
            )
        
        assert exc_info.value.status_code == 403
        assert "Acesso negado" in exc_info.value.detail
    
    def test_validate_tenant_access_with_role(self, security_service):
        """Testa validação de role específica"""
        access = Mock()
        access.role_id = 1
        
        role = Mock()
        role.machine_name = "admin"
        
        security_service.db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=access)))),
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=role))))
        ]
        
        is_valid = security_service.validate_tenant_access(
            user_id=1,
            store_id=100,
            required_role="admin"
        )
        
        assert is_valid is True
    
    def test_validate_tenant_access_wrong_role(self, security_service):
        """Testa rejeição por role incorreta"""
        access = Mock()
        access.role_id = 2
        
        role = Mock()
        role.machine_name = "employee"
        
        security_service.db.query.side_effect = [
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=access)))),
            Mock(filter=Mock(return_value=Mock(first=Mock(return_value=role))))
        ]
        
        with pytest.raises(HTTPException) as exc_info:
            security_service.validate_tenant_access(
                user_id=1,
                store_id=100,
                required_role="admin"
            )
        
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail
