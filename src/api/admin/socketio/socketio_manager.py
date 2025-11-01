"""
Gerenciador Socket.IO para Produção
===================================
Sistema completo de notificações em tempo real
"""

import logging
import json
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict

import socketio
from socketio import AsyncNamespace
from sqlalchemy.orm import Session

from src.core import models
from src.core.database import get_db
from src.core.utils.enums import TableStatus, OrderStatus, PaymentStatus

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO SERVIDOR SOCKET.IO
# ═══════════════════════════════════════════════════════════

# Configuração do servidor Socket.IO assíncrono
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',  # Em produção, especificar domínios permitidos
    logger=True,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=10**8  # 100MB para uploads grandes
)


# ═══════════════════════════════════════════════════════════
# GERENCIADOR DE CONEXÕES
# ═══════════════════════════════════════════════════════════

class ConnectionManager:
    """Gerencia conexões WebSocket e salas"""
    
    def __init__(self):
        # Mapeia store_id para conjunto de session_ids
        self.store_connections: Dict[int, Set[str]] = defaultdict(set)
        
        # Mapeia session_id para informações do usuário
        self.session_info: Dict[str, Dict[str, Any]] = {}
        
        # Mapeia table_id para conjunto de session_ids observando
        self.table_watchers: Dict[int, Set[str]] = defaultdict(set)
        
        # Rate limiting por IP
        self.rate_limits: Dict[str, List[datetime]] = defaultdict(list)
        
        # Métricas
        self.metrics = {
            "total_connections": 0,
            "messages_sent": 0,
            "messages_received": 0,
            "errors": 0
        }
    
    async def add_connection(
        self, 
        session_id: str, 
        store_id: int, 
        user_id: int,
        user_name: str,
        role: str,
        ip_address: str
    ):
        """Adiciona nova conexão"""
        
        # Verifica rate limit
        if not self._check_rate_limit(ip_address):
            logger.warning(f"⚠️ Rate limit excedido para IP {ip_address}")
            return False
        
        # Registra conexão
        self.store_connections[store_id].add(session_id)
        self.session_info[session_id] = {
            "store_id": store_id,
            "user_id": user_id,
            "user_name": user_name,
            "role": role,
            "ip_address": ip_address,
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow()
        }
        
        self.metrics["total_connections"] += 1
        
        logger.info(f"✅ Nova conexão: {user_name} (ID: {session_id}) na loja {store_id}")
        return True
    
    async def remove_connection(self, session_id: str):
        """Remove conexão"""
        
        if session_id in self.session_info:
            info = self.session_info[session_id]
            store_id = info["store_id"]
            
            # Remove de todas as salas
            self.store_connections[store_id].discard(session_id)
            
            # Remove de observadores de mesa
            for table_watchers in self.table_watchers.values():
                table_watchers.discard(session_id)
            
            # Remove informações da sessão
            del self.session_info[session_id]
            
            logger.info(f"👋 Desconectado: {info['user_name']} (ID: {session_id})")
    
    def get_store_sessions(self, store_id: int) -> List[str]:
        """Retorna sessões de uma loja"""
        return list(self.store_connections.get(store_id, []))
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retorna informações da sessão"""
        return self.session_info.get(session_id)
    
    def add_table_watcher(self, session_id: str, table_id: int):
        """Adiciona observador de mesa"""
        self.table_watchers[table_id].add(session_id)
    
    def remove_table_watcher(self, session_id: str, table_id: int):
        """Remove observador de mesa"""
        self.table_watchers[table_id].discard(session_id)
    
    def get_table_watchers(self, table_id: int) -> List[str]:
        """Retorna observadores de uma mesa"""
        return list(self.table_watchers.get(table_id, []))
    
    def update_activity(self, session_id: str):
        """Atualiza última atividade"""
        if session_id in self.session_info:
            self.session_info[session_id]["last_activity"] = datetime.utcnow()
    
    def _check_rate_limit(self, ip_address: str, max_connections: int = 10) -> bool:
        """Verifica rate limit por IP"""
        now = datetime.utcnow()
        
        # Remove conexões antigas (mais de 1 hora)
        self.rate_limits[ip_address] = [
            timestamp for timestamp in self.rate_limits[ip_address]
            if now - timestamp < timedelta(hours=1)
        ]
        
        # Verifica limite
        if len(self.rate_limits[ip_address]) >= max_connections:
            return False
        
        # Adiciona nova conexão
        self.rate_limits[ip_address].append(now)
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Retorna métricas do sistema"""
        active_connections = sum(
            1 for _ in self.session_info.values()
        )
        
        stores_connected = len([
            store_id for store_id, sessions in self.store_connections.items()
            if sessions
        ])
        
        return {
            **self.metrics,
            "active_connections": active_connections,
            "stores_connected": stores_connected,
            "tables_watched": len([
                table_id for table_id, watchers in self.table_watchers.items()
                if watchers
            ])
        }


# Instância global do gerenciador
connection_manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════
# NAMESPACE ADMIN - GESTÃO DO RESTAURANTE
# ═══════════════════════════════════════════════════════════

class AdminNamespace(AsyncNamespace):
    """Namespace para administração do restaurante"""
    
    def __init__(self, namespace=None):
        super().__init__(namespace)
    
    async def on_connect(self, sid, environ):
        """Evento de conexão"""
        
        # Extrai IP do cliente
        ip_address = environ.get('REMOTE_ADDR', 'unknown')
        
        logger.info(f"🔌 Tentativa de conexão: {sid} de {ip_address}")
        
        # Por enquanto aceita a conexão
        # A autenticação será feita no evento 'authenticate'
        return True
    
    async def on_authenticate(self, sid, data):
        """Autentica o usuário após conexão"""
        
        try:
            # Extrai dados de autenticação
            token = data.get('token')
            store_id = data.get('store_id')
            
            if not token or not store_id:
                await self.emit('error', {
                    'message': 'Token e store_id são obrigatórios'
                }, room=sid)
                return await self.disconnect(sid)
            
            # Verifica token (simplificado - em produção usar SecurityService)
            # user = verify_jwt_token(token)
            user = {
                "id": 1,
                "name": "Admin User",
                "role": "admin"
            }
            
            # Adiciona à sala da loja
            await self.enter_room(sid, f"store_{store_id}")
            
            # Registra conexão
            success = await connection_manager.add_connection(
                session_id=sid,
                store_id=store_id,
                user_id=user["id"],
                user_name=user["name"],
                role=user["role"],
                ip_address="127.0.0.1"  # Pegar do environ
            )
            
            if not success:
                await self.emit('error', {
                    'message': 'Muitas conexões do mesmo IP'
                }, room=sid)
                return await self.disconnect(sid)
            
            # Confirma autenticação
            await self.emit('authenticated', {
                'message': 'Autenticação bem-sucedida',
                'user': user,
                'store_id': store_id
            }, room=sid)
            
            # Envia dados iniciais
            await self._send_initial_data(sid, store_id)
            
            logger.info(f"✅ Autenticado: {user['name']} na loja {store_id}")
            
        except Exception as e:
            logger.error(f"❌ Erro na autenticação: {e}")
            await self.emit('error', {
                'message': 'Erro na autenticação'
            }, room=sid)
            await self.disconnect(sid)
    
    async def on_disconnect(self, sid):
        """Evento de desconexão"""
        await connection_manager.remove_connection(sid)
    
    async def on_watch_table(self, sid, data):
        """Observa uma mesa específica"""
        
        table_id = data.get('table_id')
        if not table_id:
            return
        
        # Adiciona como observador
        connection_manager.add_table_watcher(sid, table_id)
        
        # Entra na sala da mesa
        await self.enter_room(sid, f"table_{table_id}")
        
        logger.info(f"👁️ {sid} observando mesa {table_id}")
    
    async def on_unwatch_table(self, sid, data):
        """Para de observar uma mesa"""
        
        table_id = data.get('table_id')
        if not table_id:
            return
        
        # Remove como observador
        connection_manager.remove_table_watcher(sid, table_id)
        
        # Sai da sala da mesa
        await self.leave_room(sid, f"table_{table_id}")
        
        logger.info(f"👁️‍🗨️ {sid} parou de observar mesa {table_id}")
    
    async def on_ping(self, sid):
        """Responde a ping para manter conexão viva"""
        
        connection_manager.update_activity(sid)
        await self.emit('pong', {'timestamp': datetime.utcnow().isoformat()}, room=sid)
    
    async def _send_initial_data(self, sid, store_id: int):
        """Envia dados iniciais após autenticação"""
        
        try:
            # Busca dados do banco
            db = next(get_db())
            
            # Busca mesas e comandas
            tables = db.query(models.Tables).filter(
                models.Tables.store_id == store_id,
                models.Tables.is_deleted == False
            ).all()
            
            # Formata dados
            tables_data = []
            for table in tables:
                tables_data.append({
                    "id": table.id,
                    "name": table.name,
                    "status": table.status.value,
                    "status_color": table.status_color,
                    "capacity": table.max_capacity,
                    "current_capacity": table.current_capacity,
                    "assigned_employee_id": table.assigned_employee_id
                })
            
            # Envia dados iniciais
            await self.emit('initial_data', {
                'tables': tables_data,
                'timestamp': datetime.utcnow().isoformat()
            }, room=sid)
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar dados iniciais: {e}")
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════
# EMISSORES DE EVENTOS
# ═══════════════════════════════════════════════════════════

class EventEmitter:
    """Emissor de eventos para o frontend"""
    
    @staticmethod
    async def emit_table_update(store_id: int, table_data: Dict[str, Any]):
        """Emite atualização de mesa"""
        
        event_data = {
            "type": "table_update",
            "table": table_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Emite para a loja
        await sio.emit(
            'table_update',
            event_data,
            namespace='/admin',
            room=f"store_{store_id}"
        )
        
        # Emite para observadores da mesa
        if "id" in table_data:
            await sio.emit(
                'table_update',
                event_data,
                namespace='/admin',
                room=f"table_{table_data['id']}"
            )
        
        connection_manager.metrics["messages_sent"] += 1
        logger.info(f"📡 Mesa atualizada: {table_data.get('name')} na loja {store_id}")
    
    @staticmethod
    async def emit_order_update(store_id: int, order_data: Dict[str, Any]):
        """Emite atualização de pedido"""
        
        event_data = {
            "type": "order_update",
            "order": order_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await sio.emit(
            'order_update',
            event_data,
            namespace='/admin',
            room=f"store_{store_id}"
        )
        
        connection_manager.metrics["messages_sent"] += 1
        logger.info(f"📡 Pedido atualizado: #{order_data.get('id')} na loja {store_id}")
    
    @staticmethod
    async def emit_payment_update(store_id: int, payment_data: Dict[str, Any]):
        """Emite atualização de pagamento"""
        
        event_data = {
            "type": "payment_update",
            "payment": payment_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await sio.emit(
            'payment_update',
            event_data,
            namespace='/admin',
            room=f"store_{store_id}"
        )
        
        connection_manager.metrics["messages_sent"] += 1
        logger.info(f"📡 Pagamento atualizado: {payment_data.get('status')} na loja {store_id}")
    
    @staticmethod
    async def emit_notification(
        store_id: int, 
        title: str, 
        message: str, 
        level: str = "info",
        data: Optional[Dict] = None
    ):
        """Emite notificação para a loja"""
        
        event_data = {
            "type": "notification",
            "title": title,
            "message": message,
            "level": level,  # info, warning, error, success
            "data": data or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await sio.emit(
            'notification',
            event_data,
            namespace='/admin',
            room=f"store_{store_id}"
        )
        
        connection_manager.metrics["messages_sent"] += 1
        logger.info(f"📡 Notificação enviada: {title} para loja {store_id}")
    
    @staticmethod
    async def broadcast_metrics():
        """Transmite métricas do sistema (para admin)"""
        
        metrics = connection_manager.get_metrics()
        
        await sio.emit(
            'system_metrics',
            metrics,
            namespace='/admin',
            room='admins'  # Sala especial para administradores
        )


# Instância global do emissor
event_emitter = EventEmitter()


# ═══════════════════════════════════════════════════════════
# TAREFAS ASSÍNCRONAS
# ═══════════════════════════════════════════════════════════

async def cleanup_inactive_connections():
    """Remove conexões inativas periodicamente"""
    
    while True:
        try:
            now = datetime.utcnow()
            timeout = timedelta(minutes=30)
            
            inactive_sessions = [
                sid for sid, info in connection_manager.session_info.items()
                if now - info["last_activity"] > timeout
            ]
            
            for sid in inactive_sessions:
                logger.warning(f"⏰ Removendo conexão inativa: {sid}")
                await connection_manager.remove_connection(sid)
                await sio.disconnect(sid, namespace='/admin')
            
            # Aguarda 5 minutos antes da próxima limpeza
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza de conexões: {e}")
            await asyncio.sleep(60)


async def broadcast_heartbeat():
    """Envia heartbeat para todas as conexões"""
    
    while True:
        try:
            await sio.emit(
                'heartbeat',
                {'timestamp': datetime.utcnow().isoformat()},
                namespace='/admin'
            )
            
            # Aguarda 30 segundos
            await asyncio.sleep(30)
            
        except Exception as e:
            logger.error(f"❌ Erro no heartbeat: {e}")
            await asyncio.sleep(10)


# ═══════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════

def setup_socketio(app):
    """Configura Socket.IO na aplicação"""
    
    # Registra namespace
    sio.register_namespace(AdminNamespace('/admin'))
    
    # Cria aplicação ASGI combinada
    from socketio import ASGIApp
    combined_app = ASGIApp(sio, app)
    
    logger.info("✅ Socket.IO configurado com sucesso")
    
    return combined_app


def start_background_tasks():
    """Inicia tarefas em background"""
    
    asyncio.create_task(cleanup_inactive_connections())
    asyncio.create_task(broadcast_heartbeat())
    
    logger.info("✅ Tarefas em background iniciadas")
