"""
Aplicação Principal - Windsurf SaaS Menu
========================================
Sistema completo de gestão de restaurante
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Import das configurações
from src.core.config import config
from src.core.database import engine
from src.core import models

# Import dos middlewares de segurança
from src.core.middleware.security_middleware import setup_middleware

# Import do Socket.IO
from src.api.admin.socketio.socketio_manager import setup_socketio, start_background_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação"""
    
    # STARTUP
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO WINDSURF SAAS MENU")
    logger.info("=" * 60)
    
    # Cria tabelas do banco se não existirem
    logger.info("📊 Criando tabelas do banco de dados...")
    models.Base.metadata.create_all(bind=engine)
    
    # Inicia tarefas em background do Socket.IO
    logger.info("🔌 Iniciando Socket.IO...")
    start_background_tasks()
    
    # Configurações adicionais
    logger.info(f"🌍 Ambiente: {config.ENVIRONMENT}")
    logger.info(f"🔐 Debug Mode: {config.DEBUG}")
    logger.info(f"💰 Mercado Pago: {'Sandbox' if config.MERCADOPAGO_ENVIRONMENT == 'sandbox' else 'Produção'}")
    
    logger.info("=" * 60)
    logger.info("✅ APLICAÇÃO PRONTA!")
    logger.info("=" * 60)
    
    yield
    
    # SHUTDOWN
    logger.info("=" * 60)
    logger.info("👋 ENCERRANDO APLICAÇÃO")
    logger.info("=" * 60)


# Cria aplicação FastAPI
app = FastAPI(
    title="Windsurf SaaS Menu API",
    description="Sistema completo de gestão de restaurante com mesas, comandas e pagamentos",
    version="1.0.0",
    docs_url="/docs" if config.DEBUG else None,  # Desabilita docs em produção
    redoc_url="/redoc" if config.DEBUG else None,
    lifespan=lifespan
)

# Configura middlewares de segurança
setup_middleware(app)

# ═══════════════════════════════════════════════════════════
# ROTAS DA API
# ═══════════════════════════════════════════════════════════

# Import das rotas
from src.api.admin.routes import (
    table,
    mercadopago_webhook,
    auth_pin
)

# Registra rotas
app.include_router(table.router)
app.include_router(mercadopago_webhook.router)
app.include_router(auth_pin.router)

# ═══════════════════════════════════════════════════════════
# ROTAS BÁSICAS
# ═══════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Endpoint raiz"""
    return {
        "name": "Windsurf SaaS Menu API",
        "version": "1.0.0",
        "status": "operational",
        "environment": config.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check para monitoramento"""
    
    # Verifica conexão com banco
    try:
        from src.core.database import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Verifica Redis (se configurado)
    redis_status = "not_configured"
    try:
        from src.core.security.security_service import redis_client
        redis_client.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "services": {
            "database": db_status,
            "redis": redis_status,
            "mercadopago": "configured" if config.MERCADOPAGO_ACCESS_TOKEN else "not_configured"
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Métricas do sistema (para admin)"""
    
    from src.api.admin.socketio.socketio_manager import connection_manager
    
    return {
        "websocket": connection_manager.get_metrics(),
        "timestamp": datetime.utcnow().isoformat()
    }


# ═══════════════════════════════════════════════════════════
# TRATAMENTO DE ERROS GLOBAL
# ═══════════════════════════════════════════════════════════

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handler para 404"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "O recurso solicitado não foi encontrado",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handler para erros internos"""
    
    logger.error(f"❌ Erro interno: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Ocorreu um erro interno. Por favor, tente novamente mais tarde.",
            "request_id": getattr(request.state, "request_id", "unknown")
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handler para erros de validação"""
    return JSONResponse(
        status_code=400,
        content={
            "error": "Validation Error",
            "message": str(exc)
        }
    )


# ═══════════════════════════════════════════════════════════
# CONFIGURAÇÃO DO SOCKET.IO
# ═══════════════════════════════════════════════════════════

# Integra Socket.IO com FastAPI
app = setup_socketio(app)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    """Função principal para executar o servidor"""
    
    # Configurações do Uvicorn
    uvicorn_config = {
        "app": "main:app",
        "host": config.HOST,
        "port": config.PORT,
        "reload": config.DEBUG,
        "log_level": "info" if config.DEBUG else "warning",
        "access_log": config.DEBUG,
        "workers": 1 if config.DEBUG else 4,  # Multi-worker em produção
    }
    
    # Adiciona SSL em produção
    if not config.DEBUG and config.SSL_CERT_FILE and config.SSL_KEY_FILE:
        uvicorn_config.update({
            "ssl_certfile": config.SSL_CERT_FILE,
            "ssl_keyfile": config.SSL_KEY_FILE,
        })
    
    # Inicia servidor
    logger.info(f"🌐 Servidor iniciando em http://{config.HOST}:{config.PORT}")
    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    from datetime import datetime
    main()
