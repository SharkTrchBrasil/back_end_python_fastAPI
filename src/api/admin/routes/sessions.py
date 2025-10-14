from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from src.api.schemas.store.sessions import SessionOut
from src.core.database import GetDBDep
from src.core.dependencies import GetCurrentUserDep
from src.core import models

from src.socketio_instance import sio

router = APIRouter(prefix="/sessions", tags=["Sessions"])


# ✅ Schema para o body do endpoint de revogar todos
class RevokeAllOthersRequest(BaseModel):
    current_sid: str


@router.get("/active", response_model=List[SessionOut])
async def get_active_sessions(
    current_sid: str | None = None,  # ✅ NOVO: Parâmetro opcional
    db: GetDBDep = Depends(),
    current_user: GetCurrentUserDep = Depends()
):
    sessions = db.query(models.StoreSession).filter(
        models.StoreSession.user_id == current_user.id,
        models.StoreSession.client_type == 'admin'
    ).order_by(models.StoreSession.last_activity.desc()).all()

    return [
        SessionOut(
            id=s.id,
            sid=s.sid,
            device_name=s.device_name,
            device_type=s.device_type,
            platform=s.platform,
            browser=s.browser,
            ip_address=s.ip_address,
            created_at=s.created_at,
            last_activity=s.last_activity,
            is_current=(s.sid == current_sid)  # ✅ Compara com o SID enviado
        )
        for s in sessions
    ]



@router.delete("/{session_id}")
async def revoke_session(
        session_id: int,
        db: GetDBDep,
        current_user: GetCurrentUserDep
):
    """
    Desconecta uma sessão específica pelo ID.
    """
    session = db.query(models.StoreSession).filter(
        models.StoreSession.id == session_id,
        models.StoreSession.user_id == current_user.id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Sessão não encontrada ou você não tem permissão para revogá-la"
        )

    # ✅ NOVO: Envia evento ANTES de desconectar
    try:
        await sio.emit(
            'session_revoked',
            {
                'reason': 'Sessão encerrada por outro dispositivo',
                'message': 'Você foi desconectado. Por favor, faça login novamente.'
            },
            room=session.sid,
            namespace='/admin'
        )
        print(f"✅ Evento 'session_revoked' enviado para {session.sid}")

        # Aguarda um momento para o evento ser entregue
        await asyncio.sleep(0.5)

        await sio.disconnect(session.sid, namespace='/admin')
        print(f"✅ Sessão {session.sid} desconectada via socket")
    except Exception as e:
        print(f"⚠️ Erro ao desconectar socket {session.sid}: {e}")

    # Remove do banco
    db.delete(session)
    db.commit()

    return {
        "message": "Sessão revogada com sucesso",
        "session_id": session_id
    }


@router.post("/revoke-all-others")
async def revoke_all_other_sessions(
        request: RevokeAllOthersRequest,
        db: GetDBDep,
        current_user: GetCurrentUserDep
):
    """
    Desconecta todas as outras sessões do usuário.
    """
    current_sid = request.current_sid

    other_sessions = db.query(models.StoreSession).filter(
        models.StoreSession.user_id == current_user.id,
        models.StoreSession.client_type == 'admin',
        models.StoreSession.sid != current_sid
    ).all()

    count = 0
    for session in other_sessions:
        try:
            # ✅ NOVO: Envia evento antes de desconectar cada sessão
            await sio.emit(
                'session_revoked',
                {
                    'reason': 'Todas as sessões foram encerradas',
                    'message': 'O administrador desconectou todos os dispositivos.'
                },
                room=session.sid,
                namespace='/admin'
            )
            print(f"✅ Evento 'session_revoked' enviado para {session.sid}")

            # Aguarda para o evento ser entregue
            await asyncio.sleep(0.5)

            await sio.disconnect(session.sid, namespace='/admin')
            print(f"✅ Sessão {session.sid} desconectada via socket")
        except Exception as e:
            print(f"⚠️ Erro ao desconectar socket {session.sid}: {e}")

        db.delete(session)
        count += 1

    db.commit()

    return {
        "message": f"{count} sessão(ões) revogada(s) com sucesso",
        "revoked_count": count
    }