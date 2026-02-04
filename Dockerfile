# =================================================================
# ETAPA 1: "EL TALLER" - Se usa para construir LROSE
# =================================================================
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends wget
ARG DEB_FILE=lrose-core-20250105.ubuntu_22.04.amd64.deb
COPY ${DEB_FILE} .
RUN apt-get install -y ./${DEB_FILE}

# =================================================================
# ETAPA 2: "FRONTEND BUILD" - Compilar el frontend
# =================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /build
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

# Copy source files (excluding node_modules via .dockerignore)
COPY frontend/next.config.mjs frontend/postcss.config.mjs frontend/tsconfig.json frontend/components.json ./
COPY frontend/tailwind.config.* ./
COPY frontend/app ./app
COPY frontend/components ./components
COPY frontend/lib ./lib
COPY frontend/public ./public
COPY frontend/scripts ./scripts
COPY frontend/hooks ./hooks

RUN npm run build

# =================================================================
# ETAPA 3: "EL PRODUCTO FINAL" - La imagen limpia y optimizada
# =================================================================
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Instalamos las dependencias de EJECUCIÓN
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    libnetcdf19 \
    curl \
    ca-certificates \
    build-essential \
    unzip \
    libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Instalar Rclone (para Ingesta de Datos desde Drive)
RUN curl https://rclone.org/install.sh | bash

# Instalar Node.js (para servir el frontend)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copiamos solo los archivos compilados de LROSE desde la etapa "builder"
COPY --from=builder /usr/local/lrose /usr/local/lrose

# Copiamos las variables de entorno
ENV PATH="/usr/local/lrose/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/lrose/lib:${LD_LIBRARY_PATH}"

# Preparamos el código del backend
WORKDIR /app
COPY backend/requirements.txt .
RUN pip3 install --default-timeout=1000 --no-cache-dir -r requirements.txt
COPY ./backend .
COPY ./tools ./tools

# Copiamos el frontend compilado
COPY --from=frontend-builder /build/.next /app/frontend/.next
COPY --from=frontend-builder /build/public /app/frontend/public
COPY --from=frontend-builder /build/package*.json /app/frontend/
COPY --from=frontend-builder /build/next.config.mjs /app/frontend/

# Instalar solo las dependencias de producción del frontend
WORKDIR /app/frontend
RUN npm ci --only=production --legacy-peer-deps

# Volver al directorio de trabajo principal
WORKDIR /app

# Crear un script de inicio que levante backend y frontend
RUN echo '#!/bin/bash\n\
    set -e\n\
    \n\
    # Auto-detect model path for Vast.ai (Search recursively)\n\
    echo "Searching for .pth model file in /workspace..."\n\
    FOUND_MODEL=$(find /workspace -name "*.pth" | head -n 1)\n\
    \n\
    if [ -n "$FOUND_MODEL" ]; then\n\
    echo "Found model at: $FOUND_MODEL"\n\
    export MODEL_PATH="$FOUND_MODEL"\n\
    else\n\
    echo "WARNING: No .pth model found in /workspace. Using default /app/model/best_convlstm_model.pth"\n\
    fi\n\
    \n\
    echo "Starting backend services..."\n\
    python3 /app/pipeline_worker.py > /app/logs/worker.log 2>&1 &\n\
    python3 /app/api.py > /app/logs/api.log 2>&1 &\n\
    echo "Starting frontend..."\n\
    cd /app/frontend\n\
    npm start > /app/logs/frontend.log 2>&1 &\n\
    echo "All services started. Tailing logs..."\n\
    tail -f /app/logs/*.log\n\
    ' > /app/start_all.sh && chmod +x /app/start_all.sh

# Crear directorio de logs
RUN mkdir -p /app/logs

# Exponer puertos
EXPOSE 8000 3000

# Configuramos el punto de entrada
CMD ["/app/start_all.sh"]