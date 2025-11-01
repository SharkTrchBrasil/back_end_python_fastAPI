"""
Serviço de Segurança Completo
=============================
JWT, Rate Limiting, Validações, PIN Login
"""

import secrets
import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import redis
from fastapi import HTTPException, status

from src.core import models
from src.core.config import config

# Configuração do contexto de senha
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis para rate limiting e cache
redis_client = redis.Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    db=0,
    decode_responses=True
)


class SecurityService:
    """Serviço completo de segurança para produção"""
    
    def __init__(self, db: Session):
        self.db = db
        self.jwt_secret = config.JWT_SECRET_KEY
        self.jwt_algorithm = config.JWT_ALGORITHM
        self.access_token_expire_minutes = config.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = config.REFRESH_TOKEN_EXPIRE_DAYS
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 30
        self.pin_max_attempts = 3
        self.pin_lockout_minutes = 15
    
    # ═══════════════════════════════════════════════════════════
    # HASH E VERIFICAÇÃO DE SENHAS
    # ═══════════════════════════════════════════════════════════
    
    def hash_password(self, password: str) -> str:
        """
        Cria hash seguro da senha usando bcrypt
        
        Args:
            password: Senha em texto plano
            
        Returns:
            Hash bcrypt da senha
        """
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verifica se a senha corresponde ao hash
        
        Args:
            plain_password: Senha em texto plano
            hashed_password: Hash bcrypt
            
        Returns:
            True se a senha está correta
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    # ═══════════════════════════════════════════════════════════
    # JWT TOKENS COM REFRESH
    # ═══════════════════════════════════════════════════════════
    
    def create_access_token(
        self, 
        user_id: int, 
        store_id: Optional[int] = None,
        role: Optional[str] = None
    ) -> str:
        """
        Cria um access token JWT
        
        Args:
            user_id: ID do usuário
            store_id: ID da loja (opcional)
            role: Role do usuário (opcional)
            
        Returns:
            Token JWT assinado
        """
        expires = datetime.now(timezone.utc) + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": str(user_id),
            "exp": expires,
            "iat": datetime.now(timezone.utc),
            "type": "access",
            "jti": secrets.token_urlsafe(16)  # ID único do token
        }
        
        if store_id:
            payload["store_id"] = store_id
        
        if role:
            payload["role"] = role
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def create_refresh_token(self, user_id: int) -> str:
        """
        Cria um refresh token JWT
        
        Args:
            user_id: ID do usuário
            
        Returns:
            Refresh token JWT
        """
        expires = datetime.now(timezone.utc) + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": str(user_id),
            "exp": expires,
            "iat": datetime.now(timezone.utc),
            "type": "refresh",
            "jti": secrets.token_urlsafe(16)
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        
        # Salva o refresh token no banco
        self._save_refresh_token(user_id, token, expires)
        
        return token
    
    def verify_token(self, token: str, token_type: str = "access") -> Dict[str, Any]:
        """
        Verifica e decodifica um token JWT
        
        Args:
            token: Token JWT
            token_type: Tipo do token (access ou refresh)
            
        Returns:
            Payload decodificado
            
        Raises:
            HTTPException: Se o token for inválido
        """
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Verifica tipo do token
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Tipo de token inválido"
                )
            
            # Verifica se o token foi revogado
            if self._is_token_revoked(payload.get("jti")):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revogado"
                )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado"
            )
        except jwt.JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token inválido: {str(e)}"
            )
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Gera novo access token usando refresh token
        
        Args:
            refresh_token: Refresh token válido
            
        Returns:
            Dict com novo access_token e refresh_token
        """
        payload = self.verify_token(refresh_token, token_type="refresh")
        user_id = int(payload["sub"])
        
        # Verifica se o usuário ainda existe e está ativo
        user = self.db.query(models.User).filter(
            models.User.id == user_id,
            models.User.is_active == True
        ).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não encontrado ou inativo"
            )
        
        # Cria novos tokens
        new_access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token(user_id)
        
        # Revoga o refresh token antigo
        self.revoke_token(payload.get("jti"))
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    
    def revoke_token(self, jti: str):
        """
        Revoga um token pelo seu JTI
        
        Args:
            jti: JWT ID do token
        """
        if jti:
            # Adiciona à blacklist no Redis com TTL
            redis_client.setex(
                f"revoked_token:{jti}",
                timedelta(days=self.refresh_token_expire_days + 1),
                "1"
            )
    
    # ═══════════════════════════════════════════════════════════
    # LOGIN COM PIN
    # ═══════════════════════════════════════════════════════════
    
    def create_pin(self, user_id: int) -> str:
        """
        Cria um PIN único para o usuário
        
        Args:
            user_id: ID do usuário
            
        Returns:
            PIN de 6 dígitos
        """
        # Gera PIN aleatório de 6 dígitos
        pin = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        # Hash do PIN
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        
        # Salva no banco
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.pin_code = pin_hash
            user.pin_attempts = 0
            user.pin_locked_until = None
            self.db.commit()
        
        return pin
    
    def verify_pin(self, pin: str, store_id: int) -> Optional[models.User]:
        """
        Verifica PIN e retorna o usuário
        
        Args:
            pin: PIN de 6 dígitos
            store_id: ID da loja
            
        Returns:
            Usuário se o PIN for válido, None caso contrário
        """
        # Hash do PIN fornecido
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        
        # Busca usuário com esse PIN que tenha acesso à loja
        user = self.db.query(models.User).join(
            models.StoreAccess
        ).filter(
            models.User.pin_code == pin_hash,
            models.StoreAccess.store_id == store_id,
            models.User.is_active == True
        ).first()
        
        if not user:
            return None
        
        # Verifica se está bloqueado
        if user.pin_locked_until and user.pin_locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"PIN bloqueado até {user.pin_locked_until}"
            )
        
        # Reset tentativas em caso de sucesso
        user.pin_attempts = 0
        user.pin_locked_until = None
        self.db.commit()
        
        return user
    
    def register_failed_pin_attempt(self, pin: str):
        """
        Registra tentativa falha de PIN
        
        Args:
            pin: PIN tentado
        """
        # Hash do PIN
        pin_hash = hashlib.sha256(pin.encode()).hexdigest()
        
        # Busca usuário
        user = self.db.query(models.User).filter(
            models.User.pin_code == pin_hash
        ).first()
        
        if user:
            user.pin_attempts += 1
            
            # Bloqueia se exceder tentativas
            if user.pin_attempts >= self.pin_max_attempts:
                user.pin_locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.pin_lockout_minutes
                )
            
            self.db.commit()
    
    # ═══════════════════════════════════════════════════════════
    # RATE LIMITING
    # ═══════════════════════════════════════════════════════════
    
    def check_rate_limit(
        self, 
        key: str, 
        max_requests: int = 60, 
        window_seconds: int = 60
    ) -> bool:
        """
        Verifica rate limit para uma chave
        
        Args:
            key: Chave única (ex: f"login:{ip_address}")
            max_requests: Máximo de requisições permitidas
            window_seconds: Janela de tempo em segundos
            
        Returns:
            True se dentro do limite, False se excedeu
        """
        pipe = redis_client.pipeline()
        now = datetime.now().timestamp()
        window_start = now - window_seconds
        
        # Remove requisições antigas
        pipe.zremrangebyscore(key, 0, window_start)
        
        # Conta requisições na janela
        pipe.zcard(key)
        
        # Adiciona requisição atual
        pipe.zadd(key, {str(now): now})
        
        # Define TTL
        pipe.expire(key, window_seconds)
        
        results = pipe.execute()
        request_count = results[1]
        
        return request_count < max_requests
    
    def apply_rate_limit(self, identifier: str, endpoint: str):
        """
        Aplica rate limiting a um endpoint
        
        Args:
            identifier: Identificador único (IP, user_id, etc)
            endpoint: Nome do endpoint
            
        Raises:
            HTTPException: Se o rate limit for excedido
        """
        # Define limites por endpoint
        limits = {
            "login": (5, 300),      # 5 tentativas em 5 minutos
            "payment": (10, 60),    # 10 pagamentos por minuto
            "default": (60, 60)     # 60 requisições por minuto (padrão)
        }
        
        max_requests, window = limits.get(endpoint, limits["default"])
        key = f"rate_limit:{endpoint}:{identifier}"
        
        if not self.check_rate_limit(key, max_requests, window):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit excedido. Máximo {max_requests} requisições em {window} segundos."
            )
    
    # ═══════════════════════════════════════════════════════════
    # VALIDAÇÃO DE DADOS
    # ═══════════════════════════════════════════════════════════
    
    def validate_cpf(self, cpf: str) -> bool:
        """
        Valida CPF brasileiro
        
        Args:
            cpf: CPF a validar
            
        Returns:
            True se válido
        """
        # Remove caracteres não numéricos
        cpf = ''.join(filter(str.isdigit, cpf))
        
        # Verifica se tem 11 dígitos
        if len(cpf) != 11:
            return False
        
        # Verifica se todos os dígitos são iguais
        if cpf == cpf[0] * 11:
            return False
        
        # Validação do primeiro dígito
        soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
        digito1 = 11 - (soma % 11)
        if digito1 > 9:
            digito1 = 0
        
        if int(cpf[9]) != digito1:
            return False
        
        # Validação do segundo dígito
        soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
        digito2 = 11 - (soma % 11)
        if digito2 > 9:
            digito2 = 0
        
        return int(cpf[10]) == digito2
    
    def validate_cnpj(self, cnpj: str) -> bool:
        """
        Valida CNPJ brasileiro
        
        Args:
            cnpj: CNPJ a validar
            
        Returns:
            True se válido
        """
        # Remove caracteres não numéricos
        cnpj = ''.join(filter(str.isdigit, cnpj))
        
        # Verifica se tem 14 dígitos
        if len(cnpj) != 14:
            return False
        
        # Verifica se todos os dígitos são iguais
        if cnpj == cnpj[0] * 14:
            return False
        
        # Validação dos dígitos verificadores
        multiplicadores1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        multiplicadores2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        
        # Primeiro dígito
        soma = sum(int(cnpj[i]) * multiplicadores1[i] for i in range(12))
        digito1 = 11 - (soma % 11)
        if digito1 > 9:
            digito1 = 0
        
        if int(cnpj[12]) != digito1:
            return False
        
        # Segundo dígito
        soma = sum(int(cnpj[i]) * multiplicadores2[i] for i in range(13))
        digito2 = 11 - (soma % 11)
        if digito2 > 9:
            digito2 = 0
        
        return int(cnpj[13]) == digito2
    
    def sanitize_input(self, text: str, max_length: int = 500) -> str:
        """
        Sanitiza input do usuário
        
        Args:
            text: Texto a sanitizar
            max_length: Tamanho máximo permitido
            
        Returns:
            Texto sanitizado
        """
        if not text:
            return ""
        
        # Remove caracteres de controle
        text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
        
        # Limita tamanho
        text = text[:max_length]
        
        # Remove espaços extras
        text = ' '.join(text.split())
        
        return text.strip()
    
    # ═══════════════════════════════════════════════════════════
    # VALIDAÇÃO DE TENANT (MULTI-LOJA)
    # ═══════════════════════════════════════════════════════════
    
    def validate_tenant_access(
        self, 
        user_id: int, 
        store_id: int, 
        required_role: Optional[str] = None
    ) -> bool:
        """
        Valida se o usuário tem acesso à loja
        
        Args:
            user_id: ID do usuário
            store_id: ID da loja
            required_role: Role necessária (opcional)
            
        Returns:
            True se tem acesso
            
        Raises:
            HTTPException: Se não tem acesso
        """
        access = self.db.query(models.StoreAccess).filter(
            models.StoreAccess.user_id == user_id,
            models.StoreAccess.store_id == store_id
        ).first()
        
        if not access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acesso negado a esta loja"
            )
        
        if required_role:
            role = self.db.query(models.Role).filter(
                models.Role.id == access.role_id
            ).first()
            
            if not role or role.machine_name != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissão '{required_role}' necessária"
                )
        
        return True
    
    # ═══════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES PRIVADOS
    # ═══════════════════════════════════════════════════════════
    
    def _save_refresh_token(self, user_id: int, token: str, expires: datetime):
        """Salva refresh token no banco"""
        # Implementação dependeria do modelo de RefreshToken
        # Por enquanto, apenas loga
        pass
    
    def _is_token_revoked(self, jti: str) -> bool:
        """Verifica se o token está na blacklist"""
        if not jti:
            return False
        return redis_client.exists(f"revoked_token:{jti}") > 0
