# =================================================================
# ETAPA 1: "EL TALLER" - Se usa para construir LROSE
# =================================================================
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends wget
ARG DEB_FILE=lrose-core-20250105.ubuntu_22.04.amd64.deb
COPY ${DEB_FILE} .
RUN apt-get install -y ./${DEB_FILE}

# =================================================================
# ETAPA 2: "EL PRODUCTO FINAL" - La imagen limpia y optimizada
# =================================================================
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

# Instalamos las dependencias de EJECUCIÓN, incluyendo la que faltaba.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    libnetcdf19 # <--- LIBRERÍA AÑADIDA

# Copiamos solo los archivos compilados de LROSE desde la etapa "builder"
COPY --from=builder /usr/local/lrose /usr/local/lrose

# Copiamos las variables de entorno
ENV PATH="/usr/local/lrose/bin:${PATH}"
ENV LD_LIBRARY_PATH="/usr/local/lrose/lib:${LD_LIBRARY_PATH}"

# Preparamos el código de tu proyecto
WORKDIR /app
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt
COPY ./backend .

# Nos aseguramos que el script es ejecutable
RUN chmod +x /app/run.sh

# Configuramos el punto de entrada
CMD ["/app/run.sh"]