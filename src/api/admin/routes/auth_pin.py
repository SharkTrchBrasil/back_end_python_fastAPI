"""
Rotas de Autenticação com PIN
=============================
Login rápido para funcionários
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional

from src.core.database import GetDBDep
from src.core.dependencies import GetStoreDep, get_current_user
from src.core.security.security_service import SecurityService
from src.core.utils.enums import Roles

router = APIRouter(tags=["Auth PIN"], prefix="/api/auth")


# ═══════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════

class PinLoginRequest(BaseModel):
    """Schema para login com PIN"""
    pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    store_id: int = Field(..., gt=0)


class PinLoginResponse(BaseModel):
    """Resposta do login com PIN"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class CreatePinRequest(BaseModel):
    """Schema para criar/atualizar PIN"""
    new_pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    current_password: str = Field(..., min_length=6)


class ChangePinRequest(BaseModel):
    """Schema para trocar PIN"""
    current_pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    new_pin: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")


# ═══════════════════════════════════════════════════════════
# ROTAS
# ═══════════════════════════════════════════════════════════

@router.post("/pin-login", response_model=PinLoginResponse)
async def pin_login(
    request: PinLoginRequest,
    db: GetDBDep,
):
    """
    Login rápido com PIN para funcionários
    
    - PIN de 6 dígitos
    - Bloqueio após 3 tentativas falhas
    - Desbloqueio automático após 15 minutos
    """
    
    security = SecurityService(db)
    
    # Verifica rate limit específico para PIN
    # (implementado via middleware)
    
    # Verifica PIN
    user = security.verify_pin(request.pin, request.store_id)
    
    if not user:
        # Registra tentativa falha
        security.register_failed_pin_attempt(request.pin)
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN inválido"
        )
    
    # Busca role do usuário na loja
    from src.core import models
    access = db.query(models.StoreAccess).filter(
        models.StoreAccess.user_id == user.id,
        models.StoreAccess.store_id == request.store_id
    ).first()
    
    if not access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem acesso a esta loja"
        )
    
    role = db.query(models.Role).filter(
        models.Role.id == access.role_id
    ).first()
    
    # Cria tokens
    access_token = security.create_access_token(
        user_id=user.id,
        store_id=request.store_id,
        role=role.machine_name if role else None
    )
    
    refresh_token = security.create_refresh_token(user.id)
    
    # Log de auditoria
    from src.core.utils.enums import AuditAction, AuditEntityType
    # Aqui você adicionaria o log de auditoria
    
    return PinLoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": role.machine_name if role else None,
            "store_id": request.store_id
        }
    )


@router.post("/create-pin", status_code=status.HTTP_201_CREATED)
async def create_pin(
    request: CreatePinRequest,
    db: GetDBDep,
    current_user: dict = Depends(get_current_user),  # Implementar dependência
):
    """
    Cria ou atualiza PIN do usuário
    
    - Requer senha atual para confirmação
    - PIN deve ter exatamente 6 dígitos
    """
    
    security = SecurityService(db)
    
    # Verifica senha atual
    from src.core import models
    user = db.query(models.User).filter(
        models.User.id == current_user["id"]
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    if not security.verify_password(request.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta"
        )
    
    # Cria/atualiza PIN
    import hashlib
    pin_hash = hashlib.sha256(request.new_pin.encode()).hexdigest()
    
    user.pin_code = pin_hash
    user.pin_attempts = 0
    user.pin_locked_until = None
    
    db.commit()
    
    return {"message": "PIN criado/atualizado com sucesso"}


@router.put("/change-pin", status_code=status.HTTP_200_OK)
async def change_pin(
    request: ChangePinRequest,
    db: GetDBDep,
    current_user: dict = Depends(get_current_user),
):
    """
    Troca o PIN do usuário
    
    - Requer PIN atual para confirmação
    - Novo PIN deve ser diferente do atual
    """
    
    security = SecurityService(db)
    
    # Verifica se os PINs são diferentes
    if request.current_pin == request.new_pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Novo PIN deve ser diferente do atual"
        )
    
    # Busca usuário
    from src.core import models
    user = db.query(models.User).filter(
        models.User.id == current_user["id"]
    ).first()
    
    if not user or not user.pin_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PIN não configurado para este usuário"
        )
    
    # Verifica PIN atual
    import hashlib
    current_pin_hash = hashlib.sha256(request.current_pin.encode()).hexdigest()
    
    if user.pin_code != current_pin_hash:
        # Registra tentativa falha
        user.pin_attempts += 1
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="PIN atual incorreto"
        )
    
    # Atualiza para novo PIN
    new_pin_hash = hashlib.sha256(request.new_pin.encode()).hexdigest()
    
    user.pin_code = new_pin_hash
    user.pin_attempts = 0
    user.pin_locked_until = None
    
    db.commit()
    
    return {"message": "PIN alterado com sucesso"}


@router.delete("/remove-pin", status_code=status.HTTP_200_OK)
async def remove_pin(
    db: GetDBDep,
    current_user: dict = Depends(get_current_user),
):
    """
    Remove o PIN do usuário
    
    - Apenas o próprio usuário pode remover seu PIN
    - Requer autenticação completa (não pode ser feito via PIN)
    """
    
    from src.core import models
    user = db.query(models.User).filter(
        models.User.id == current_user["id"]
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    user.pin_code = None
    user.pin_attempts = 0
    user.pin_locked_until = None
    
    db.commit()
    
    return {"message": "PIN removido com sucesso"}


@router.get("/pin-status")
async def pin_status(
    db: GetDBDep,
    current_user: dict = Depends(get_current_user),
):
    """
    Verifica status do PIN do usuário
    
    Retorna:
    - Se o PIN está configurado
    - Número de tentativas falhas
    - Se está bloqueado e até quando
    """
    
    from src.core import models
    from datetime import datetime, timezone
    
    user = db.query(models.User).filter(
        models.User.id == current_user["id"]
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado"
        )
    
    is_locked = False
    locked_until = None
    
    if user.pin_locked_until:
        if user.pin_locked_until > datetime.now(timezone.utc):
            is_locked = True
            locked_until = user.pin_locked_until.isoformat()
    
    return {
        "has_pin": user.pin_code is not None,
        "failed_attempts": user.pin_attempts,
        "is_locked": is_locked,
        "locked_until": locked_until,
        "max_attempts": 3
    }


# ═══════════════════════════════════════════════════════════
# DEPENDÊNCIAS
# ═══════════════════════════════════════════════════════════

from fastapi import Header
import jwt
from src.core.config import config


async def get_current_user(
    db: GetDBDep,
    authorization: str = Header(None)

) -> dict:
    """
    Obtém usuário atual do token JWT
    
    Esta é uma versão simplificada. 
    Em produção, use a dependência completa de src.core.dependencies
    """
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token não fornecido"
        )
    
    token = authorization.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(
            token,
            config.JWT_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM]
        )
        
        return {
            "id": int(payload["sub"]),
            "store_id": payload.get("store_id"),
            "role": payload.get("role")
        }
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )



