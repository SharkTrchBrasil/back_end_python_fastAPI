# 🚀 WINDSURF SAAS MENU - DOCUMENTAÇÃO DE PRODUÇÃO

## 📋 Índice
1. [Visão Geral](#visão-geral)
2. [Funcionalidades Implementadas](#funcionalidades-implementadas)
3. [Arquitetura do Sistema](#arquitetura-do-sistema)
4. [Instalação e Configuração](#instalação-e-configuração)
5. [API Reference](#api-reference)
6. [WebSocket Events](#websocket-events)
7. [Segurança](#segurança)
8. [Testes](#testes)
9. [Deploy em Produção](#deploy-em-produção)
10. [Monitoramento](#monitoramento)

---

## 🎯 Visão Geral

Sistema completo de gestão de restaurante com funcionalidades avançadas para produção.

### Stack Tecnológico
- **Backend**: FastAPI (Python 3.11)
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **WebSocket**: Socket.IO
- **Pagamentos**: Mercado Pago API
- **Autenticação**: JWT + PIN
- **Container**: Docker & Docker Compose

---

## ✅ Funcionalidades Implementadas

### 1. Sistema de Mesas e Comandas
- ✅ Gerenciamento de status em tempo real (AVAILABLE, OCCUPIED, RESERVED, CLEANING, MAINTENANCE)
- ✅ Criação de comandas vinculadas às mesas
- ✅ Atribuição de mesas a funcionários
- ✅ Status visual colorido no dashboard
- ✅ Histórico detalhado de atividades
- ✅ Relatórios de uso e receita
- ✅ Split de pagamento (igual, percentual, customizado)
- ✅ Transferência de comandas entre mesas

### 2. Integração Mercado Pago
- ✅ Pagamento PIX com QR Code
- ✅ Link de pagamento para cartão
- ✅ Boleto bancário
- ✅ Webhook para notificações em tempo real
- ✅ Reembolso total e parcial
- ✅ Validação de assinatura HMAC

### 3. Sistema de Segurança
- ✅ JWT com refresh tokens
- ✅ Login com PIN (6 dígitos)
- ✅ Rate limiting por endpoint
- ✅ Validação multi-tenant
- ✅ Headers de segurança (CSP, HSTS, etc)
- ✅ Validação de CPF/CNPJ
- ✅ Sanitização de inputs

### 4. WebSocket (Socket.IO)
- ✅ Notificações em tempo real
- ✅ Atualização de status de mesas
- ✅ Eventos de pagamento
- ✅ Sistema de salas por loja
- ✅ Heartbeat e reconexão automática
- ✅ Métricas de conexões

### 5. Testes Automatizados
- ✅ Testes unitários
- ✅ Testes de integração
- ✅ Testes de performance
- ✅ Mock de serviços externos

---

## 🏗️ Arquitetura do Sistema

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│    NGINX    │────▶│   FastAPI   │
│   (Flutter) │     │   (Proxy)   │     │   Backend   │
└─────────────┘     └─────────────┘     └─────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────┐
                    │                           │                           │
            ┌───────▼────────┐        ┌────────▼────────┐         ┌────────▼────────┐
            │   PostgreSQL   │        │     Redis       │         │   Socket.IO     │
            │   (Database)   │        │    (Cache)      │         │  (WebSocket)    │
            └────────────────┘        └─────────────────┘         └─────────────────┘
                                                │
                                    ┌───────────▼───────────┐
                                    │    Mercado Pago      │
                                    │       (API)          │
                                    └───────────────────────┘
```

---

## 🛠️ Instalação e Configuração

### Pré-requisitos
- Docker & Docker Compose
- Python 3.11+ (desenvolvimento local)
- PostgreSQL 15
- Redis 7

### 1. Clone o Repositório
```bash
git clone https://github.com/yourusername/menuhub-backend.git
cd menuhub-backend
```

### 2. Configure Variáveis de Ambiente
```bash
cp .env.example .env
# Edite .env com suas configurações
```

### 3. Configuração Essencial (.env)
```env
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/menuhub_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars
JWT_ALGORITHM=HS256

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=TEST-your-access-token
MERCADOPAGO_PUBLIC_KEY=TEST-your-public-key
MERCADOPAGO_APP_ID=your-app-id
MERCADOPAGO_WEBHOOK_SECRET=your-webhook-secret
MERCADOPAGO_ENVIRONMENT=sandbox
MERCADOPAGO_NOTIFICATION_URL=https://yourapi.com/webhook/mercadopago

# App
ENVIRONMENT=production
DEBUG=false
CORS_ORIGINS=https://yourfrontend.com
```

### 4. Execute com Docker Compose
```bash
# Build e inicia todos os serviços
docker-compose up -d

# Verifica logs
docker-compose logs -f backend

# Para desenvolvimento local
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

pip install -r requirements.txt
python main.py
```

### 5. Execute Migrações
```bash
# Dentro do container
docker exec -it menuhub_backend bash
alembic upgrade head

# Ou localmente
alembic upgrade head
```

---

## 📚 API Reference

### Autenticação

#### PIN Login
```http
POST /api/auth/pin-login
Content-Type: application/json

{
    "pin": "123456",
    "store_id": 1
}
```

### Mesas

#### Listar Dashboard
```http
GET /stores/{store_id}/tables/dashboard
Authorization: Bearer {token}
```

#### Criar Mesa
```http
POST /stores/{store_id}/tables
Authorization: Bearer {token}

{
    "saloon_id": 1,
    "name": "Mesa 01",
    "max_capacity": 4,
    "location_description": "Próximo à janela"
}
```

#### Atribuir Funcionário
```http
POST /stores/{store_id}/tables/assign-employee
Authorization: Bearer {token}

{
    "table_id": 1,
    "employee_id": 10
}
```

#### Abrir Mesa
```http
POST /stores/{store_id}/tables/open
Authorization: Bearer {token}

{
    "table_id": 1,
    "customer_name": "João Silva",
    "customer_contact": "11999999999",
    "attendant_id": 10
}
```

#### Split de Pagamento
```http
POST /stores/{store_id}/tables/split-payment
Authorization: Bearer {token}

{
    "command_id": 1,
    "split_type": "equal",
    "splits": [
        {"customer_name": "João"},
        {"customer_name": "Maria"},
        {"customer_name": "Pedro"}
    ]
}
```

### Pagamentos (Mercado Pago)

#### Criar Pagamento PIX
```http
POST /payments/create
Authorization: Bearer {token}

{
    "command_id": 1,
    "payment_method_type": "pix"
}

Response:
{
    "payment_id": "12345",
    "status": "pending",
    "qr_code": "00020126330014BR.GOV.BCB.PIX...",
    "qr_code_base64": "data:image/png;base64,..."
}
```

---

## 🔌 WebSocket Events

### Conexão
```javascript
const socket = io('wss://api.yourapp.com', {
    path: '/socket.io/',
    transports: ['websocket'],
    auth: {
        token: 'your-jwt-token',
        store_id: 1
    }
});
```

### Eventos Disponíveis

#### Cliente → Servidor
- `authenticate` - Autenticação inicial
- `watch_table` - Observar mesa específica
- `unwatch_table` - Parar de observar mesa
- `ping` - Manter conexão viva

#### Servidor → Cliente
- `authenticated` - Confirmação de autenticação
- `initial_data` - Dados iniciais
- `table_update` - Atualização de mesa
- `order_update` - Atualização de pedido
- `payment_update` - Atualização de pagamento
- `notification` - Notificações gerais
- `heartbeat` - Heartbeat do servidor

### Exemplo de Uso
```javascript
// Observar mesa
socket.emit('watch_table', { table_id: 1 });

// Receber atualizações
socket.on('table_update', (data) => {
    console.log('Mesa atualizada:', data);
    // {
    //     type: 'table_update',
    //     table: {
    //         id: 1,
    //         name: 'Mesa 01',
    //         status: 'OCCUPIED',
    //         status_color: '#dc3545'
    //     },
    //     timestamp: '2024-01-01T12:00:00Z'
    // }
});
```

---

## 🔐 Segurança

### Headers de Segurança
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ X-XSS-Protection: 1; mode=block
- ✅ Content-Security-Policy configurado
- ✅ Strict-Transport-Security (HTTPS)

### Rate Limiting
- Login: 5 tentativas em 5 minutos
- PIN: 3 tentativas em 3 minutos
- Pagamentos: 10 requisições por minuto
- Geral: 60 requisições por minuto

### Validações
- CPF/CNPJ brasileiros
- Sanitização de inputs
- Tamanho máximo de requisições
- Validação de tenant_id

---

## 🧪 Testes

### Executar Todos os Testes
```bash
# No container
docker exec -it menuhub_backend pytest

# Localmente
pytest -v

# Com coverage
pytest --cov=src --cov-report=html
```

### Testes Específicos
```bash
# Apenas testes de mesas
pytest tests/test_table_service.py -v

# Apenas testes de integração
pytest -m integration

# Apenas testes de performance
pytest -m performance
```

---

## 🚀 Deploy em Produção

### 1. Preparação
```bash
# Build da imagem
docker build -t menuhub-backend:latest .

# Tag para registry
docker tag menuhub-backend:latest your-registry/menuhub-backend:latest

# Push para registry
docker push your-registry/menuhub-backend:latest
```

### 2. Configuração SSL/TLS
```nginx
server {
    listen 443 ssl http2;
    server_name api.yourapp.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    location / {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    location /socket.io/ {
        proxy_pass http://backend:8000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3. Deploy com Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: menuhub-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: menuhub-backend
  template:
    metadata:
      labels:
        app: menuhub-backend
    spec:
      containers:
      - name: backend
        image: your-registry/menuhub-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: menuhub-secrets
              key: database-url
```

---

## 📊 Monitoramento

### Endpoints de Monitoramento
- `/health` - Health check
- `/metrics` - Métricas do sistema
- `/api/docs` - Documentação Swagger (dev only)

### Grafana Dashboard
1. Acesse: http://localhost:3000
2. Login: admin/admin
3. Dashboards disponíveis:
   - System Overview
   - API Performance
   - WebSocket Connections
   - Payment Analytics

### Logs
```bash
# Ver logs do backend
docker-compose logs -f backend

# Ver logs específicos
docker exec -it menuhub_backend tail -f /app/logs/app.log

# Logs estruturados com jq
docker-compose logs backend | jq '.'
```

### Alertas Configurados
- CPU > 80%
- Memória > 90%
- Taxa de erro > 1%
- Tempo de resposta > 2s
- Conexões WebSocket > 1000

---

## 📞 Suporte

### Problemas Comuns

#### Erro de Conexão com Banco
```bash
# Verifica se o PostgreSQL está rodando
docker-compose ps postgres

# Recria o container
docker-compose restart postgres
```

#### WebSocket não Conecta
```bash
# Verifica configuração do NGINX
docker exec -it menuhub_nginx nginx -t

# Verifica logs do Socket.IO
docker-compose logs backend | grep -i socket
```

#### Rate Limit Excedido
```bash
# Limpa cache do Redis
docker exec -it menuhub_redis redis-cli FLUSHDB
```

### Contato
- **Email**: suporte@menuhub.com.br
- **Discord**: [Link do Discord]
- **GitHub Issues**: [Link do Repositório]

---

## 📄 Licença

Copyright © 2024 MenuHub. Todos os direitos reservados.

---

**Última atualização**: 31 de Outubro de 2024
