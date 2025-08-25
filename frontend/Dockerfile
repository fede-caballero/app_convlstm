FROM nvidia/cuda:11.8-devel-ubuntu20.04

# Evitar prompts interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar LROSE (ajustar según tu instalación)
# RUN wget https://github.com/NCAR/lrose-core/releases/download/lrose-core-20230815/lrose-core-20230815.x86_64.tgz
# RUN tar -xzf lrose-core-20230815.x86_64.tgz -C /opt/
# ENV PATH="/opt/lrose-core-20230815.x86_64/bin:${PATH}"

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de la aplicación
COPY scripts/ ./scripts/
COPY requirements.txt .

# Instalar dependencias Python
RUN pip3 install --no-cache-dir -r requirements.txt

# Crear directorios de datos
RUN mkdir -p /data/radar/mdv \
    /data/radar/netcdf \
    /data/radar/predictions \
    /data/radar/predictions_mdv \
    /models \
    /logs

# Configurar permisos
RUN chmod +x scripts/*.py scripts/*.sh

# Exponer puerto para API
EXPOSE 8000

# Comando por defecto
CMD ["python3", "scripts/api_server.py"]
