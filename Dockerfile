# Multi-stage build para otimização
FROM python:3.11-slim as builder

# Variáveis de ambiente para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Copia requirements
COPY requirements.txt .

# Instala dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ═══════════════════════════════════════════════════════════
# Imagem final
# ═══════════════════════════════════════════════════════════
FROM python:3.11-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Instala apenas runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário não-root
RUN useradd -m -u 1000 menuhub && \
    mkdir -p /app/logs /app/static && \
    chown -R menuhub:menuhub /app

# Define diretório de trabalho
WORKDIR /app

# Copia dependências instaladas do builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copia código da aplicação
COPY --chown=menuhub:menuhub . /app

# Troca para usuário não-root
USER menuhub

# Porta da aplicação
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["python", "main.py"]
