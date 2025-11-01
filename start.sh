#!/bin/bash

# ═══════════════════════════════════════════════════════════
# Script de Inicialização - MenuHub Backend
# ═══════════════════════════════════════════════════════════

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          WINDSURF SAAS MENU - INICIALIZAÇÃO               ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Função para verificar comando
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 não está instalado!${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ $1 encontrado${NC}"
    fi
}

# Função para criar arquivo .env se não existir
create_env_file() {
    if [ ! -f .env ]; then
        echo -e "${YELLOW}📝 Criando arquivo .env...${NC}"
        cat > .env << EOF
# Database
DATABASE_URL=postgresql://menuhub_user:SecurePassword123!@localhost:5432/menuhub_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=RedisPass123!

# JWT
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Mercado Pago (Configure com suas credenciais)
MERCADOPAGO_ACCESS_TOKEN=TEST-your-access-token
MERCADOPAGO_PUBLIC_KEY=TEST-your-public-key
MERCADOPAGO_APP_ID=your-app-id
MERCADOPAGO_WEBHOOK_SECRET=webhook-secret
MERCADOPAGO_ENVIRONMENT=sandbox
MERCADOPAGO_NOTIFICATION_URL=https://yourapi.com/webhook/mercadopago

# App
ENVIRONMENT=development
DEBUG=true
HOST=0.0.0.0
PORT=8000

# CORS
CORS_ORIGINS=*

# Frontend
FRONTEND_URL=http://localhost:3000
EOF
        echo -e "${GREEN}✅ Arquivo .env criado${NC}"
    else
        echo -e "${GREEN}✅ Arquivo .env já existe${NC}"
    fi
}

# Menu de opções
show_menu() {
    echo ""
    echo -e "${YELLOW}Escolha uma opção:${NC}"
    echo "1) Desenvolvimento Local (sem Docker)"
    echo "2) Desenvolvimento com Docker"
    echo "3) Produção com Docker"
    echo "4) Executar Testes"
    echo "5) Executar Migrações"
    echo "6) Limpar e Reconstruir"
    echo "0) Sair"
    echo ""
    read -p "Opção: " choice
}

# Desenvolvimento local
dev_local() {
    echo -e "${YELLOW}🚀 Iniciando desenvolvimento local...${NC}"
    
    # Verifica Python
    check_command python3
    
    # Cria ambiente virtual se não existir
    if [ ! -d "venv" ]; then
        echo -e "${YELLOW}📦 Criando ambiente virtual...${NC}"
        python3 -m venv venv
    fi
    
    # Ativa ambiente virtual
    source venv/bin/activate
    
    # Instala dependências
    echo -e "${YELLOW}📦 Instalando dependências...${NC}"
    pip install -r requirements.txt
    
    # Executa migrações
    echo -e "${YELLOW}🗃️ Executando migrações...${NC}"
    alembic upgrade head
    
    # Inicia servidor
    echo -e "${GREEN}✅ Servidor iniciando em http://localhost:8000${NC}"
    echo -e "${GREEN}📚 Documentação em http://localhost:8000/docs${NC}"
    python main.py
}

# Desenvolvimento com Docker
dev_docker() {
    echo -e "${YELLOW}🐳 Iniciando com Docker (desenvolvimento)...${NC}"
    
    check_command docker
    check_command docker-compose
    
    # Para containers antigos
    docker-compose down
    
    # Build e inicia
    docker-compose up --build -d
    
    echo -e "${YELLOW}⏳ Aguardando serviços iniciarem...${NC}"
    sleep 10
    
    # Executa migrações
    echo -e "${YELLOW}🗃️ Executando migrações...${NC}"
    docker exec menuhub_backend alembic upgrade head
    
    # Mostra logs
    echo -e "${GREEN}✅ Serviços iniciados!${NC}"
    echo -e "${GREEN}📚 API: http://localhost:8000${NC}"
    echo -e "${GREEN}📊 Grafana: http://localhost:3000${NC}"
    echo ""
    echo -e "${YELLOW}Logs (Ctrl+C para sair):${NC}"
    docker-compose logs -f backend
}

# Produção com Docker
prod_docker() {
    echo -e "${YELLOW}🚀 Iniciando em modo PRODUÇÃO...${NC}"
    
    check_command docker
    check_command docker-compose
    
    # Verifica se .env tem configurações de produção
    if grep -q "DEBUG=true" .env; then
        echo -e "${RED}⚠️  AVISO: DEBUG está ativado no .env!${NC}"
        read -p "Continuar mesmo assim? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            exit 0
        fi
    fi
    
    # Para containers antigos
    docker-compose down
    
    # Build otimizado para produção
    docker-compose -f docker-compose.yml up --build -d
    
    echo -e "${YELLOW}⏳ Aguardando serviços iniciarem...${NC}"
    sleep 15
    
    # Executa migrações
    docker exec menuhub_backend alembic upgrade head
    
    # Verifica saúde dos serviços
    echo -e "${YELLOW}🔍 Verificando saúde dos serviços...${NC}"
    docker-compose ps
    
    echo -e "${GREEN}✅ Sistema em produção iniciado!${NC}"
}

# Executar testes
run_tests() {
    echo -e "${YELLOW}🧪 Executando testes...${NC}"
    
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    
    # Testes com coverage
    pytest -v --cov=src --cov-report=html --cov-report=term
    
    echo -e "${GREEN}✅ Testes concluídos!${NC}"
    echo -e "${GREEN}📊 Relatório HTML em: htmlcov/index.html${NC}"
}

# Executar migrações
run_migrations() {
    echo -e "${YELLOW}🗃️ Executando migrações...${NC}"
    
    read -p "Local ou Docker? (l/d): " env_choice
    
    if [ "$env_choice" == "l" ]; then
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        alembic upgrade head
    else
        docker exec menuhub_backend alembic upgrade head
    fi
    
    echo -e "${GREEN}✅ Migrações executadas!${NC}"
}

# Limpar e reconstruir
clean_rebuild() {
    echo -e "${YELLOW}🧹 Limpando e reconstruindo...${NC}"
    
    read -p "Isso irá APAGAR todos os dados. Confirma? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        exit 0
    fi
    
    # Para e remove containers
    docker-compose down -v
    
    # Remove arquivos temporários
    find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    rm -rf htmlcov .coverage .pytest_cache
    
    # Reconstrói
    docker-compose build --no-cache
    
    echo -e "${GREEN}✅ Sistema limpo e reconstruído!${NC}"
}

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

# Verifica dependências básicas
echo -e "${YELLOW}🔍 Verificando dependências...${NC}"
check_command git

# Cria arquivo .env se necessário
create_env_file

# Menu principal
while true; do
    show_menu
    
    case $choice in
        1)
            dev_local
            break
            ;;
        2)
            dev_docker
            break
            ;;
        3)
            prod_docker
            break
            ;;
        4)
            run_tests
            ;;
        5)
            run_migrations
            ;;
        6)
            clean_rebuild
            ;;
        0)
            echo -e "${GREEN}👋 Até logo!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Opção inválida!${NC}"
            ;;
    esac
done
